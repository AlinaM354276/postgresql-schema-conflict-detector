CREATE TABLE users (
    id INT PRIMARY KEY,
    email VARCHAR(255)
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    CONSTRAINT fk_orders_user_email
        FOREIGN KEY (user_id)
        REFERENCES users(email)
);