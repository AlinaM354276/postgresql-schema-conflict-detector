CREATE TABLE users (
    id INT PRIMARY KEY,
    email TEXT UNIQUE,
    username VARCHAR(100) UNIQUE,
    status VARCHAR(20),
    created_at TIMESTAMP
);

CREATE TABLE customers (
    id INT PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(30),
    mobile_phone VARCHAR(40),
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
    sku VARCHAR(50) UNIQUE,
    name VARCHAR(255),
    price NUMERIC(10,2),
    category_code INT,
    CONSTRAINT chk_price_positive
        CHECK (price > 0)
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
        REFERENCES users(email),
    CONSTRAINT fk_orders_customer_email
        FOREIGN KEY (user_email)
        REFERENCES customers(email)
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
        REFERENCES orders(id),
    CONSTRAINT fk_shipments_warehouse
        FOREIGN KEY (warehouse_id)
        REFERENCES warehouses(id)
);

CREATE TABLE audit_logs (
    id INT PRIMARY KEY,
    message TEXT,
    actor_id INT,
    created_at TIMESTAMP
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

CREATE INDEX idx_audit_logs_actor
    ON audit_logs(actor_id);