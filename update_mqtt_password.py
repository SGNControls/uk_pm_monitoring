#!/usr/bin/env python3
"""
Update MQTT password in database for data_source_id=6
"""

import os
import psycopg2
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

def update_mqtt_password():
    """Update the MQTT password for data_source_id=6"""
    correct_password = "24csnE%<MLVSQ#6d9!zb"

    print("🔄 Updating MQTT password for data_source_id=6...")
    print(f"   New password: {correct_password}")

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Update the password
        cur.execute("""
            UPDATE dust_data_sources
            SET password = %s
            WHERE id = 6 AND source_type = 'mqtt'
        """, (correct_password,))

        # Check if update was successful
        if cur.rowcount > 0:
            print("✅ Password updated successfully!")
            conn.commit()

            # Verify the update
            cur.execute("SELECT id, broker_url, username, password FROM dust_data_sources WHERE id = 6")
            result = cur.fetchone()
            if result:
                print(f"   📡 Data Source {result[0]}: {result[1]}")
                print(f"      Username: {result[2]}")
                print(f"      Password: {'*' * len(result[3])} (length: {len(result[3])})")
                print("   ✅ Password verification complete")

        else:
            print("❌ No rows updated - data source 6 not found")

    except Exception as e:
        print(f"❌ Error updating password: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    print("\n📋 Next Steps:")
    print("1. Redeploy your Railway application")
    print("2. Check Railway logs for MQTT connection messages")
    print("3. Device 1225 data should start flowing to the dashboard")

if __name__ == '__main__':
    update_mqtt_password()
