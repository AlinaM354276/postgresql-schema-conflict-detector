CREATE TABLE users (
    id INT PRIMARY KEY,
    code INT UNIQUE
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_code INT,
    CONSTRAINT fk_orders_user_code
        FOREIGN KEY (user_code)
        REFERENCES users(code)
);