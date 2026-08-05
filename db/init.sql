CREATE TABLE IF NOT EXISTS dt (
    dt_id VARCHAR(50) PRIMARY KEY,
    feeder_id VARCHAR(50) NOT NULL,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS pole (
    pole_id VARCHAR(50) PRIMARY KEY,
    dt_id VARCHAR(50) REFERENCES dt(dt_id),
    parent_pole_id VARCHAR(50),
    seq_on_line INT,
    device_id VARCHAR(50),
    has_device BOOLEAN DEFAULT TRUE,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    pincode VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS ticket (
    id SERIAL PRIMARY KEY,
    dt_id VARCHAR(50) REFERENCES dt(dt_id),
    status VARCHAR(50) DEFAULT 'detected',
    fault_boundary JSONB,
    confidence VARCHAR(20),
    affected_poles_count INT,
    is_geometric_inference BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);
