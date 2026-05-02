CREATE TABLE products (
    id INT PRIMARY KEY,
    price INT,
    CONSTRAINT chk_price_positive
        CHECK (price > 0)
);
