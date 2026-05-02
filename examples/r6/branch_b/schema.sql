CREATE TABLE users (
    id INT PRIMARY KEY,
    email VARCHAR(255) UNIQUE
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_email VARCHAR(255),
    CONSTRAINT fk_orders_user_email
        FOREIGN KEY (user_email)
        REFERENCES users(email)
);

CREATE INDEX idx_orders_user_email
    ON orders(user_email, id);