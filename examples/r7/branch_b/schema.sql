CREATE TABLE products (
    id INT PRIMARY KEY,
    price INT,
    CONSTRAINT chk_price_nonpositive
        CHECK (price <= 0)
);