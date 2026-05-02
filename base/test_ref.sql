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
    created_by INT,
    approved_by INT,
    product_id INT,
    source_warehouse_id INT,
    target_warehouse_id INT,

    CONSTRAINT fk_inventory_created_by
        FOREIGN KEY (created_by)
        REFERENCES users(id),

    CONSTRAINT fk_inventory_approved_by
        FOREIGN KEY (approved_by)
        REFERENCES users(id),

    CONSTRAINT fk_inventory_product
        FOREIGN KEY (product_id)
        REFERENCES products(id),

    CONSTRAINT fk_inventory_source_warehouse
        FOREIGN KEY (source_warehouse_id)
        REFERENCES warehouses(id),

    CONSTRAINT fk_inventory_target_warehouse
        FOREIGN KEY (target_warehouse_id)
        REFERENCES warehouses(id)
);