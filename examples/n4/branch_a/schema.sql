CREATE TABLE users (
    id INT PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);

CREATE TABLE order_statuses (
    id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    status_id INT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (status_id) REFERENCES order_statuses(id)
);