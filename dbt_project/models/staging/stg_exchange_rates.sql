with source as (

    select * from {{ source('raw', 'exchange_rates') }}

),

cleaned as (

    select
        valid_for::date as valid_for,
        country,
        currency,
        currency_code,
        amount,
        rate,
        -- normalize to "CZK per 1 unit of currency" -- some currencies
        -- (e.g. JPY, HUF) are fixed per 100 or 1000 units, not per 1
        round((rate / amount)::numeric, 4) as czk_per_unit

    from source

)

select * from cleaned
