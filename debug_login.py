#!/usr/bin/env python3
import os
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

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

def test_password_checking():
    """Test password checking with existing hashes"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get all users
        cur.execute("SELECT id, username, email, password_hash FROM dust_users")
        users = cur.fetchall()

        print("Testing password checking for all users:")
        for user in users:
            hash_value = user['password_hash']
            print(f"\nUser: {user['username']}")
            print(f"Hash: {repr(hash_value)}")
            print(f"Hash type: {type(hash_value)}")
            print(f"Hash length: {len(hash_value)}")
            print(f"Hash bytes: {hash_value.encode('utf-8')}")

            # Test with empty password
            try:
                result = check_password_hash(hash_value, "")
                print(f"Empty password check: {result}")
            except Exception as e:
                print(f"Empty password check FAILED: {e}")

            # Test with a test password
            try:
                result = check_password_hash(hash_value, "test")
                print(f"Test password check: {result}")
            except Exception as e:
                print(f"Test password check FAILED: {e}")

            # Test with the username as password
            try:
                result = check_password_hash(hash_value, user['username'])
                print(f"Username as password check: {result}")
            except Exception as e:
                print(f"Username as password check FAILED: {e}")

    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

def test_empty_hash():
    """Test what happens with empty hash"""
    print("\nTesting empty hash:")
    try:
        result = check_password_hash("", "test")
        print(f"Empty hash result: {result}")
    except Exception as e:
        print(f"Empty hash FAILED: {e}")

    print("\nTesting None hash:")
    try:
        result = check_password_hash(None, "test")
        print(f"None hash result: {result}")
    except Exception as e:
        print(f"None hash FAILED: {e}")

if __name__ == "__main__":
    test_password_checking()
    test_empty_hash()
