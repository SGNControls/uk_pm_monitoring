import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Check devices and their data sources
    cur.execute('''
        SELECT d.id, d.deviceid, d.name, d.has_relay, ds.source_type
        FROM dust_devices d
        JOIN dust_data_sources ds ON d.data_source_id = ds.id
        LIMIT 5
    ''')
    devices = cur.fetchall()
    print(f'Found {len(devices)} devices:')
    for device in devices:
        print(f'  ID: {device["id"]}, DeviceID: {device["deviceid"]}, Name: {device["name"]}, Type: {device["source_type"]}, Relay: {device["has_relay"]}')

    if devices:
        device_id = devices[0]['id']
        device_name = devices[0]['name']
        source_type = devices[0]['source_type']

        print(f'\nChecking data for device {device_name} (ID: {device_id}, Type: {source_type})')

        # Check sensor data
        cur.execute('SELECT COUNT(*) as count FROM dust_sensor_data WHERE device_id = %s', (device_id,))
        sensor_count = cur.fetchone()['count']
        print(f'Sensor data records: {sensor_count}')

        # Check extended data
        cur.execute('SELECT COUNT(*) as count FROM dust_extended_data WHERE device_id = %s', (device_id,))
        extended_count = cur.fetchone()['count']
        print(f'Extended data records: {extended_count}')

        if extended_count > 0:
            print('Recent extended data samples:')
            cur.execute('''
                SELECT timestamp, temperature_c, humidity_percent, pressure_hpa, voc_ppb, no2_ppb
                FROM dust_extended_data
                WHERE device_id = %s
                ORDER BY timestamp DESC LIMIT 3
            ''', (device_id,))
            extended_data = cur.fetchall()
            for row in extended_data:
                print(f'  {row["timestamp"]}: Temp={row["temperature_c"]}, Humidity={row["humidity_percent"]}, Pressure={row["pressure_hpa"]}, VOC={row["voc_ppb"]}, NO2={row["no2_ppb"]}')
        else:
            print('No extended data found for this device')

    conn.close()
except Exception as e:
    print(f'Error: {e}')
