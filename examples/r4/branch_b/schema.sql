CREATE TABLE users (
    id INT PRIMARY KEY
);

CREATE TABLE logs (
    id INT PRIMARY KEY,
    event_type VARCHAR(100),
    created_at TIMESTAMP
);