CREATE TABLE authors (
    id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE books (
    id INT PRIMARY KEY,
    author_id INT,
    title VARCHAR(255) NOT NULL,
    publisher_id INT,
    FOREIGN KEY (author_id) REFERENCES authors(id)
);

CREATE TABLE publishers (
    id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);