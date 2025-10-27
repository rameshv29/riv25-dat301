-- Workshop table creation

CREATE TABLE sales_data (
    sale_id     bigint,
    product_id  bigint,
    customer_id bigint,
    sale_amount numeric(12,2),
    sale_date   date
);


INSERT INTO sales_data (sale_id, product_id, customer_id, sale_amount, sale_date)
SELECT 
    generate_series(1, 5000000) as sale_id,
    floor(random() * 1000 + 1)::bigint as product_id,
    floor(random() * 10000 + 1)::bigint as customer_id,
    round((random() * 1000)::numeric, 2) as sale_amount,
    (timestamp '2020-01-01' + 
        (random() * (timestamp '2025-11-30' - timestamp '2020-01-01'))::interval)::date as sale_date
;

-- Create indexes
CREATE INDEX sales_data_sale_date_idx ON sales_data (sale_date);
CREATE INDEX sales_data_sale_id_idx ON sales_data (sale_id);

