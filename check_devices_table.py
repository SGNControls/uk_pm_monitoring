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

def check_devices_table():
    """Check what columns exist in the dust_devices table"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Check columns in dust_devices table
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'dust_devices'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()

        print("Columns in dust_devices table:")
        for col in columns:
            print(f"  {col[0]}: {col[1]} {'NULL' if col[2] == 'YES' else 'NOT NULL'} {col[3] or ''}")

        # Check if data_source_id exists
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'dust_devices' AND column_name = 'data_source_id'
        """)
        has_data_source_id = cur.fetchone() is not None
        print(f"\ndata_source_id column exists: {has_data_source_id}")

        # Check what devices exist
        cur.execute("SELECT id, deviceid, name, user_id FROM dust_devices LIMIT 5")
        devices = cur.fetchall()
        print(f"\nSample devices ({len(devices)} found):")
        for device in devices:
            print(f"  ID: {device[0]}, DeviceID: {device[1]}, Name: {device[2]}, UserID: {device[3]}")

    except Exception as e:
        print(f"Error checking devices table: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_devices_table()
