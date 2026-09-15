with transactions as (

    select * from {{ ref('stg_transactions') }}

),

loans as (

    select loan_id, client_id from {{ ref('dim_loan') }}

)

select
    t.transaction_id,
    t.loan_id,
    l.client_id,
    t.transaction_date,
    t.amount,
    t.transaction_type

from transactions t
left join loans l on t.loan_id = l.loan_id
