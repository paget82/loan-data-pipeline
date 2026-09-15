with loans as (

    select * from {{ ref('stg_loans') }}

)

select
    loan_id,
    client_id,
    principal_amount,
    interest_rate,
    is_interest_rate_missing,
    origination_date,
    term_months,
    status,
    case
        when term_months <= 12 then 'short_term'
        when term_months <= 36 then 'medium_term'
        else 'long_term'
    end as term_bucket

from loans
