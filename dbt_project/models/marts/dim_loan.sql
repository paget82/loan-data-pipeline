with loans as (

    select * from {{ ref('stg_loans') }}

),

clients as (

    select client_id, credit_score from {{ ref('dim_client') }}

)

select
    l.loan_id,
    l.client_id,
    l.principal_amount,
    -- converted using the latest EUR fixing from the CNB REST API
    -- (scalar subquery, not a join, so a missing/failed API pull never
    -- drops loan rows -- it just yields a null conversion for that run)
    round(
        (l.principal_amount::numeric / nullif(
            (select czk_per_unit from {{ ref('dim_exchange_rate') }} where currency_code = 'EUR' limit 1),
            0
        )),
        2
    ) as principal_amount_eur,
    l.interest_rate,
    l.is_interest_rate_missing,
    l.origination_date,
    l.term_months,
    l.status,
    l.application_type,
    l.purpose,
    l.last_credit_pull_date,
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
