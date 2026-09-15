with source as (

    select * from {{ source('raw', 'clients') }}

),

deduplicated as (

    select distinct on (client_id) *
    from source

),

cleaned as (

    select
        client_id,
        trim(full_name)                            as full_name,
        birth_date,
        trim(city)                                  as city,
        -- replace missing income with the median instead of dropping the row
        coalesce(monthly_income, median_income.med) as monthly_income,
        credit_score,
        signup_date

    from deduplicated
    cross join (
        select percentile_cont(0.5) within group (order by monthly_income) as med
        from deduplicated
        where monthly_income is not null
    ) as median_income

)

select * from cleaned
