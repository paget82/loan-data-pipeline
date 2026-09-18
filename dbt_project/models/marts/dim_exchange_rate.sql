with rates as (

    select * from {{ ref('stg_exchange_rates') }}

)

select
    valid_for,
    country,
    currency,
    currency_code,
    czk_per_unit

from rates
