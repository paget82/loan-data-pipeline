with rates as (

    select * from {{ ref('stg_exchange_rates') }}

)

select
    valid_for,
    currency_code,
    rate_per_usd

from rates
