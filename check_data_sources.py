#!/usr/bin/env python3
"""
Check all MQTT data sources in the database
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

def check_data_sources():
    """Check all data sources"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        print("🔍 Checking all data sources...")
        print("=" * 60)

        # Check all data sources
        cur.execute("SELECT * FROM dust_data_sources ORDER BY id")
        data_sources = cur.fetchall()

        if not data_sources:
            print("❌ No data sources found!")
            return

        print(f"📋 Found {len(data_sources)} data sources:\n")

        hivemq_broker = "461dec45331a4366882762ab7221c726.s1.eu.hivemq.cloud"

        for ds in data_sources:
            print(f"🔹 Data Source ID: {ds['id']}")
            print(f"   Type: {ds['source_type']}")
            print(f"   Description: {ds.get('description', 'N/A')}")

            if ds['source_type'] == 'mqtt':
                print(f"   Broker URL: {ds['broker_url']}")
                print(f"   Username: {ds['username']}")
                print(f"   Password: {'*' * len(ds['password']) if ds['password'] else 'N/A'}")

                # Check if this matches device 1225's broker
                if ds['broker_url'] == hivemq_broker:
                    print("   ✅ MATCHES device 1225's HiveMQ broker!")
                else:
                    print("   ❌ Does NOT match device 1225's broker")
                    print(f"      Device 1225 uses: {hivemq_broker}")
            elif ds['source_type'] == 'api':
                print(f"   API Device ID: {ds.get('api_device_id', 'N/A')}")

            print()

        # Check which devices use which data sources
        print("🔗 Device to Data Source Mapping:")
        print("-" * 40)
        cur.execute("""
            SELECT d.id, d.deviceid, d.name, d.data_source_id, ds.broker_url
            FROM dust_devices d
            JOIN dust_data_sources ds ON d.data_source_id = ds.id
            ORDER BY d.id
        """)
        device_mapping = cur.fetchall()

        for device in device_mapping:
            print(f"Device {device['deviceid']} (ID: {device['id']}) → Data Source {device['data_source_id']}")
            if device['deviceid'] == '1225':
                print(f"   🎯 This is device 1225! Uses: {device['broker_url']}")
                if device['broker_url'] == hivemq_broker:
                    print("   ✅ Correct broker for device 1225")
                else:
                    print("   ❌ Wrong broker for device 1225")
                    print(f"      Should be: {hivemq_broker}")
            print()

    except Exception as e:
        print(f"❌ Error checking data sources: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    check_data_sources()
