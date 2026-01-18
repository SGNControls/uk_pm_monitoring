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

def update_schema():
    """Update database schema with new columns for environmental sensors"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        print("Adding new environmental sensor columns to dust_extended_data...")

        # Add new columns to dust_extended_data for lux, UV index, and battery
        cur.execute("""
            ALTER TABLE dust_extended_data
            ADD COLUMN IF NOT EXISTS lux DOUBLE PRECISION;
        """)
        print("✓ Added lux column")

        cur.execute("""
            ALTER TABLE dust_extended_data
            ADD COLUMN IF NOT EXISTS uv_index DOUBLE PRECISION;
        """)
        print("✓ Added uv_index column")

        cur.execute("""
            ALTER TABLE dust_extended_data
            ADD COLUMN IF NOT EXISTS battery_percent DOUBLE PRECISION;
        """)
        print("✓ Added battery_percent column")

        cur.execute("""
            ALTER TABLE dust_extended_data
            ADD COLUMN IF NOT EXISTS noise_db DOUBLE PRECISION;
        """)
        print("✓ Added noise_db column")

        conn.commit()
        print("✅ Schema update completed successfully!")

    except Exception as e:
        print(f"❌ Error updating schema: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def update_password_hash_column():
    """Update the password_hash column to accommodate longer hashes"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Check current column definition
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'dust_users' AND column_name = 'password_hash'
        """)
        result = cur.fetchone()
        print(f"Current password_hash column: {result}")

        # Alter the column to be longer
        cur.execute("ALTER TABLE dust_users ALTER COLUMN password_hash TYPE VARCHAR(512)")
        conn.commit()

        print("Password hash column updated to VARCHAR(512)")

        # Verify the change
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'dust_users' AND column_name = 'password_hash'
        """)
        result = cur.fetchone()
        print(f"Updated password_hash column: {result}")

    except Exception as e:
        print(f"Error updating schema: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    update_schema()
    update_password_hash_column()
