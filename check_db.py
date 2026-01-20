import psycopg2
from psycopg2.extras import RealDictCursor
import os

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'dust_monitoring'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'port': int(os.getenv('DB_PORT', 5432))
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Check devices
    cur.execute('SELECT id, deviceid, name FROM dust_devices')
    devices = cur.fetchall()
    print('Devices:', devices)

    # Check data for first device if exists
    if devices:
        device_id = devices[0]['id']
        cur.execute('SELECT COUNT(*) as count FROM dust_sensor_data WHERE device_id = %s', (device_id,))
        count = cur.fetchone()
        print(f'Data count for device {device_id}: {count["count"]}')

        # Check date range
        cur.execute('SELECT MIN(timestamp), MAX(timestamp) FROM dust_sensor_data WHERE device_id = %s', (device_id,))
        date_range = cur.fetchone()
        print(f'Date range for device {device_id}: {date_range}')

    conn.close()
except Exception as e:
    print(f'Error: {e}')
