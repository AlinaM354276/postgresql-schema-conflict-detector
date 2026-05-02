CREATE TABLE customers (
    id INT PRIMARY KEY
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_id)
        REFERENCES customers(id)
);