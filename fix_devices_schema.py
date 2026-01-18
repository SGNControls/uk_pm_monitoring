#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import psycopg2

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    "host": os.getenv('DB_HOST'),
    "database": os.getenv('DB_NAME'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "port": os.getenv('DB_PORT')
}

def fix_devices_table():
    """Add missing data_source_id column to dust_devices table"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # First check if dust_data_sources table exists
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'dust_data_sources'
        """)
        data_sources_exists = cur.fetchone() is not None

        if not data_sources_exists:
            print("Creating dust_data_sources table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dust_data_sources (
                    id SERIAL PRIMARY KEY,
                    source_type VARCHAR(10) NOT NULL CHECK (source_type IN ('mqtt', 'api')),
                    broker_url TEXT,
                    api_device_id TEXT,
                    username TEXT,
                    password TEXT,
                    description TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (source_type, broker_url, api_device_id)
                )
            """)
            print("dust_data_sources table created")

        # Add data_source_id column to dust_devices if it doesn't exist
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'dust_devices' AND column_name = 'data_source_id'
        """)
        column_exists = cur.fetchone() is not None

        if not column_exists:
            print("Adding data_source_id column to dust_devices...")
            cur.execute("""
                ALTER TABLE dust_devices
                ADD COLUMN data_source_id INTEGER REFERENCES dust_data_sources(id) ON DELETE CASCADE
            """)
            print("data_source_id column added")

            # Create a default data source for existing devices
            cur.execute("""
                INSERT INTO dust_data_sources (source_type, description)
                VALUES ('mqtt', 'Default MQTT data source')
                ON CONFLICT DO NOTHING
            """)

            # Get the default data source ID
            cur.execute("""
                SELECT id FROM dust_data_sources
                WHERE source_type = 'mqtt' AND description = 'Default MQTT data source'
                LIMIT 1
            """)
            default_source = cur.fetchone()

            if default_source:
                # Update existing devices to use the default data source
                cur.execute("""
                    UPDATE dust_devices
                    SET data_source_id = %s
                    WHERE data_source_id IS NULL
                """, (default_source[0],))
                print(f"Updated existing devices to use default data source (ID: {default_source[0]})")

        # Make data_source_id NOT NULL if it's still nullable
        cur.execute("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'dust_devices' AND column_name = 'data_source_id'
        """)
        result = cur.fetchone()
        is_nullable = result[0] if result else None

        if is_nullable == 'YES':
            # First ensure all devices have a data_source_id
            cur.execute("""
                SELECT COUNT(*) FROM dust_devices WHERE data_source_id IS NULL
            """)
            null_count = cur.fetchone()[0]

            if null_count > 0:
                print(f"Warning: {null_count} devices still have NULL data_source_id")

            # Make the column NOT NULL
            cur.execute("""
                ALTER TABLE dust_devices
                ALTER COLUMN data_source_id SET NOT NULL
            """)
            print("data_source_id column set to NOT NULL")

        conn.commit()
        print("Schema fix completed successfully!")

    except Exception as e:
        print(f"Error fixing schema: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    fix_devices_table()
