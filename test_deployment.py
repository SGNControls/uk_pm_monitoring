#!/usr/bin/env python3
"""
Railway Deployment Test Script
Tests the configuration and connectivity for Railway deployment
"""

import os
import sys
import urllib.parse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_database_connection():
    """Test database connection configuration"""
    print("Testing database configuration...")

    DATABASE_URL = os.getenv('DATABASE_URL')

    if DATABASE_URL:
        print("✓ DATABASE_URL found")
        try:
            parsed = urllib.parse.urlparse(DATABASE_URL)
            print(f"  Host: {parsed.hostname}")
            print(f"  Port: {parsed.port}")
            print(f"  Database: {parsed.path.lstrip('/')}")
            print(f"  User: {parsed.username}")
            print("✓ DATABASE_URL parsing successful")
        except Exception as e:
            print(f"✗ DATABASE_URL parsing failed: {e}")
            return False
    else:
        print("⚠ DATABASE_URL not found, checking individual variables...")
        required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        for var in required_vars:
            if not os.getenv(var):
                print(f"✗ Missing {var}")
                return False
        print("✓ Individual database variables found")

    # Test actual connection
    try:
        import psycopg2
        from psycopg2.pool import SimpleConnectionPool

        if DATABASE_URL:
            parsed = urllib.parse.urlparse(DATABASE_URL)
            DB_CONFIG = {
                "host": parsed.hostname,
                "database": parsed.path.lstrip('/'),
                "user": parsed.username,
                "password": parsed.password,
                "port": parsed.port or 5432
            }
        else:
            DB_CONFIG = {
                "host": os.getenv('DB_HOST'),
                "database": os.getenv('DB_NAME'),
                "user": os.getenv('DB_USER'),
                "password": os.getenv('DB_PASSWORD'),
                "port": int(os.getenv('DB_PORT', 5432))
            }

        pool = SimpleConnectionPool(minconn=1, maxconn=1, **DB_CONFIG)
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        result = cur.fetchone()
        pool.putconn(conn)
        pool.closeall()

        if result[0] == 1:
            print("✓ Database connection successful")
            return True
        else:
            print("✗ Database connection test failed")
            return False

    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def test_flask_config():
    """Test Flask configuration"""
    print("\nTesting Flask configuration...")

    secret_key = os.getenv('SECRET_KEY')
    if secret_key and len(secret_key) > 10:
        print("✓ SECRET_KEY is set and sufficiently long")
    else:
        print("⚠ SECRET_KEY is weak or not set")

    railway_env = os.getenv('RAILWAY_ENVIRONMENT')
    if railway_env:
        print(f"✓ Running in Railway environment: {railway_env}")
    else:
        print("⚠ Not running in Railway environment")

    return True

def test_imports():
    """Test that all required modules can be imported"""
    print("\nTesting imports...")

    required_modules = [
        'flask', 'flask_socketio', 'flask_login', 'flask_caching',
        'psycopg2', 'paho.mqtt.client', 'eventlet', 'gunicorn'
    ]

    failed_imports = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError:
            print(f"✗ {module}")
            failed_imports.append(module)

    if failed_imports:
        print(f"✗ Failed to import: {', '.join(failed_imports)}")
        return False
    else:
        print("✓ All required modules imported successfully")
        return True

def main():
    """Run all tests"""
    print("Railway Deployment Test Suite")
    print("=" * 40)

    tests = [
        test_imports,
        test_flask_config,
        test_database_connection
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")

    print("\n" + "=" * 40)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Ready for Railway deployment.")
        return 0
    else:
        print("❌ Some tests failed. Please fix the issues before deploying.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
