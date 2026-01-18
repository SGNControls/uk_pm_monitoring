#!/usr/bin/env python3
"""
Script to fix device setup and ensure UK_001 is properly associated with a data source
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    "host": os.getenv('DB_HOST', 'localhost'),
    "database": os.getenv('DB_NAME', 'pm_monitoring'),
    "user": os.getenv('DB_USER', 'postgres'),
    "password": os.getenv('DB_PASSWORD', 'password'),
    "port": os.getenv('DB_PORT', '5432')
}

def get_db_connection():
    """Get database connection"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)

def fix_device_setup():
    """Fix the device setup for UK_001"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("Checking current device setup...")
        
        # Check if UK_001 exists
        cur.execute("SELECT * FROM dust_devices WHERE deviceid = 'UK_001'")
        device = cur.fetchone()
        
        if not device:
            print("Device UK_001 not found!")
            return
        
        print(f"Found device UK_001 with ID: {device['id']}")
        print(f"Current data_source_id: {device['data_source_id']}")
        
        # Check if data source exists
        if device['data_source_id']:
            cur.execute("SELECT * FROM dust_data_sources WHERE id = %s", (device['data_source_id'],))
            data_source = cur.fetchone()
            if data_source:
                print(f"Data source found: {data_source}")
            else:
                print("Data source not found!")
        else:
            print("No data source associated with device!")
        
        # Check if we need to create a data source
        cur.execute("SELECT COUNT(*) as count FROM dust_data_sources")
        source_count = cur.fetchone()['count']
        
        if source_count == 0:
            print("No data sources found. Creating a default MQTT data source...")
            
            # Create a default MQTT data source
            cur.execute("""
                INSERT INTO dust_data_sources (source_type, broker_url, description)
                VALUES ('mqtt', 'mqtt.example.com', 'Default MQTT Broker')
                RETURNING id
            """)
            data_source_id = cur.fetchone()[0]
            conn.commit()
            print(f"Created data source with ID: {data_source_id}")
            
            # Update the device to use this data source
            cur.execute("""
                UPDATE dust_devices 
                SET data_source_id = %s 
                WHERE deviceid = 'UK_001'
            """, (data_source_id,))
            conn.commit()
            print("Updated device to use new data source")
        
        # Check if device has a user_id
        if not device['user_id']:
            print("Device has no user_id. Setting to admin user...")
            
            # Get admin user
            cur.execute("SELECT id FROM dust_users WHERE is_admin = true LIMIT 1")
            admin_user = cur.fetchone()
            
            if admin_user:
                cur.execute("""
                    UPDATE dust_devices 
                    SET user_id = %s 
                    WHERE deviceid = 'UK_001'
                """, (admin_user['id'],))
                conn.commit()
                print(f"Updated device user_id to: {admin_user['id']}")
            else:
                print("No admin user found!")
        
        # Verify the fix
        cur.execute("SELECT * FROM dust_devices WHERE deviceid = 'UK_001'")
        updated_device = cur.fetchone()
        print(f"\nUpdated device info:")
        print(f"ID: {updated_device['id']}")
        print(f"Device ID: {updated_device['deviceid']}")
        print(f"Name: {updated_device['name']}")
        print(f"User ID: {updated_device['user_id']}")
        print(f"Data Source ID: {updated_device['data_source_id']}")
        print(f"Has Relay: {updated_device['has_relay']}")
        
        # Check if there's any sensor data
        cur.execute("SELECT COUNT(*) as count FROM dust_sensor_data WHERE device_id = %s", (updated_device['id'],))
        sensor_count = cur.fetchone()['count']
        print(f"Number of sensor data records: {sensor_count}")
        
        if sensor_count == 0:
            print("No sensor data found. This is expected if MQTT is not connected.")
        
        print("\nDevice setup fix completed!")
        
    except Exception as e:
        print(f"Error fixing device setup: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    fix_device_setup()

