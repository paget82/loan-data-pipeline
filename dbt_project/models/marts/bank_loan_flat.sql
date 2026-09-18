with loans as (

    select * from {{ ref('dim_loan') }}

),

clients as (

    select * from {{ ref('dim_client') }}

),

-- Per-loan aggregates computed from the actual transaction history,
-- rather than stored as independent random fields, so they stay
-- internally consistent with the rest of the pipeline.
transaction_agg as (

    select
        loan_id,
        sum(amount)         as total_payment,
        max(transaction_date) as last_payment_date

    from {{ ref('fact_transactions') }}
    group by loan_id

),

joined as (

    select
        l.loan_id                          as id,
        c.address_state,
        l.application_type,
        c.emp_length,
        c.emp_title,
        l.grade,
        c.home_ownership,
        l.origination_date                 as issue_date,
        l.last_credit_pull_date,
        ta.last_payment_date,
        -- Simplified to the three statuses used by the reference dataset.
        -- "delinquent" loans are still being paid (just behind), so they
        -- are grouped with "Current" rather than "Charged Off".
        case
            when l.status = 'paid_off' then 'Fully Paid'
            when l.status = 'defaulted' then 'Charged Off'
            else 'Current'
        end                                 as loan_status,
        coalesce(ta.last_payment_date, l.origination_date) + interval '1 month'
                                            as next_payment_date,
        l.client_id                        as member_id,
        l.purpose,
        l.sub_grade,
        l.term_months || ' months'         as term,
        c.verification_status,
        round((c.monthly_income * 12)::numeric, 2)
                                            as annual_income,
        l.dti,
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
        )                                   as installment,
        round((l.interest_rate / 100)::numeric, 4)
                                            as int_rate,
        l.principal_amount                 as loan_amount,
        c.total_acc,
        coalesce(ta.total_payment, 0)       as total_payment

    from loans l
    left join clients c on l.client_id = c.client_id
    left join transaction_agg ta on l.loan_id = ta.loan_id

)

select * from joined
