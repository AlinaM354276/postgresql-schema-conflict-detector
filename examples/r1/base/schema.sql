CREATE TABLE users (
    id INT PRIMARY KEY,
    email VARCHAR(255)
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT
);