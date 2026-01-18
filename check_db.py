#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv('DB_HOST'),
    "database": os.getenv('DB_NAME'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "port": os.getenv('DB_PORT')
}

def check_data_sources():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check all data sources
        cur.execute("SELECT * FROM dust_data_sources ORDER BY id")
        data_sources = cur.fetchall()

        print("=== DATA SOURCES ===")
        for ds in data_sources:
            print(f"ID: {ds['id']}")
            print(f"Type: {ds['source_type']}")
            print(f"Broker URL: {ds['broker_url']}")
            print(f"Username: '{ds['username']}'")
            print(f"Password: '{ds['password']}'")
            print(f"Description: {ds['description']}")
            print("---")

        # Check if there are any devices
        cur.execute("SELECT d.*, ds.broker_url, ds.username, ds.password FROM dust_devices d JOIN dust_data_sources ds ON d.data_source_id = ds.id")
        devices = cur.fetchall()

        print("=== DEVICES ===")
        for device in devices:
            print(f"Device ID: {device['deviceid']}")
            print(f"Data Source ID: {device['data_source_id']}")
            print(f"Broker URL: {device['broker_url']}")
            print(f"Username: '{device['username']}'")
            print(f"Password: '{device['password']}'")
            print("---")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_data_sources()
