with source as (

    select * from {{ source('raw', 'exchange_rates') }}

),

cleaned as (

    select
        valid_for::date as valid_for,
        currency_code,
        -- units of currency per 1 USD, as returned directly by the
        -- Frankfurter API (base currency = USD)
        rate_per_usd

    from source

)

select * from cleaned
