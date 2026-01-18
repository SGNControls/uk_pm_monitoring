#!/usr/bin/env python3
"""
Debug MQTT clients in Flask application
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

def check_mqtt_initialization():
    """Check if MQTT clients should be initialized"""
    print("🔍 Checking Flask MQTT Client Initialization...")
    print("=" * 60)

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check data sources
        print("1. Checking data sources configuration:")
        cur.execute("SELECT * FROM dust_data_sources WHERE source_type = 'mqtt'")
        data_sources = cur.fetchall()

        if not data_sources:
            print("   ❌ No MQTT data sources found!")
            return

        for ds in data_sources:
            print(f"   📡 Data Source {ds['id']}: {ds['broker_url']}")
            print(f"      Username: {ds['username']}")
            print(f"      Password: {'*' * len(ds['password']) if ds['password'] else 'N/A'}")

        # Check devices
        print("\n2. Checking device to data source mapping:")
        cur.execute("""
            SELECT d.id, d.deviceid, d.name, ds.broker_url, ds.username
            FROM dust_devices d
            JOIN dust_data_sources ds ON d.data_source_id = ds.id
            WHERE ds.source_type = 'mqtt'
        """)
        devices = cur.fetchall()

        if not devices:
            print("   ❌ No devices associated with MQTT data sources!")
            return

        for device in devices:
            print(f"   📱 Device {device['deviceid']} (ID: {device['id']}) → {device['broker_url']}")
            if device['deviceid'] == '1225':
                print("      🎯 This is device 1225!")
                hivemq_broker = "461dec45331a4366882762ab7221c726.s1.eu.hivemq.cloud"
                if hivemq_broker in device['broker_url']:
                    print("      ✅ Correct HiveMQ broker configured")
                else:
                    print(f"      ❌ Wrong broker! Should be: {hivemq_broker}")

        # Check if data is being received
        print("\n3. Checking recent data reception:")
        cur.execute("""
            SELECT device_id, COUNT(*) as records, MAX(timestamp) as latest
            FROM dust_sensor_data
            WHERE timestamp >= NOW() - INTERVAL '1 hour'
            GROUP BY device_id
        """)
        recent_data = cur.fetchall()

        if recent_data:
            print("   📊 Recent data (last hour):")
            for record in recent_data:
                print(f"      Device {record['device_id']}: {record['records']} records, latest: {record['latest']}")
        else:
            print("   ❌ No data received in the last hour!")
        # Check extended data
        cur.execute("""
            SELECT device_id, COUNT(*) as records, MAX(timestamp) as latest
            FROM dust_extended_data
            WHERE timestamp >= NOW() - INTERVAL '1 hour'
            GROUP BY device_id
        """)
        recent_extended = cur.fetchall()

        if recent_extended:
            print("   📊 Recent extended data (last hour):")
            for record in recent_extended:
                print(f"      Device {record['device_id']}: {record['records']} records, latest: {record['latest']}")

    except Exception as e:
        print(f"❌ Error checking MQTT initialization: {e}")
    finally:
        if conn:
            conn.close()

def check_railway_environment():
    """Check Railway environment variables"""
    print("\n4. Checking Railway environment:")
    railway_env = os.getenv('RAILWAY_ENVIRONMENT')
    if railway_env:
        print(f"   ✅ Running in Railway environment: {railway_env}")
    else:
        print("   ⚠️ Not running in Railway environment")

    port = os.getenv('PORT')
    if port:
        print(f"   ✅ PORT environment variable set: {port}")
    else:
        print("   ⚠️ PORT environment variable not set")

    database_url = os.getenv('DATABASE_URL')
    if database_url:
        print("   ✅ DATABASE_URL environment variable set")
    else:
        print("   ❌ DATABASE_URL environment variable not set")

if __name__ == '__main__':
    check_mqtt_initialization()
    check_railway_environment()

    print("\n🔧 Troubleshooting Steps:")
    print("1. Check Railway logs for MQTT connection messages")
    print("2. Verify the correct password is stored in data_source_id=6")
    print("3. Ensure Flask app has internet access to HiveMQ broker")
    print("4. Check if MQTT client threads are starting properly")
    print("5. Verify TLS/SSL configuration for HiveMQ connection")
