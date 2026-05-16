CREATE TABLE authors (
    id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    country VARCHAR(100)
);

CREATE TABLE books (
    id INT PRIMARY KEY,
    author_id INT,
    title VARCHAR(255) NOT NULL,
    FOREIGN KEY (author_id) REFERENCES authors(id)
);