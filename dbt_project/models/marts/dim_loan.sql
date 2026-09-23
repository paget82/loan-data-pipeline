with loans as (

    select * from {{ ref('stg_loans') }}

),

clients as (

    select client_id, credit_score from {{ ref('dim_client') }}

),

-- Per-loan aggregates computed from the actual transaction history,
-- rather than stored as independent random fields, so they stay
-- internally consistent with the rest of the pipeline.
payments as (

    select
        loan_id,
        sum(amount)            as total_payment,
        max(transaction_date)  as last_payment_date

    from {{ ref('fact_transactions') }}
    group by loan_id

)

select
    l.loan_id,
    l.client_id,
    l.principal_amount,
    -- principal_amount is in USD; converted to EUR using the latest
    -- USD-based fixing from the Frankfurter REST API (scalar subquery,
    -- not a join, so a missing/failed API pull never drops loan rows --
    -- it just yields a null conversion for that run)
    round(
        (l.principal_amount::numeric *
            (select rate_per_usd::numeric from {{ ref('dim_exchange_rate') }} where currency_code = 'EUR' limit 1)
        ),
        2
    ) as principal_amount_eur,
    l.interest_rate,
    round((l.interest_rate / 100)::numeric, 4) as int_rate,
    l.is_interest_rate_missing,
    l.origination_date,
    l.origination_date as issue_date,
    l.term_months,
    l.term_months || ' months' as term,
    l.status,
    -- Simplified to three reporting-friendly statuses. "delinquent" loans
    -- are still being paid (just behind), so they are grouped with
    -- "Current" rather than "Charged Off".
    case
        when l.status = 'paid_off' then 'Fully Paid'
        when l.status = 'defaulted' then 'Charged Off'
        else 'Current'
    end as loan_status,
    l.application_type,
    l.purpose,
    l.last_credit_pull_date,
    p.last_payment_date,
    coalesce(p.last_payment_date, l.origination_date) + interval '1 month' as next_payment_date,
    coalesce(p.total_payment, 0) as total_payment,
    -- Standard loan amortization formula (equal monthly installments),
    -- derived from principal / rate / term rather than randomly
    -- generated, so it is financially consistent with the loan.
    round(
        case
            when l.interest_rate is null or l.interest_rate = 0
                then l.principal_amount / l.term_months
            else
                l.principal_amount
                * (l.interest_rate / 100 / 12)
                * power(1 + l.interest_rate / 100 / 12, l.term_months)
                / (power(1 + l.interest_rate / 100 / 12, l.term_months) - 1)
        end::numeric,
        2
    ) as installment,
    l.dti,
    case
        when l.term_months <= 12 then 'short_term'
        when l.term_months <= 36 then 'medium_term'
        else 'long_term'
    end as term_bucket,
    -- Grade/sub_grade derived from the client's credit_score (not an
    -- independent random field), so they stay logically consistent with
    -- creditworthiness -- mirrors the grading logic of the bank_loan_data
    -- reference dataset.
    case
        when c.credit_score >= 750 then 'A'
        when c.credit_score >= 700 then 'B'
        when c.credit_score >= 650 then 'C'
        when c.credit_score >= 600 then 'D'
        when c.credit_score >= 550 then 'E'
        when c.credit_score >= 500 then 'F'
        else 'G'
    end as grade,
    case
        when c.credit_score >= 750 then 'A'
        when c.credit_score >= 700 then 'B'
        when c.credit_score >= 650 then 'C'
        when c.credit_score >= 600 then 'D'
        when c.credit_score >= 550 then 'E'
        when c.credit_score >= 500 then 'F'
        else 'G'
    end || (1 + mod(c.credit_score, 50) / 10)::text as sub_grade

from loans l
left join clients c on l.client_id = c.client_id
left join payments p on l.loan_id = p.loan_id
