#!/usr/bin/env python3
"""
Check for existing data for device_id 1225
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=int(os.getenv('DB_PORT', 5432))
    )

def check_device_data(device_id):
    """Check for existing data for a specific device"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        print(f"🔍 Checking data for device_id: {device_id}")
        print("=" * 50)

        # Check if device exists in dust_devices table
        print("1. Checking device registration...")
        cur.execute("SELECT * FROM dust_devices WHERE id = %s", (device_id,))
        device_info = cur.fetchone()

        if device_info:
            print(f"   ✅ Device found: {dict(device_info)}")
        else:
            print("   ❌ Device not found in dust_devices table")
            # Check if device exists with deviceid field
            cur.execute("SELECT * FROM dust_devices WHERE deviceid = %s", (str(device_id),))
            device_by_deviceid = cur.fetchone()
            if device_by_deviceid:
                print(f"   ✅ Device found by deviceid field: {dict(device_by_deviceid)}")
                device_id = device_by_deviceid['id']  # Use the actual ID
            else:
                print("   ❌ Device not found in dust_devices table")
                return

        # Check sensor data
        print(f"\n2. Checking sensor data in dust_sensor_data table...")
        cur.execute("""
            SELECT COUNT(*) as total_records,
                   MIN(timestamp) as earliest_record,
                   MAX(timestamp) as latest_record
            FROM dust_sensor_data
            WHERE device_id = %s
        """, (device_id,))
        sensor_stats = cur.fetchone()

        if sensor_stats['total_records'] > 0:
            print(f"   ✅ Found {sensor_stats['total_records']} sensor records")
            print(f"      Earliest: {sensor_stats['earliest_record']}")
            print(f"      Latest: {sensor_stats['latest_record']}")

            # Get a sample of recent data
            cur.execute("""
                SELECT timestamp, pm1, pm2_5, pm4, pm10, tsp
                FROM dust_sensor_data
                WHERE device_id = %s
                ORDER BY timestamp DESC
                LIMIT 5
            """, (device_id,))
            recent_data = cur.fetchall()

            print("      Recent records:")
            for record in recent_data:
                print(f"        {record['timestamp']}: PM1={record['pm1']}, PM2.5={record['pm2_5']}, PM10={record['pm10']}")
        else:
            print("   ❌ No sensor data found")

        # Check extended data
        print(f"\n3. Checking extended data in dust_extended_data table...")
        cur.execute("""
            SELECT COUNT(*) as total_records,
                   MIN(timestamp) as earliest_record,
                   MAX(timestamp) as latest_record
            FROM dust_extended_data
            WHERE device_id = %s
        """, (device_id,))
        extended_stats = cur.fetchone()

        if extended_stats['total_records'] > 0:
            print(f"   ✅ Found {extended_stats['total_records']} extended records")
            print(f"      Earliest: {extended_stats['earliest_record']}")
            print(f"      Latest: {extended_stats['latest_record']}")

            # Get a sample of recent extended data
            cur.execute("""
                SELECT timestamp, temperature_c, humidity_percent, voc_ppb, no2_ppb
                FROM dust_extended_data
                WHERE device_id = %s
                ORDER BY timestamp DESC
                LIMIT 3
            """, (device_id,))
            recent_extended = cur.fetchall()

            print("      Recent extended records:")
            for record in recent_extended:
                print(f"        {record['timestamp']}: Temp={record['temperature_c']}°C, Humidity={record['humidity_percent']}%, VOC={record['voc_ppb']}ppb")
        else:
            print("   ❌ No extended data found")

        # Check thresholds
        print(f"\n4. Checking thresholds in dust_thresholds table...")
        cur.execute("""
            SELECT pm1, pm2_5, pm4, pm10, tsp, timestamp
            FROM dust_thresholds
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        threshold_data = cur.fetchone()

        if threshold_data:
            print("   ✅ Thresholds found:")
            print(f"      PM1: {threshold_data['pm1']}, PM2.5: {threshold_data['pm2_5']}, PM10: {threshold_data['pm10']}")
            print(f"      Set at: {threshold_data['timestamp']}")
        else:
            print("   ❌ No thresholds found")
        print(f"\n5. Summary for device {device_id}:")
        total_sensor = sensor_stats['total_records'] if sensor_stats else 0
        total_extended = extended_stats['total_records'] if extended_stats else 0
        print(f"   - Sensor records: {total_sensor}")
        print(f"   - Extended records: {total_extended}")
        print(f"   - Total records: {total_sensor + total_extended}")

    except Exception as e:
        print(f"❌ Error checking device data: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    check_device_data(1225)
