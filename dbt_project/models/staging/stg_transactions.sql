with source as (

    select * from {{ source('raw', 'transactions') }}

),

deduplicated as (

    -- remove duplicate transactions (same loan_id, date, amount, type)
    select distinct on (loan_id, transaction_date, amount, transaction_type)
        transaction_id,
        loan_id,
        transaction_date::date as transaction_date,
        amount,
        transaction_type
    from source

)

select * from deduplicated
