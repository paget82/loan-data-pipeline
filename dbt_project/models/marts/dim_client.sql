with clients as (

    select * from {{ ref('stg_clients') }}

)

select
    client_id,
    full_name,
    birth_date,
    date_part('year', age(current_date, birth_date))::int as age,
    city,
    monthly_income,
    round((monthly_income * 12)::numeric, 2) as annual_income,
    credit_score,
    signup_date,
    address_state,
    emp_length,
    emp_title,
    home_ownership,
    verification_status,
    total_acc,
    case
        when credit_score >= 750 then 'excellent'
        when credit_score >= 650 then 'good'
        when credit_score >= 550 then 'fair'
        else 'poor'
    end as credit_tier

from clients
