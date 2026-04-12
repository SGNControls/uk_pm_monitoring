-- Adds columns that app.py already reads/writes but schema.sql does not yet define
ALTER TABLE dust_extended_data
    ADD COLUMN IF NOT EXISTS lux DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS uv_index DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS battery_percent DOUBLE PRECISION;

-- Helpful index for latest location and extended telemetry lookups
CREATE INDEX IF NOT EXISTS idx_extended_data_device_latest
    ON dust_extended_data(device_id, timestamp DESC);
