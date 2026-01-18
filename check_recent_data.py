#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT')
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Check recent data
    cur.execute("SELECT COUNT(*) as count FROM dust_sensor_data WHERE timestamp > NOW() - INTERVAL '1 hour'")
    sensor_count = cur.fetchone()['count']

    cur.execute("SELECT COUNT(*) as count FROM dust_extended_data WHERE timestamp > NOW() - INTERVAL '1 hour'")
    extended_count = cur.fetchone()['count']

    print(f"Recent sensor data (1h): {sensor_count} records")
    print(f"Recent extended data (1h): {extended_count} records")

    # Check latest entries
    cur.execute("SELECT device_id, timestamp FROM dust_sensor_data ORDER BY timestamp DESC LIMIT 3")
    latest_sensor = cur.fetchall()

    cur.execute("SELECT device_id, timestamp FROM dust_extended_data ORDER BY timestamp DESC LIMIT 3")
    latest_extended = cur.fetchall()

    print("\nLatest sensor data:")
    for row in latest_sensor:
        print(f"  Device {row['device_id']}: {row['timestamp']}")

    print("\nLatest extended data:")
    for row in latest_extended:
        print(f"  Device {row['device_id']}: {row['timestamp']}")

except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
