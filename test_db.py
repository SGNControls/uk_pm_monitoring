#!/usr/bin/env python3
import os
import sys
sys.path.append('.')

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

def test_database():
    try:
        # Database connection
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT')
        )

        cur = conn.cursor(cursor_factory=RealDictCursor)

        print("=== TESTING DATABASE CONNECTION ===")

        # Check devices
        print('\n=== DEVICES ===')
        cur.execute('SELECT id, deviceid, name, has_relay FROM dust_devices')
        devices = cur.fetchall()
        for device in devices:
            print(f'ID: {device["id"]}, DeviceID: {device["deviceid"]}, Name: {device["name"]}, Relay: {device["has_relay"]}')

        # Check latest sensor data
        print('\n=== LATEST SENSOR DATA ===')
        cur.execute('SELECT device_id, pm2_5, timestamp FROM dust_sensor_data ORDER BY timestamp DESC LIMIT 3')
        sensor_data = cur.fetchall()
        for row in sensor_data:
            print(f'Device: {row["device_id"]}, PM2.5: {row["pm2_5"]}, Timestamp: {row["timestamp"]}')

        # Check latest extended data
        print('\n=== LATEST EXTENDED DATA ===')
        try:
            cur.execute('SELECT COUNT(*) as count FROM dust_extended_data')
            count_result = cur.fetchone()
            count = count_result['count']
            print(f'Extended data records: {count}')

            if count > 0:
                cur.execute('SELECT device_id, temperature_c, humidity_percent, pressure_hpa, voc_ppb, lux, uv_index, timestamp FROM dust_extended_data ORDER BY timestamp DESC LIMIT 3')
                extended_data = cur.fetchall()
                for row in extended_data:
                    print(f'Device {row["device_id"]}: Temp={row["temperature_c"]}, Humidity={row["humidity_percent"]}, Pressure={row["pressure_hpa"]}, VOC={row["voc_ppb"]}, Lux={row["lux"]}, UV={row["uv_index"]}, Time={row["timestamp"]}')
            else:
                print("No extended data found in database")
        except Exception as e:
            print(f"Error checking extended data: {e}")

        conn.close()
        print("\n=== DATABASE TEST COMPLETE ===")

    except Exception as e:
        print(f"Database connection error: {e}")

if __name__ == "__main__":
    test_database()
