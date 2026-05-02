CREATE TABLE users (
    id INT PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    username VARCHAR(100) UNIQUE,
    status VARCHAR(20),
    created_at TIMESTAMP
);

CREATE TABLE customers (
    id INT PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(30),
    loyalty_code INT UNIQUE,
    created_at TIMESTAMP
);

CREATE TABLE warehouses (
    id INT PRIMARY KEY,
    code INT UNIQUE,
    city VARCHAR(100)
);

CREATE TABLE products (
    id INT PRIMARY KEY,
    sku INT UNIQUE,
    name VARCHAR(255),
    price NUMERIC(10,2),
    category_code INT
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    user_email VARCHAR(255),
    customer_id INT,
    total NUMERIC(10,2),
    status VARCHAR(20),
    created_at TIMESTAMP,
    CONSTRAINT fk_orders_user_email
        FOREIGN KEY (user_email)
        REFERENCES users(email)
);

CREATE TABLE order_items (
    id INT PRIMARY KEY,
    order_id INT,
    product_id INT,
    product_sku INT,
    quantity INT,
    price NUMERIC(10,2),
    CONSTRAINT fk_items_order
        FOREIGN KEY (order_id)
        REFERENCES orders(id)
);

CREATE TABLE payments (
    id INT PRIMARY KEY,
    order_id INT,
    amount NUMERIC(10,2),
    status VARCHAR(20),
    CONSTRAINT fk_payments_order
        FOREIGN KEY (order_id)
        REFERENCES orders(id)
);

CREATE TABLE shipments (
    id INT PRIMARY KEY,
    order_id INT,
    warehouse_id INT,
    tracking_code VARCHAR(100),
    CONSTRAINT fk_shipments_order
        FOREIGN KEY (order_id)
        REFERENCES orders(id)
);

CREATE INDEX idx_orders_user_email
    ON orders(user_email);

CREATE INDEX idx_orders_status
    ON orders(status);

CREATE INDEX idx_items_product_sku
    ON order_items(product_sku);

CREATE INDEX idx_payments_order
    ON payments(order_id);

CREATE INDEX idx_shipments_warehouse
    ON shipments(warehouse_id);