with source as (

    select * from {{ source('raw', 'loans') }}

),

cleaned as (

    select
        loan_id,
        client_id,
        principal_amount,
        -- flag a missing interest rate instead of silently replacing it
        interest_rate,
        (interest_rate is null)     as is_interest_rate_missing,
        origination_date::date              as origination_date,
        term_months,
        status,
        application_type,
        purpose,
        last_credit_pull_date::date         as last_credit_pull_date,
        dti

    from source
    where principal_amount > 0  -- basic sanity check

)

select * from cleaned
