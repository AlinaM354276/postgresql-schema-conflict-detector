CREATE TABLE users (
    id INT PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);

CREATE TABLE payment_methods (
    id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    payment_method_id INT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id)
);