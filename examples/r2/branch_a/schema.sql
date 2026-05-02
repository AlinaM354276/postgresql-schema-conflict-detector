CREATE TABLE users (
    id INT PRIMARY KEY,
    code VARCHAR(50) UNIQUE
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_code INT
);