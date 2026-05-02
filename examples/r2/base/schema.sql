CREATE TABLE users (
    id INT PRIMARY KEY,
    code INT UNIQUE
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_code INT
);