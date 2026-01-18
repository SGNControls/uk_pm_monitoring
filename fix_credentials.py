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

def update_credentials():
    try:
        # You'll need to replace these with your actual MQTT broker credentials
        username = input("Enter your MQTT broker username: ").strip()
        password = input("Enter your MQTT broker password: ").strip()

        if not username or not password:
            print("Username and password cannot be empty!")
            return

        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        print(f"Updating data source with username: {username}")
        print(f"Updating data source with password: {'*' * len(password)}")

        cur.execute("""
            UPDATE dust_data_sources
            SET username = %s, password = %s
            WHERE id = 6
        """, (username, password))

        conn.commit()
        print("Credentials updated successfully!")

        # Verify the update
        cur.execute("SELECT id, broker_url, username, password, description FROM dust_data_sources WHERE id = 6")
        updated = cur.fetchone()
        print(f"Updated data source ID {updated[0]}:")
        print(f"  Broker URL: {updated[1]}")
        print(f"  Username: {updated[2]}")
        print(f"  Password: {'*' * len(updated[3]) if updated[3] else 'None'}")
        print(f"  Description: {updated[4]}")

    except Exception as e:
        print(f"Error: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

def show_credentials():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT * FROM dust_data_sources WHERE id = 6")
        ds = cur.fetchone()

        print("Current credentials for data source ID 6:")
        print(f"Username: '{ds['username']}'")
        print(f"Password: '{ds['password']}'")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("Current credentials:")
    show_credentials()

    print("\nTo fix the credentials, replace the username and password in this script")
    print("Then uncomment the update_credentials() call below")

    # Uncomment the line below to update credentials
    update_credentials()
