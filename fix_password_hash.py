#!/usr/bin/env python3
import os
from werkzeug.security import generate_password_hash
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

def update_admin_password():
    """Update the admin user's password hash to use current werkzeug format"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Get current admin user
        cur.execute("SELECT id, username, password_hash FROM dust_users WHERE username = 'admin'")
        user = cur.fetchone()

        if not user:
            print("Admin user not found!")
            return

        user_id, username, old_hash = user
        print(f"Found admin user: {username}")
        print(f"Old hash: {old_hash}")

        # Generate new hash for default password "admin"
        # Since we don't know the original password, we'll set it to "admin"
        new_hash = generate_password_hash("admin")
        print(f"New hash: {new_hash}")

        # Update the password hash
        cur.execute(
            "UPDATE dust_users SET password_hash = %s WHERE id = %s",
            (new_hash, user_id)
        )
        conn.commit()

        print("Admin password hash updated successfully!")
        print("Default login credentials: username='admin', password='admin'")

    except Exception as e:
        print(f"Error updating password hash: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    update_admin_password()
