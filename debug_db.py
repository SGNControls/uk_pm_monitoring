import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_CONFIG = {
    "host": os.getenv('DB_HOST'),
    "database": os.getenv('DB_NAME'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "port": os.getenv('DB_PORT')
}

# Database connection
conn = psycopg2.connect(**DB_CONFIG)

cur = conn.cursor(cursor_factory=RealDictCursor)

# Check latest sensor data
print('=== LATEST SENSOR DATA ===')
cur.execute('SELECT * FROM dust_sensor_data ORDER BY timestamp DESC LIMIT 5')
sensor_data = cur.fetchall()
for row in sensor_data:
    print(f'Device: {row["device_id"]}, PM2.5: {row["pm2_5"]}, Timestamp: {row["timestamp"]}')

# Check latest extended data
print('\n=== LATEST EXTENDED DATA ===')
cur.execute('SELECT device_id, pm2_5, temperature_c, humidity_percent, voc_ppb, no2_ppb, noise_db, timestamp FROM dust_extended_data ORDER BY timestamp DESC LIMIT 5')
extended_data = cur.fetchall()
for row in extended_data:
    print(f'Device: {row["device_id"]}, PM2.5: {row["pm2_5"]}, Temp: {row["temperature_c"]}, Humidity: {row["humidity_percent"]}, VOC: {row["voc_ppb"]}, NO2: {row["no2_ppb"]}, Noise: {row["noise_db"]}, Timestamp: {row["timestamp"]}')

# Check devices
print('\n=== DEVICES ===')
cur.execute('SELECT id, deviceid, name, has_relay FROM dust_devices')
devices = cur.fetchall()
for device in devices:
    print(f'ID: {device["id"]}, DeviceID: {device["deviceid"]}, Name: {device["name"]}, Relay: {device["has_relay"]}')

conn.close()
