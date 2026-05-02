CREATE TABLE users (
    id INT PRIMARY KEY
);

CREATE TABLE products (
    id INT PRIMARY KEY
);

CREATE TABLE warehouses (
    id INT PRIMARY KEY
);

CREATE TABLE inventory_movements (
    id BIGINT PRIMARY KEY,
    user_id INT,
    product_id INT,
    warehouse_id INT,

    CONSTRAINT fk_inventory_user
        FOREIGN KEY (user_id)
        REFERENCES users(id),

    CONSTRAINT fk_inventory_product
        FOREIGN KEY (product_id)
        REFERENCES products(id)
);