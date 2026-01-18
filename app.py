import eventlet
eventlet.monkey_patch()
import os
import sys
import json
from datetime import timezone
import time
import random
import csv
import io
import logging
from datetime import datetime, timedelta
from collections import deque
from typing import List, Dict
from functools import wraps
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, Response, render_template, jsonify, request, make_response, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_caching import Cache
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import requests
from time import sleep


# Initialize
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)

# Railway-specific configuration
if os.getenv('RAILWAY_ENVIRONMENT'):
    # Production settings for Railway
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
else:
    # Development settings
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize extensions
# Configure SocketIO for Railway compatibility
socketio_config = {
    'cors_allowed_origins': "*",
    'async_mode': 'eventlet',
    'logging': False,
    'engineio_logging': False,
    'ping_timeout': 60,
    'ping_interval': 25,
    'max_http_buffer_size': 1000000,
    'transports': ['polling', 'websocket']  # Allow both polling and websocket
}

# Add Railway-specific CORS if running on Railway
if os.getenv('RAILWAY_ENVIRONMENT'):
    socketio_config.update({
        'cors_allowed_origins': ["https://*.up.railway.app", "https://*.railway.app"],
        'cors_credentials': True,
        'cors_headers': ['Content-Type', 'Authorization', 'X-Requested-With']
    })

socketio = SocketIO(app, **socketio_config)
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
cache.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

logging.basicConfig(level=logging.INFO)
logging = logging.getLogger(__name__)

# Database configuration
# Railway provides DATABASE_URL, but we'll also support individual variables for compatibility
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Parse Railway DATABASE_URL
    import urllib.parse
    parsed = urllib.parse.urlparse(DATABASE_URL)
    DB_CONFIG = {
        "host": parsed.hostname,
        "database": parsed.path.lstrip('/'),
        "user": parsed.username,
        "password": parsed.password,
        "port": parsed.port or 5432
    }
else:
    # Fallback to individual environment variables
    DB_CONFIG = {
        "host": os.getenv('DB_HOST'),
        "database": os.getenv('DB_NAME'),
        "user": os.getenv('DB_USER'),
        "password": os.getenv('DB_PASSWORD'),
        "port": int(os.getenv('DB_PORT', 5432))
    }

# Initialize database connection pool
try:
    DB_POOL = SimpleConnectionPool(
        minconn=1,
        maxconn=20,
        **DB_CONFIG
    )
    logging.info("Database connection pool initialized")
except Exception as e:
    logging.error(f"Database connection pool failed: {e}")
    sys.exit(1)

# Data storage
latest_data = {
    "sensor": {},
    "status": {
        "mode": "auto",
        "relay_state": "OFF",
        "thresholds": {
            "pm1": 50.0,
            "pm2.5": 75.0,
            "pm4": 100.0,
            "pm10": 150.0,
            "tsp": 200.0
        }
    }
}

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, is_admin=False):
        self.id = id
        self.username = username
        self.email = email
        self.is_admin = is_admin

def get_db_connection():
    """Get database connection from pool with error handling"""
    try:
        return DB_POOL.getconn()
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        raise

def put_db_connection(conn):
    """Return database connection to pool"""
    try:
        DB_POOL.putconn(conn)
    except Exception as e:
        logging.error(f"Error returning connection to pool: {e}")

@login_manager.user_loader
def load_user(user_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, username, email, is_admin FROM dust_users WHERE id = %s", (user_id,))
        user_data = cur.fetchone()
        if user_data:
            return User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                is_admin=user_data['is_admin']
            )
    except Exception as e:
        logging.error(f"Error loading user: {e}")
    finally:
        if conn:
            put_db_connection(conn)
    return None

# Database initialization
def initialize_database():
    """Initialize database tables and default admin user"""
    conn = None
    try:


        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS dust_extended_data (
            id SERIAL PRIMARY KEY,
            device_id INTEGER REFERENCES dust_devices(id) ON DELETE CASCADE,
            timestamp TIMESTAMPTZ NOT NULL,
            temperature_c DOUBLE PRECISION,
            humidity_percent DOUBLE PRECISION,
            pressure_hpa DOUBLE PRECISION,
            voc_ppb DOUBLE PRECISION,
            no2_ppb DOUBLE PRECISION,
            pm1 DOUBLE PRECISION,
            pm2_5 DOUBLE PRECISION,
            pm4 DOUBLE PRECISION,
            pm10 DOUBLE PRECISION,
            tsp_um DOUBLE PRECISION,
            gps_lat DOUBLE PRECISION,
            gps_lon DOUBLE PRECISION,
            gps_alt_m DOUBLE PRECISION,
            gps_speed_kmh DOUBLE PRECISION,
            cloud_cover_percent DOUBLE PRECISION
        );
        """)
        conn.commit()

        # Check if tables exist
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'dust_users' LIMIT 1
        """)
        if not cur.fetchone():
            # Tables don't exist, create them
            with open('schema.sql', 'r') as f:
                sql_script = f.read()
            cur.execute(sql_script)
            conn.commit()
            logging.info("Database tables initialized successfully")

        # Create default admin user if not exists
        

        # Create dust_data_sources table if not exists
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'dust_data_sources' LIMIT 1
        """)
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dust_data_sources (
                    id SERIAL PRIMARY KEY,
                    source_type VARCHAR(10) NOT NULL CHECK (source_type IN ('mqtt', 'api')),
                    broker_url TEXT,
                    api_device_id TEXT,
                    description TEXT,
                    UNIQUE (source_type, broker_url, api_device_id)
                )
            """)
            conn.commit()
            logging.info("dust_data_sources table created successfully")

    except Exception as e:
        logging.error(f"Database initialization failed: {e}")
        raise
    finally:
        if conn:
            put_db_connection(conn)


        


            
    # MQTT clients are now initialized in initialize_mqtt_clients() above
    pass

    

# MQTT Client Management
mqtt_clients = {}

def process_extended_device_data(payload, device_id, timestamp, data_source_id):
    """Process and store extended telemetry data for new device type"""
    logging.info(f"[EXTENDED] Processing data for device: {device_id}")
    logging.info(f"[EXTENDED] Data source: {data_source_id}")
    logging.info(f"[EXTENDED] Payload keys: {list(payload.keys())}")
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get or validate device
        cur.execute("""
            SELECT id FROM dust_devices
            WHERE deviceid = %s AND data_source_id = %s
        """, (device_id, data_source_id))
        row = cur.fetchone()
        
        if not row:
            logging.warning(f"[EXTENDED] Unauthorized device: {device_id} for source: {data_source_id}")
            # Let's also check what devices exist
            cur.execute("SELECT deviceid, data_source_id FROM dust_devices")
            existing_devices = cur.fetchall()
            logging.info(f"[EXTENDED] Existing devices: {existing_devices}")
            return

        device_id_db = row[0]
        logging.info(f"[EXTENDED] Found device in DB with ID: {device_id_db}")

        # Check if this is the new compact format
        if "e" in payload and "pm" in payload and "g" in payload:
            logging.info(f"[EXTENDED] Processing new compact format")
            process_compact_format_data(payload, device_id_db, timestamp, data_source_id, cur)
        else:
            logging.info(f"[EXTENDED] Processing legacy extended format")
            # Legacy format processing
            temperature = payload.get("Temperature_C")
            humidity = payload.get("Humidity_%")
            pressure = payload.get("Pressure_hPa")
            voc = payload.get("VOC_ppb")
            no2 = payload.get("NO2_ppb")
            
            pm_data = payload.get("PM_data", {})
            logging.info(f"[EXTENDED] PM_data: {pm_data}")
            pm1 = pm_data.get("PM1")
            pm2_5 = pm_data.get("PM2_5")
            pm4 = pm_data.get("PM4")
            pm10 = pm_data.get("PM10")
            tsp_um = pm_data.get("TSP_um")

            gps_data = payload.get("GPS", {})
            logging.info(f"[EXTENDED] GPS_data: {gps_data}")
            gps_lat = gps_data.get("Latitude")
            gps_lon = gps_data.get("Longitude")
            gps_alt = gps_data.get("Altitude_m")
            gps_speed = gps_data.get("Speed_kmh")
            
            cloud_cover = payload.get("Cloud_cover_%")

            # Handle timestamp
            ts_str = payload.get("timestamp_utc")
            if ts_str:
                try:
                    timestamp = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                except Exception as e:
                    logging.warning(f"[EXTENDED] Invalid timestamp format: {ts_str} - using server timestamp: {e}")

            insert_extended_data(cur, device_id_db, timestamp, temperature, humidity, pressure,
                           voc, no2, pm1, pm2_5, pm4, pm10, tsp_um,
                           gps_lat, gps_lon, gps_alt, gps_speed, cloud_cover)
        
        conn.commit()
        logging.info(f"[EXTENDED] Successfully inserted extended data for device {device_id_db}")

        # Emit immediately to frontend for both streams
        emit_extended_websocket_update(device_id_db)
        emit_websocket_update(device_id_db)

    except Exception as e:
        logging.error(f"[EXTENDED] Error processing extended device data: {e}")
        if conn:
            conn.rollback()
        raise  # Re-raise to see full traceback
    finally:
        if conn:
            put_db_connection(conn)

def process_compact_format_data(payload, device_id_db, timestamp, data_source_id, cur):
    """Process the new compact data format"""
    logging.info(f"[COMPACT] Processing compact format data for device: {device_id_db}")

    # Extract the arrays
    environmental_data = payload.get("e", [])
    pm_data = payload.get("pm", [])
    gps_data = payload.get("g", {})

    logging.info(f"[COMPACT] Environmental data length: {len(environmental_data)}")
    logging.info(f"[COMPACT] PM data length: {len(pm_data)}")
    logging.info(f"[COMPACT] GPS data: {gps_data}")

    # Map environmental data according to the new MQTT script structure (8+ elements)
    # Index 0: Temperature (°C) - REAL SENSOR DATA
    # Index 1: Humidity (%) - REAL SENSOR DATA
    # Index 2: Pressure (hPa) - REAL SENSOR DATA
    # Index 3: UV Index - REAL SENSOR DATA
    # Index 4: Lux (lux) - REAL SENSOR DATA
    # Index 5: VOC (ppb) - REAL SENSOR DATA ⭐️ NEW
    # Index 6: NO2 (ppb) - REAL SENSOR DATA ⭐️ NEW
    # Index 7: Noise (dB) - REAL SENSOR DATA ⭐️ NEW

    temperature = environmental_data[0] if len(environmental_data) > 0 and environmental_data[0] is not None else None
    humidity = environmental_data[1] if len(environmental_data) > 1 and environmental_data[1] is not None else None
    pressure = environmental_data[2] if len(environmental_data) > 2 and environmental_data[2] is not None else None
    uv_index = environmental_data[3] if len(environmental_data) > 3 and environmental_data[3] is not None else None
    lux = environmental_data[4] if len(environmental_data) > 4 and environmental_data[4] is not None else None

    # Based on actual MQTT data received, map the values correctly
    # From the actual data: [22.67, 33.87, 1012.49, 0.0, 0.44, 32044, 0.605, 66.23]
    # Index 5: 32044 (this looks like a large ADC reading, convert to ppb)
    # Index 6: 0.605 (this looks like ppm, convert to ppb)
    # Index 7: 66.23 (this looks like dB already)

    # Extract raw values with debug logging
    voc_raw = environmental_data[5] if len(environmental_data) > 5 and environmental_data[5] is not None else None
    no2_raw = environmental_data[6] if len(environmental_data) > 6 and environmental_data[6] is not None else None
    noise_db = environmental_data[7] if len(environmental_data) > 7 and environmental_data[7] is not None else None

    logging.info(f"[COMPACT] Raw values - VOC: {voc_raw}, NO2: {no2_raw}, Noise: {noise_db}")

    # Convert raw values to proper units
    # VOC: raw ADC value (32044) -> convert to reasonable ppb range
    voc = voc_raw / 1000 if voc_raw is not None and voc_raw != 0 else None  # 32044 -> 32.044 ppb

    # NO2: ppm value (0.605) -> convert to ppb
    no2 = no2_raw * 1000 if no2_raw is not None and no2_raw != 0 else None  # 0.605 ppm -> 605 ppb

    # Noise: already in dB
    # noise_db is already in correct units

    logging.info(f"[COMPACT] Converted values - VOC: {voc}, NO2: {no2}, Noise: {noise_db}")

    # Battery still at the end if available
    battery_percent = environmental_data[18] if len(environmental_data) > 18 and environmental_data[18] is not None else None

    cloud_cover = None  # Not implemented yet
    
    # PM data mapping: [PM1, PM2.5, PM4, PM10, TSP]
    pm1 = pm_data[0] if len(pm_data) > 0 else None
    pm2_5 = pm_data[1] if len(pm_data) > 1 else None
    pm4 = pm_data[2] if len(pm_data) > 2 else None
    pm10 = pm_data[3] if len(pm_data) > 3 else None
    tsp_um = pm_data[4] if len(pm_data) > 4 else None
    
    # GPS data
    gps_lat = gps_data.get("lat")
    gps_lon = gps_data.get("lon")
    gps_alt = None  # Not provided in this format
    gps_speed = None  # Not provided in this format
    
    # Handle timestamp
    timestamp_str = payload.get("t")
    if timestamp_str:
        try:
            # Handle ISO format with Z
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            timestamp = datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logging.warning(f"[COMPACT] Invalid timestamp format: {timestamp_str} - using server timestamp: {e}")
            timestamp = datetime.now(timezone.utc)
    
    logging.info(f"[COMPACT] Mapped values:")
    logging.info(f"[COMPACT]   Temperature: {temperature}°C")
    logging.info(f"[COMPACT]   Humidity: {humidity}%")
    logging.info(f"[COMPACT]   Pressure: {pressure}hPa")
    logging.info(f"[COMPACT]   Lux: {lux} lux")
    logging.info(f"[COMPACT]   UV Index: {uv_index}")
    logging.info(f"[COMPACT]   Battery: {battery_percent}%")
    logging.info(f"[COMPACT]   VOC: {voc}ppb")
    logging.info(f"[COMPACT]   NO2: {no2}ppb")
    logging.info(f"[COMPACT]   Cloud Cover: {cloud_cover}%")
    logging.info(f"[COMPACT]   PM1: {pm1}")
    logging.info(f"[COMPACT]   PM2.5: {pm2_5}")
    logging.info(f"[COMPACT]   PM4: {pm4}")
    logging.info(f"[COMPACT]   PM10: {pm10}")
    logging.info(f"[COMPACT]   TSP: {tsp_um}")
    logging.info(f"[COMPACT]   GPS: lat={gps_lat}, lon={gps_lon}")
    
    # Insert into database
    insert_extended_data(cur, device_id_db, timestamp, temperature, humidity, pressure,
                     voc, no2, noise_db, pm1, pm2_5, pm4, pm10, tsp_um,
                     gps_lat, gps_lon, gps_alt, gps_speed, cloud_cover,
                     lux, uv_index, battery_percent)
    
    # Also insert/update the standard sensor table so existing charts/UI update
    try:
        cur.execute(
            """
            INSERT INTO dust_sensor_data
            (timestamp, device_id, data_source_id, pm1, pm2_5, pm4, pm10, tsp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                timestamp,
                device_id_db,
                data_source_id,
                float(pm1) * 1 if pm1 is not None else None,
                float(pm2_5) * 1 if pm2_5 is not None else None,
                float(pm4) * 1 if pm4 is not None else None,
                float(pm10) * 1 if pm10 is not None else None,
                float(tsp_um) * 1 if tsp_um is not None else None,
            ),
        )
        logging.info(f"[COMPACT] Successfully inserted mirrored sensor data")
    except Exception as e:
        logging.warning(f"[COMPACT] Failed to write mirrored sensor row: {e}")

def insert_extended_data(cur, device_id_db, timestamp, temperature, humidity, pressure,
                     voc, no2, noise_db, pm1, pm2_5, pm4, pm10, tsp_um,
                     gps_lat, gps_lon, gps_alt, gps_speed, cloud_cover,
                     lux=None, uv_index=None, battery_percent=None):
    """Helper function to insert extended data into database"""
    cur.execute("""
        INSERT INTO dust_extended_data (
            device_id, timestamp,
            temperature_c, humidity_percent, pressure_hpa,
            voc_ppb, no2_ppb, noise_db,
            pm1, pm2_5, pm4, pm10, tsp_um,
            gps_lat, gps_lon, gps_alt_m, gps_speed_kmh,
            cloud_cover_percent, lux, uv_index, battery_percent
        ) VALUES (
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
        )
    """, (
        device_id_db, timestamp,
        temperature, humidity, pressure,
        voc, no2, noise_db,
        pm1, pm2_5, pm4, pm10, tsp_um,
        gps_lat, gps_lon, gps_alt, gps_speed,
        cloud_cover, lux, uv_index, battery_percent
    ))
    logging.info(f"[EXTENDED] Successfully inserted extended data")


def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    logging.info(f"[MQTT] Connection result code: {rc}")
    if rc == 0:
        logging.info(f"[MQTT] Connection result code: {rc}")
        logging.info("Connected to MQTT broker")
        for topic in userdata['topics']:
            client.subscribe(topic)
            logging.info(f"Subscribed to {topic}")
            
    else:
        logging.error(f"Failed to connect to MQTT broker with result code {rc}")

def on_mqtt_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        device_id = payload.get("deviceid") or payload.get("i")  # Support both formats

        if not device_id:
            logging.warning("MQTT message missing deviceid or i")
            return

        timestamp = datetime.now(timezone.utc)
        data_source_id = userdata['data_source_id']

        logging.info(f"[MQTT] msg topic={msg.topic}, payload={msg.payload[:200]}")

        # Process message based on topic
        if msg.topic.endswith("data"):
            logging.info(f"[MQTT] Processing message for device: {device_id}")
            logging.info(f"[MQTT] Payload keys: {list(payload.keys())}")
            logging.info(f"[MQTT] Payload sample: {str(payload)[:500]}")

            # Check for compact format (new format with e, pm, g arrays)
            is_compact_format = "e" in payload and "pm" in payload and "g" in payload
            # Check for legacy extended format
            has_pm_data = "PM_data" in payload
            has_extended_keys = any(k in payload for k in ["Temperature_C", "Humidity_%", "GPS"])

            logging.info(f"[MQTT] Compact format present: {is_compact_format}")
            logging.info(f"[MQTT] Legacy PM_data present: {has_pm_data}")
            logging.info(f"[MQTT] Legacy extended keys present: {has_extended_keys}")

            if is_compact_format or (has_pm_data and has_extended_keys):
                logging.info("[MQTT] Routing to process_extended_device_data")
                process_extended_device_data(payload, device_id, timestamp, data_source_id)
            else:
                logging.info("[MQTT] Routing to process_sensor_data")
                process_sensor_data(payload, device_id, timestamp, data_source_id)
        elif msg.topic.endswith("status"):
            process_status_data(payload, device_id)
            
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON payload: {msg.payload}")
    except Exception as e:
        logging.error(f"Error processing MQTT message: {e}")

def start_mqtt_client(data_source_id, broker_url, topics, username=None, password=None):
    """Start MQTT client with Railway-compatible threading"""
    import threading

    def mqtt_worker():
        def on_connect(client, userdata, flags, rc, properties=None):
            logging.info(f"[MQTT-{data_source_id}] Connected to broker: {broker_url}, rc={rc}")
            if rc == 0:
                for topic in topics:
                    client.subscribe(topic, qos=1)
                    logging.info(f"[MQTT-{data_source_id}] Subscribed to topic: {topic}")
            else:
                logging.error(f"[MQTT-{data_source_id}] Connection failed with rc={rc}")

        def on_message(client, userdata, msg):
            try:
                # Get full payload first
                raw_payload = msg.payload.decode('utf-8')
                logging.info(f"[MQTT-{data_source_id}] Topic: {msg.topic}")
                logging.info(f"[MQTT-{data_source_id}] Payload size: {len(raw_payload)} bytes")
                logging.info(f"[MQTT-{data_source_id}] Full payload: {raw_payload}")

                payload = json.loads(raw_payload)
                device_id = payload.get("deviceid") or payload.get("i")

                if not device_id:
                    logging.warning(f"[MQTT-{data_source_id}] Message missing deviceid or i")
                    return

                logging.info(f"[MQTT-{data_source_id}] Parsed payload keys: {list(payload.keys())}")

                timestamp = datetime.now(timezone.utc)
                data_source_id_local = userdata['data_source_id']

                if msg.topic.endswith("data"):
                    # Check for compact format
                    is_compact_format = "e" in payload and "pm" in payload and "g" in payload
                    has_pm_data = "PM_data" in payload
                    has_extended_keys = any(k in payload for k in ["Temperature_C", "Humidity_%", "GPS"])

                    logging.info(f"[MQTT-{data_source_id}] Compact format: {is_compact_format}")

                    if is_compact_format or (has_pm_data and has_extended_keys):
                        logging.info(f"[MQTT-{data_source_id}] Processing extended data")
                        process_extended_device_data(payload, device_id, timestamp, data_source_id_local)
                    else:
                        logging.info(f"[MQTT-{data_source_id}] Processing sensor data")
                        process_sensor_data(payload, device_id, timestamp, data_source_id_local)
                elif msg.topic.endswith("status"):
                    process_status_data(payload, device_id)

            except json.JSONDecodeError as e:
                logging.error(f"[MQTT-{data_source_id}] JSON decode error: {e}")
                logging.error(f"[MQTT-{data_source_id}] Raw payload: {msg.payload}")
            except Exception as e:
                logging.error(f"[MQTT-{data_source_id}] Error processing message: {e}")

        def on_disconnect(client, userdata, rc):
            logging.warning(f"[MQTT-{data_source_id}] Disconnected with code: {rc}")
            if rc != 0:
                logging.info(f"[MQTT-{data_source_id}] Unexpected disconnection, will retry...")

        while True:
            try:
                logging.info(f"[MQTT-{data_source_id}] Creating MQTT client...")

                client = mqtt.Client(
                    mqtt.CallbackAPIVersion.VERSION2,
                    userdata={"data_source_id": data_source_id, "topics": topics}
                )

                # Configure authentication
                if username and password:
                    client.username_pw_set(username, password)
                    logging.info(f"[MQTT-{data_source_id}] Auth configured for user: {username}")

                # Configure TLS for Railway compatibility
                import ssl
                context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                client.tls_set_context(context)

                # Set callbacks
                client.on_connect = on_connect
                client.on_message = on_message
                client.on_disconnect = on_disconnect

                # Set message buffer sizes
                client.max_inflight_messages_set(10)
                client.max_queued_messages_set(100)

                logging.info(f"[MQTT-{data_source_id}] Connecting to {broker_url}:8883...")
                client.connect(broker_url, 8883, 60)

                # Store client reference
                mqtt_clients[data_source_id] = client
                logging.info(f"[MQTT-{data_source_id}] Client stored, starting loop...")

                # Start the MQTT loop (blocking)
                client.loop_forever()

            except Exception as e:
                logging.error(f"[MQTT-{data_source_id}] Connection error: {e}")
                logging.info(f"[MQTT-{data_source_id}] Retrying in 15 seconds...")
                time.sleep(15)

    # Start the MQTT worker in a daemon thread
    thread = threading.Thread(target=mqtt_worker, daemon=True, name=f"MQTT-{data_source_id}")
    thread.start()
    logging.info(f"[MQTT-{data_source_id}] Started MQTT thread")

# Updated MQTT initialization function using Railway-compatible approach
def initialize_mqtt_clients():
    import threading

    logging.info("[MQTT-INIT] 🚀 Starting MQTT client initialization...")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ds.id, ds.broker_url, ds.username, ds.password
            FROM dust_data_sources ds
            WHERE ds.source_type = 'mqtt'
        """)
        mqtt_sources = cur.fetchall()

        logging.info(f"[MQTT-INIT] 📊 Found {len(mqtt_sources)} MQTT data sources")

        for source in mqtt_sources:
            data_source_id, broker_url, username, password = source
            logging.info(f"[MQTT-INIT] 🔄 Processing data source {data_source_id}: {broker_url}")

            # Check if client already exists
            if data_source_id in mqtt_clients:
                logging.warning(f"[MQTT-INIT] ⚠️ MQTT client for data source {data_source_id} already exists")
                continue

            try:
                # Use standard threading instead of eventlet for Railway compatibility
                thread = threading.Thread(
                    target=start_mqtt_client,
                    args=(data_source_id, broker_url, ['sensor/data', 'dustrak/status'], username, password),
                    daemon=True,
                    name=f"MQTT-{data_source_id}"
                )
                thread.start()
                logging.info(f"[MQTT-INIT] ✅ Started MQTT client thread for data source {data_source_id}")

                # Give thread time to start and check if it's alive
                time.sleep(0.5)
                if thread.is_alive():
                    logging.info(f"[MQTT-INIT] 🟢 Thread {thread.name} is running")
                else:
                    logging.error(f"[MQTT-INIT] 🔴 Thread {thread.name} died immediately")

            except Exception as thread_error:
                logging.error(f"[MQTT-INIT] ❌ Failed to start MQTT thread for data source {data_source_id}: {thread_error}")

    except Exception as e:
        logging.error(f"[MQTT-INIT] 💥 MQTT initialization failed: {e}")
    finally:
        if conn:
            put_db_connection(conn)

    logging.info("[MQTT-INIT] ✨ MQTT client initialization completed")

# Add to initialization
def initialize_app():
    initialize_database()
    initialize_mqtt_clients()  # Initialize all MQTT clients
    
    logging.info("All services initialized")


def process_sensor_data(payload, device_id, timestamp, data_source_id):
    """Process and store sensor data only for the specified device and data source"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get or create device associated with this data source
        cur.execute("""
            SELECT id, user_id, has_relay 
            FROM dust_devices 
            WHERE deviceid = %s AND data_source_id = %s
        """, (device_id, data_source_id))
        device = cur.fetchone()

        if not device:
            # Create device with admin user as owner
            logging.warning(f"Unauthorized device creation attempted: {device_id}")
            return
        device_id_db = device[0]
        user_id = device[1]
        has_relay = device[2]

        # Insert sensor data
        pm_data = payload.get("PM_data", {})
        db_record = {
            "timestamp": timestamp,
            "device_id": device_id_db,
            "data_source_id": data_source_id,
            "pm1": float(pm_data.get("PM1", 0)) * 1000,
            "pm2_5": float(pm_data.get("PM2_5", 0)) * 1000,
            "pm4": float(pm_data.get("PM4", 0)) * 1000,
            "pm10": float(pm_data.get("PM10", 0)) * 1000,
            "tsp": float(pm_data.get("TSP_um", 0)) * 1000
        }

        cur.execute("""
            INSERT INTO dust_sensor_data
            (timestamp, device_id, data_source_id, pm1, pm2_5, pm4, pm10, tsp)
            VALUES (%(timestamp)s, %(device_id)s, %(data_source_id)s, %(pm1)s, %(pm2_5)s, %(pm4)s, %(pm10)s, %(tsp)s)
        """, db_record)
        conn.commit()

        # Only process thresholds if device has relay
        if has_relay:
            process_thresholds(device_id_db, user_id)

        # Emit WebSocket update
        emit_websocket_update(device_id_db)

        # Also emit extended data if this was an extended device
        if hasattr(data, 'get') and ('e' in data or 'extended' in data or 'Temperature_C' in data):
            emit_extended_websocket_update(device_id_db)

    except Exception as e:
        logging.error(f"Error processing sensor data: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            put_db_connection(conn)

@app.route('/')
def landing_page():
    return render_template('index.html')

@app.route('/contact_us')
def contact_us():
    return render_template('contact_us.html')

@app.route('/about_us')
def about_us():
    return render_template('about_us.html')

@app.route('/products')
def products():
    return render_template('products.html')




def process_status_data(payload, device_id):
    """Process status data from MQTT"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, has_relay FROM dust_devices WHERE deviceid = %s", (device_id,))

        device = cur.fetchone()

        if device and not device[0]:
            return

        latest_data["status"].update(payload)

        if "thresholds" in payload:
            cur.execute("""
                INSERT INTO dust_thresholds (device_id, pm1, pm2_5, pm4, pm10, tsp, averaging_window)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                device[0],
                payload["thresholds"].get("pm1", latest_data["status"]["thresholds"]["pm1"]),
                payload["thresholds"].get("pm2.5", latest_data["status"]["thresholds"]["pm2.5"]),
                payload["thresholds"].get("pm4", latest_data["status"]["thresholds"]["pm4"]),
                payload["thresholds"].get("pm10", latest_data["status"]["thresholds"]["pm10"]),
                payload["thresholds"].get("tsp", latest_data["status"]["thresholds"]["tsp"]),
                payload.get("averaging_window", 15)
            ))

            conn.commit()
    except Exception as e:
        logging.error(f"Error saving thresholds: {e}")
    finally:
        if conn:
            put_db_connection(conn)
                

def process_thresholds(device_id, user_id):
    """Check thresholds and control relay if needed"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get averages over the configured window
        cur.execute("""
            WITH window_settings AS (
                SELECT averaging_window
                FROM dust_thresholds
                WHERE device_id = %s
                ORDER BY timestamp DESC
                LIMIT 1
            ),
            recent_data AS (
                SELECT pm1, pm2_5, pm4, pm10, tsp
                FROM dust_sensor_data
                WHERE device_id = %s
                AND timestamp >= NOW() - INTERVAL '1 minute' * COALESCE((SELECT averaging_window FROM window_settings), 15)
                ORDER BY timestamp DESC
            )
            SELECT
                AVG(pm1) as avg_pm1,
                AVG(pm2_5) as avg_pm2_5,
                AVG(pm4) as avg_pm4,
                AVG(pm10) as avg_pm10,
                AVG(tsp) as avg_tsp
            FROM recent_data
        """, (device_id, device_id))

        averages = cur.fetchone()

        # Get latest thresholds
        cur.execute("""
            SELECT pm1, pm2_5, pm4, pm10, tsp, averaging_window
            FROM dust_thresholds
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))

        threshold_row = cur.fetchone()
        thresholds = {
            "pm1": threshold_row[0] if threshold_row else latest_data["status"]["thresholds"]["pm1"],
            "pm2.5": threshold_row[1] if threshold_row else latest_data["status"]["thresholds"]["pm2.5"],
            "pm4": threshold_row[2] if threshold_row else latest_data["status"]["thresholds"]["pm4"],
            "pm10": threshold_row[3] if threshold_row else latest_data["status"]["thresholds"]["pm10"],
            "tsp": threshold_row[4] if threshold_row else latest_data["status"]["thresholds"]["tsp"],
            "averaging_window": threshold_row[5] if threshold_row else 15
        }

        # Check if any threshold is exceeded
        trigger_relay = False
        if averages and any([
            averages[0] and averages[0] > thresholds["pm1"],
            averages[1] and averages[1] > thresholds["pm2.5"],
            averages[2] and averages[2] > thresholds["pm4"],
            averages[3] and averages[3] > thresholds["pm10"],
            averages[4] and averages[4] > thresholds["tsp"]
        ]):
            trigger_relay = True
            create_alert(device_id, "threshold_exceeded", "One or more thresholds exceeded", thresholds, averages)

        # Publish control message
        control_message = {
            "command": "all_on" if trigger_relay else "all_off",
            "source": "server",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "deviceid": device_id
        }
        if device_id in mqtt_clients and mqtt_clients[device_id].is_connected():
            mqtt_clients[device_id].publish("dustrak/control", json.dumps(control_message), qos=1)

    except Exception as e:
        logging.error(f"Error processing thresholds: {e}")
    finally:
        if conn:
            put_db_connection(conn)



def emit_websocket_update(device_id):
    """Emit WebSocket update for a specific device"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get latest sensor reading
        cur.execute("""
            SELECT timestamp, pm1, pm2_5, pm4, pm10, tsp
            FROM dust_sensor_data
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        latest_sensor = cur.fetchone()

        def safe_avg(values):
            return sum(values) / len(values) if values else 0



        cur.execute("SELECT has_relay FROM dust_devices WHERE id = %s", (device_id,))
        row = cur.fetchone()
        has_relay = row['has_relay'] if row else False


        # Get chart data (last 15 minutes)
        cur.execute("""
            SELECT timestamp, pm1, pm2_5, pm4, pm10, tsp
            FROM dust_sensor_data
            WHERE device_id = %s
            AND timestamp >= NOW() - INTERVAL '15 minutes'
            ORDER BY timestamp ASC
        """, (device_id,))
        chart_data = cur.fetchall()

        avg_pm1 = safe_avg([float(r['pm1']) for r in chart_data if r['pm1'] is not None])
        avg_pm2_5 = safe_avg([float(r['pm2_5']) for r in chart_data if r['pm2_5'] is not None])
        avg_pm4 = safe_avg([float(r['pm4']) for r in chart_data if r['pm4'] is not None])
        avg_pm10 = safe_avg([float(r['pm10']) for r in chart_data if r['pm10'] is not None])
        avg_tsp = safe_avg([float(r['tsp']) for r in chart_data if r['tsp'] is not None])


        # Get latest thresholds
        cur.execute("""
            SELECT pm1, pm2_5, pm4, pm10, tsp, averaging_window
            FROM dust_thresholds
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        threshold_row = cur.fetchone()

        # Get extended data if available
        extended_data = None
        try:
            cur.execute("""
                SELECT *
                FROM dust_extended_data
                WHERE device_id = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (device_id,))
            extended_row = cur.fetchone()
            if extended_row:
                extended_data = dict(extended_row)
                # Convert datetime to ISO string
                if isinstance(extended_data.get("timestamp"), datetime):
                    extended_data["timestamp"] = extended_data["timestamp"].isoformat()
        except Exception as e:
            logging.warning(f"Could not fetch extended data for device {device_id}: {e}")

        # Prepare data for WebSocket
        cur.execute("SELECT user_id FROM dust_devices WHERE id = %s", (device_id,))
        user_row = cur.fetchone()
        if user_row:
            user_id = user_row['user_id']

            websocket_data = {
                'device_id': device_id,
                'sensor': {
                    **latest_sensor,
                    'timestamp': latest_sensor['timestamp'].isoformat(),
                    'avg_pm1': avg_pm1,
                    'avg_pm2_5': avg_pm2_5,
                    'avg_pm4': avg_pm4,
                    'avg_pm10': avg_pm10,
                    'avg_tsp': avg_tsp
                } if latest_sensor else {},
                'history': {
                    "timestamps": [row['timestamp'].isoformat() for row in chart_data],
                    "pm1": [float(row['pm1']) if row['pm1'] else 0 for row in chart_data],
                    "pm2_5": [float(row['pm2_5']) if row['pm2_5'] else 0 for row in chart_data],
                    "pm4": [float(row['pm4']) if row['pm4'] else 0 for row in chart_data],
                    "pm10": [float(row['pm10']) if row['pm10'] else 0 for row in chart_data],
                    "tsp": [float(row['tsp']) if row['tsp'] else 0 for row in chart_data],
                },
                'status': {
                    'system': 'operational',
                    'mode': 'auto',
                    'relay_state': latest_data["status"].get("relay_state", "OFF") if has_relay else "N/A",   # <-- THIS LINE
                    'thresholds': {
                        "pm1": threshold_row['pm1'] if threshold_row else latest_data["status"]["thresholds"]["pm1"],
                        "pm2.5": threshold_row['pm2_5'] if threshold_row else latest_data["status"]["thresholds"]["pm2.5"],
                        "pm4": threshold_row['pm4'] if threshold_row else latest_data["status"]["thresholds"]["pm4"],
                        "pm10": threshold_row['pm10'] if threshold_row else latest_data["status"]["thresholds"]["pm10"],
                        "tsp": threshold_row['tsp'] if threshold_row else latest_data["status"]["thresholds"]["tsp"],
                        "averaging_window": threshold_row['averaging_window'] if threshold_row else 15
                    }
                }
            }

            # Include extended data if available
            if extended_data:
                websocket_data['extended'] = extended_data
                logging.info(f"Including extended data in WebSocket update for device {device_id}: temp={extended_data.get('temperature_c')}, humidity={extended_data.get('humidity_percent')}, lux={extended_data.get('lux')}")
            else:
                logging.info(f"No extended data found for device {device_id}")

            socketio.emit('new_data', websocket_data, room=f"user_{user_id}_device_{device_id}")

    except Exception as e:
        logging.error(f"Error emitting WebSocket update: {e}")
    finally:
        if conn:
            put_db_connection(conn)


def emit_extended_websocket_update(device_id):
    """Send latest extended device data to frontend via WebSocket"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT *
            FROM dust_extended_data
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        latest_ext = cur.fetchone()

        if not latest_ext:
            return

        # Send data
        cur.execute("SELECT user_id FROM dust_devices WHERE id = %s", (device_id,))
        user_row = cur.fetchone()
        if not user_row:
            return

        user_id = user_row['user_id']

        # Convert datetime objects to ISO strings for JSON serialization
        def serialize_extended_row(row):
            data = dict(row)
            if isinstance(data.get("timestamp"), datetime):
                data["timestamp"] = data["timestamp"].isoformat()
            return data

        serialized_data = serialize_extended_row(latest_ext)
        socketio.emit('new_extended_data', serialized_data, room=f"user_{user_id}_device_{device_id}")

    except Exception as e:
        logging.error(f"Error emitting extended WebSocket: {e}")
    finally:
        if conn:
            put_db_connection(conn)



# Add these routes to app.py

@app.route('/api/admin/data_sources', methods=['GET'])
@login_required
def get_data_sources():
    """Get all data sources"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, source_type, broker_url, api_device_id, description
            FROM dust_data_sources
            ORDER BY id DESC
        """)
        data_sources = cur.fetchall()
        return jsonify({"data_sources": data_sources})
    except Exception as e:
        logging.error(f"Error fetching data sources: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            put_db_connection(conn)

@app.route('/api/admin/data_sources', methods=['POST'])
@login_required
def add_data_source():
    """Add a new data source"""
    try:
        data = request.get_json()
        source_type = data.get('source_type')
        description = data.get('description', '')

        if not source_type or source_type not in ['mqtt', 'api']:
            return jsonify({"status": "error", "message": "Invalid source type"}), 400

        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            if source_type == 'mqtt':
                broker_url = data.get('broker_url')
                username = data.get('username', '')
                password = data.get('password', '')

                if not broker_url:
                    return jsonify({"status": "error", "message": "Broker URL is required"}), 400

                # Check for duplicate broker
                cur.execute("SELECT id FROM dust_data_sources WHERE broker_url = %s", (broker_url,))
                if cur.fetchone():
                    return jsonify({"status": "error", "message": "Broker already exists"}), 400

                cur.execute("""
                    INSERT INTO dust_data_sources (source_type, broker_url, username, password, description)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                """, (source_type, broker_url, username, password, description))

                data_source_id = cur.fetchone()[0]
                conn.commit()

                # MQTT clients are now initialized in initialize_mqtt_clients() above

            else:  # API source
                api_device_id = data.get('api_device_id')
                if not api_device_id:
                    return jsonify({"status": "error", "message": "API Device ID is required"}), 400

                cur.execute("""
                    INSERT INTO dust_data_sources (source_type, api_device_id, description)
                    VALUES (%s, %s, %s) RETURNING id
                """, (source_type, api_device_id, description))
                data_source_id = cur.fetchone()[0]
                conn.commit()

            return jsonify({"status": "success", "data_source_id": data_source_id})
        except Exception as e:
            logging.error(f"Error adding data source: {e}")
            if conn:
                conn.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
        finally:
            if conn:
                put_db_connection(conn)

    except Exception as e:
        logging.error(f"Error in add_data_source: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admin/data_sources/<int:source_id>', methods=['DELETE'])
@login_required
def delete_data_source(source_id):
    """Delete a data source"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # First delete any credentials referencing this source
        
        
        # Then delete the source
        cur.execute("DELETE FROM dust_data_sources WHERE id = %s", (source_id,))
        conn.commit()

        # Stop MQTT client if running
        if source_id in mqtt_clients:
            mqtt_clients[source_id].disconnect()
            del mqtt_clients[source_id]

        return jsonify({"status": "success"})
    except Exception as e:
        logging.error(f"Error deleting data source: {e}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn:
            put_db_connection(conn)



@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_password or not new_password or not confirm_password:
            return render_template('change_password.html', error="All fields are required.")

        if new_password != confirm_password:
            return render_template('change_password.html', error="New passwords do not match.")

        conn = get_db_connection()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT password_hash FROM dust_users WHERE id = %s", (current_user.id,))
            user = cur.fetchone()
            if not user or not check_password_hash(user['password_hash'], current_password):
                return render_template('change_password.html', error="Incorrect current password.")

            new_hash = generate_password_hash(new_password)
            cur.execute("UPDATE dust_users SET password_hash = %s WHERE id = %s", (new_hash, current_user.id))
            conn.commit()
            return render_template('change_password.html', success="Password changed successfully.")
        except Exception as e:
            logging.error(f"Error changing password: {e}")
            return render_template('change_password.html', error="Something went wrong. Try again.")
        finally:
            put_db_connection(conn)
    return render_template('change_password.html')




def create_alert(device_id, alert_type, message, thresholds=None, readings=None):
    """Create an alert in the database"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        threshold_value = None
        measured_value = None

        if alert_type == "threshold_exceeded" and thresholds and readings:
            for i, param in enumerate(["pm1", "pm2.5", "pm4", "pm10", "tsp"]):
                if readings[i] and readings[i] > thresholds[param]:
                    threshold_value = thresholds[param]
                    measured_value = readings[i]
                    break

        cur.execute("""
            INSERT INTO dust_device_alerts
            (device_id, alert_type, message, threshold_value, measured_value)
            VALUES (%s, %s, %s, %s, %s)
        """, (device_id, alert_type, message, threshold_value, measured_value))
        conn.commit()

    except Exception as e:
        logging.error(f"Error creating alert: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            put_db_connection(conn)

def add_data_source(source_type: str, source_config: dict):
    """Add a new data source to the database."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if source_type == 'mqtt':
            cur.execute(
                "INSERT INTO dust_data_sources (source_type, broker_url, description) VALUES (%s, %s, %s) RETURNING id",
                (source_type, source_config.get('broker_url'), source_config.get('description', ''))
            )
        elif source_type == 'api':
            cur.execute(
                "INSERT INTO dust_data_sources (source_type, api_device_id, description) VALUES (%s, %s, %s) RETURNING id",
                (source_type, source_config.get('api_device_id'), source_config.get('description', ''))
            )
        data_source_id = cur.fetchone()[0]
        conn.commit()

        # Start MQTT client if source type is MQTT
        if source_type == 'mqtt':
            eventlet.spawn(start_mqtt_client, data_source_id, source_config['broker_url'], ['sensor/data', 'dustrak/status'], source_config.get('username'), source_config.get('password'))

        return data_source_id
    except Exception as e:
        logging.error(f"Error adding data source: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            put_db_connection(conn)

@app.route('/dashboard')
def dashboard():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Show all devices for demo (temporarily bypass auth for testing)
        cur.execute("""
            SELECT d.id, d.deviceid, d.name, d.has_relay, ds.source_type
            FROM dust_devices d
            JOIN dust_data_sources ds ON d.data_source_id = ds.id
            ORDER BY d.created_at DESC
        """)
        devices = cur.fetchall()

        # Debug: Print what we found
        print(f"[DASHBOARD] Found {len(devices)} devices")
        for device in devices:
            print(f"[DASHBOARD] Device: {device}")
            print(f"[DASHBOARD]   ID: {device['id']}")
            print(f"[DASHBOARD]   DeviceID: {device['deviceid']}")
            print(f"[DASHBOARD]   Name: {device['name']}")
            print(f"[DASHBOARD]   Relay: {device['has_relay']}")
            print(f"[DASHBOARD]   Type: {device['source_type']}")

        # Add debug info to template context
        debug_info = {
            'device_count': len(devices),
            'device_list': [f"{d['name']} ({d['deviceid']})" for d in devices]
        }

        print(f"[DASHBOARD] Debug info: {debug_info}")

        # Set demo user ID in session for WebSocket room handling
        session['demo_user_id'] = 1

        # Use admin user ID for testing
        return render_template('dashboard.html', devices=devices, current_user_id=1, debug_info=debug_info)
        
    except Exception as e:
        logging.error(f"Error loading dashboard: {e}")
        import traceback
        traceback.print_exc()
        return render_template('error.html', message='An error occurred while loading the dashboard')
    finally:
        if conn:
            put_db_connection(conn)

# Add a demo dashboard route for testing
@app.route('/demo')
def demo_dashboard():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Show all devices for demo
        cur.execute("""
            SELECT d.id, d.deviceid, d.name, d.has_relay, ds.source_type
            FROM dust_devices d
            JOIN dust_data_sources ds ON d.data_source_id = ds.id
            ORDER BY d.created_at DESC
        """)
        devices = cur.fetchall()
        
        print(f"[DEMO] Found {len(devices)} devices for demo")
        for device in devices:
            print(f"[DEMO] Device: {device}")
        
        return render_template('dashboard.html', devices=devices, current_user_id=1)  # Use admin user ID
        
    except Exception as e:
        logging.error(f"Error loading demo dashboard: {e}")
        return render_template('error.html', message='An error occurred while loading the demo dashboard')
    finally:
        if conn:
            put_db_connection(conn)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_panel'))
        else:
            return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Fetch user by username
            cur.execute("SELECT id, username, email, password_hash, is_admin FROM dust_users WHERE username = %s", (username,))
            user_data = cur.fetchone()

            if user_data and check_password_hash(user_data['password_hash'], password):
                user = User(
                    id=user_data['id'],
                    username=user_data['username'],
                    email=user_data['email'],
                    is_admin=user_data['is_admin']
                )
                login_user(user)
                # No need to fetch data sources or set session
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error='Invalid username or password')

        except Exception as e:
            logging.error(f"Login error: {e}")
            return render_template('login.html', error='Internal server error')
        finally:
            if conn:
                put_db_connection(conn)

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    return render_template('admin.html')

@app.route('/api/admin/devices', methods=['GET'])
@login_required
def get_devices():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT d.id, d.deviceid, d.name, d.user_id, d.data_source_id, d.has_relay, d.created_at,
                   ds.source_type, ds.broker_url, ds.api_device_id
            FROM dust_devices d
            JOIN dust_data_sources ds ON d.data_source_id = ds.id
            ORDER BY d.id DESC
        """)
        devices = cur.fetchall()
        return jsonify({'devices': devices})
    finally:
        if conn:
            put_db_connection(conn)

@app.route('/api/admin/devices', methods=['POST'])
@login_required
def add_device():
    data = request.get_json()
    deviceid = data.get('deviceid')
    name = data.get('name')
    user_id = data.get('user_id')
    has_relay = data.get('has_relay', False)
    data_source_id = data.get('data_source_id')
    
    if not all([deviceid, name, user_id, data_source_id]):
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Ensure data_source exists
        cur.execute("SELECT id FROM dust_data_sources WHERE id = %s", (data_source_id,))
        if not cur.fetchone():
            return jsonify({'status': 'error', 'message': 'Data source does not exist'}), 400

        # Create device
        cur.execute("""
            INSERT INTO dust_devices (deviceid, name, user_id, has_relay, data_source_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (deviceid, name, user_id, has_relay, data_source_id))
        conn.commit()
        return jsonify({'status': 'success'})
    finally:
        put_db_connection(conn)



@app.route('/api/admin/devices/<int:device_id>', methods=['PUT'])
@login_required
def update_device(device_id):
    data = request.get_json()
    deviceid = data.get('deviceid')
    name = data.get('name')
    user_id = data.get('user_id')
    has_relay = data.get('has_relay', False)
    data_source_id = data.get('data_source_id')
    location = data.get('location', '')
    description = data.get('description', '')

    # Require all fields for update
    if not all([deviceid, name, user_id, data_source_id]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Do not allow changing data_source_id after creation!
        cur.execute("SELECT data_source_id FROM dust_devices WHERE id = %s", (device_id,))
        row = cur.fetchone()
        if row:
            original_source = row[0]
            if str(original_source) != str(data_source_id):
                return jsonify({'status': 'error', 'message': 'Cannot change device data source after creation'}), 400

        # Proceed with update
        cur.execute("""
            UPDATE dust_devices
            SET deviceid = %s, name = %s, user_id = %s, has_relay = %s, location = %s, description = %s
            WHERE id = %s
        """, (deviceid, name, user_id, has_relay, location, description, device_id))
        conn.commit()
        return jsonify({'status': 'success'})
    finally:
        put_db_connection(conn)

@app.route('/api/admin/devices/<int:device_id>', methods=['DELETE'])
@login_required
def delete_device(device_id):
    """Delete a device"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("DELETE FROM dust_sensor_data WHERE device_id = %s", (device_id,))
        cur.execute("DELETE FROM dust_thresholds WHERE device_id = %s", (device_id,))
        cur.execute("DELETE FROM dust_device_alerts WHERE device_id = %s", (device_id,))
        cur.execute("DELETE FROM dust_devices WHERE id = %s", (device_id,))
        conn.commit()

        return jsonify({"status": "success"})
    except Exception as e:
        logging.error(f"Error deleting device: {e}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn:
            put_db_connection(conn)

@app.route('/api/data')
@login_required
def get_data():
    """Get sensor data and history for a specific device"""
    hours = float(request.args.get('hours', 24))
    device_id = request.args.get('deviceid')

    if not device_id:
        return jsonify({"error": "Device ID required"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # For demo/testing purposes, bypass ownership validation
        # TODO: Remove this bypass in production
        cur.execute("SELECT id FROM dust_devices WHERE id = %s", (device_id,))
        if not cur.fetchone():
            return jsonify({"error": "Device not found"}), 404
        logging.info(f"Data access allowed for device {device_id}")

        # Get latest sensor data
        cur.execute("""
            SELECT (timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') as timestamp,
                   pm1, pm2_5, pm4, pm10, tsp
            FROM dust_sensor_data
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        latest = cur.fetchone()

        # Get average over past 15 minutes
        cur.execute("""
            SELECT AVG(pm1) as avg_pm1,
                   AVG(pm2_5) as avg_pm2_5,
                   AVG(pm4) as avg_pm4,
                   AVG(pm10) as avg_pm10,
                   AVG(tsp) as avg_tsp
            FROM dust_sensor_data
            WHERE device_id = %s AND timestamp >= NOW() - INTERVAL '15 minutes'
        """, (device_id,))
        avg_row = cur.fetchone()

        # Get history for chart
        cur.execute("""
            SELECT (timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') as time_bucket,
                   pm1, pm2_5, pm4, pm10, tsp
            FROM dust_sensor_data
            WHERE device_id = %s AND timestamp >= NOW() - INTERVAL %s
            ORDER BY time_bucket ASC
        """, (device_id, f'{hours} hours'))
        history_rows = cur.fetchall()

        # Get thresholds
        cur.execute("""
            SELECT pm1, pm2_5, pm4, pm10, tsp, averaging_window
            FROM dust_thresholds
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        t = cur.fetchone()
        thresholds = {
            "pm1": t['pm1'] if t else 50,
            "pm2.5": t['pm2_5'] if t else 75,
            "pm4": t['pm4'] if t else 100,
            "pm10": t['pm10'] if t else 150,
            "tsp": t['tsp'] if t else 200,
            "averaging_window": t['averaging_window'] if t else 15
        }

        sensor = {}
        if latest:
            sensor = {
                "timestamp": latest["timestamp"].isoformat(),
                "pm1": latest["pm1"] or 0,
                "pm2_5": latest["pm2_5"] or 0,
                "pm4": latest["pm4"] or 0,
                "pm10": latest["pm10"] or 0,
                "tsp": latest["tsp"] or 0,
                "avg_pm1": avg_row["avg_pm1"] or 0,
                "avg_pm2_5": avg_row["avg_pm2_5"] or 0,
                "avg_pm4": avg_row["avg_pm4"] or 0,
                "avg_pm10": avg_row["avg_pm10"] or 0,
                "avg_tsp": avg_row["avg_tsp"] or 0
            }

        history = {
            "timestamps": [r['time_bucket'].isoformat() for r in history_rows],
            "pm1": [float(r['pm1'] or 0) for r in history_rows],
            "pm2_5": [float(r['pm2_5'] or 0) for r in history_rows],
            "pm4": [float(r['pm4'] or 0) for r in history_rows],
            "pm10": [float(r['pm10'] or 0) for r in history_rows],
            "tsp": [float(r['tsp'] or 0) for r in history_rows],
        }

        # Get extended data and history
        logging.info(f"[API] Fetching extended data for device {device_id}")
        extended_row = None
        extended_history_rows = []
        
        try:
            # Get latest extended data
            cur.execute("""
                SELECT *
                FROM dust_extended_data
                WHERE device_id = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (int(device_id),))
            extended_row = cur.fetchone()
            logging.info(f"[API] Extended row found: {extended_row is not None}")
            if extended_row:
                logging.info(f"[API] Extended row data: temperature_c={extended_row.get('temperature_c')}, humidity_percent={extended_row.get('humidity_percent')}")
        except Exception as e:
            logging.error(f"[API] Error fetching extended row: {e}")

        try:
            # Get extended data history for charts - INCLUDE ALL PARAMETERS
            cur.execute("""
                SELECT (timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') as timestamp,
                       temperature_c, humidity_percent, pressure_hpa,
                       voc_ppb, no2_ppb, noise_db, gps_speed_kmh, cloud_cover_percent,
                       lux, uv_index, battery_percent
                FROM dust_extended_data
                WHERE device_id = %s AND timestamp >= NOW() - INTERVAL '%s hours'
                ORDER BY timestamp ASC
            """, (int(device_id), hours))
            extended_history_rows = cur.fetchall()
            logging.info(f"[API] Extended history rows: {len(extended_history_rows)}")
            if extended_history_rows:
                logging.info(f"[API] First extended history row: temperature_c={extended_history_rows[0].get('temperature_c')}, lux={extended_history_rows[0].get('lux')}")
        except Exception as e:
            logging.error(f"[API] Error fetching extended history: {e}")

        response = {
            "sensor": sensor,
            "status": {
                "system": "operational",
                "mode": "auto",
                "relay_state": "OFF",
                "thresholds": thresholds
            },
            "history": history
        }

        # Always include extended data if available
        if extended_row:
            logging.info(f"[API] Adding extended data to response")
            # Convert RealDictCursor row to regular dict for JSON serialization
            response["extended"] = dict(extended_row)
            logging.info(f"[API] Extended data keys: {list(response['extended'].keys())}")

        # Add extended history for charts if available
        if extended_history_rows:
            logging.info(f"[API] Adding extended history to response: {len(extended_history_rows)} rows")
            response["history"]["extended"] = {
                "timestamps": [row['timestamp'].isoformat() for row in extended_history_rows],
                "temperature_c": [float(row['temperature_c'] or 0) for row in extended_history_rows],
                "humidity_percent": [float(row['humidity_percent'] or 0) for row in extended_history_rows],
                "pressure_hpa": [float(row['pressure_hpa'] or 0) for row in extended_history_rows],
                "voc_ppb": [float(row['voc_ppb'] or 0) for row in extended_history_rows],
                "no2_ppb": [float(row['no2_ppb'] or 0) for row in extended_history_rows],
                "noise_db": [float(row['noise_db'] or 0) for row in extended_history_rows],
                "gps_speed_kmh": [float(row['gps_speed_kmh'] or 0) for row in extended_history_rows],
                "cloud_cover_percent": [float(row['cloud_cover_percent'] or 0) for row in extended_history_rows],
                "lux": [float(row['lux'] or 0) for row in extended_history_rows],
                "uv_index": [float(row['uv_index'] or 0) for row in extended_history_rows],
                "battery_percent": [float(row['battery_percent'] or 0) for row in extended_history_rows]
            }

        logging.info(f"[API] Final response keys: {list(response.keys())}")
        logging.info(f"[API] Response has extended: {'extended' in response}")
        logging.info(f"[API] Response history has extended: {'extended' in response.get('history', {})}")

        # Debug: Log extended data values
        if 'extended' in response:
            logging.info(f"[API] Extended data sample values:")
            logging.info(f"  temperature_c: {response['extended'].get('temperature_c')}")
            logging.info(f"  humidity_percent: {response['extended'].get('humidity_percent')}")
            logging.info(f"  pressure_hpa: {response['extended'].get('pressure_hpa')}")
            logging.info(f"  voc_ppb: {response['extended'].get('voc_ppb')}")
            logging.info(f"  no2_ppb: {response['extended'].get('no2_ppb')}")
            logging.info(f"  cloud_cover_percent: {response['extended'].get('cloud_cover_percent')}")

        return jsonify(response)
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        put_db_connection(conn)


@app.route('/api/update_thresholds', methods=['POST'])
@login_required
def update_thresholds():
    """Update threshold values for a device with relay functionality"""
    try:
        thresholds = request.json
        if not thresholds:
            return jsonify({"status": "error", "message": "No data provided"}), 400

        device_id = request.args.get('deviceid')

        validated = {}
        for key in ["pm1", "pm2.5", "pm4", "pm10", "tsp"]:
            value = thresholds.get(key) or thresholds.get(key.replace(".", "_"))
            try:
                validated[key] = float(value) if value is not None else latest_data["status"]["thresholds"][key]
                if validated[key] < 0:
                    return jsonify({
                        "status": "error",
                        "message": f"Invalid value for {key}. Must be positive."
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "status": "error",
                    "message": f"Invalid value for {key}"
                }), 400

        avg_window = int(thresholds.get("averaging_window", 15))
        if avg_window not in [5, 10, 15, 30, 45, 60]:
            return jsonify({
                "status": "error",
                "message": "Invalid averaging window. Must be 5, 10, 15, 30, 45, or 60 minutes."
            }), 400
        validated["averaging_window"] = avg_window

        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO dust_thresholds (device_id, pm1, pm2_5, pm4, pm10, tsp, averaging_window)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                device_id, validated["pm1"], validated["pm2.5"], validated["pm4"],
                validated["pm10"], validated["tsp"], avg_window
            ))
            conn.commit()

            latest_data["status"]["thresholds"].update(validated)
            publish_thresholds(validated, device_id)

            logging.info(f"Thresholds updated for device {device_id}")
            return jsonify({"status": "success", "thresholds": validated})

        except Exception as e:
            logging.error(f"Error saving thresholds: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
        finally:
            if conn:
                put_db_connection(conn)

    except Exception as e:
        logging.error(f"Threshold update error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/relay_control', methods=['POST'])
@login_required
def relay_control():
    """Handle relay control commands from UI (manual ON/OFF or auto mode update)."""
    try:
        data = request.get_json(force=True) or {}
        device_id = data.get('device_id') or data.get('deviceid')
        if not device_id:
            return jsonify({"success": False, "message": "device_id is required"}), 400

        # Validate ownership
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT id, user_id, has_relay FROM dust_devices WHERE id = %s", (device_id,))
            device = cur.fetchone()
            if not device or str(device['user_id']) != str(current_user.id):
                return jsonify({"success": False, "message": "Unauthorized"}), 403

            # Manual relay state
            if 'state' in data and device['has_relay']:
                state = str(data['state']).upper()
                if state not in ['ON', 'OFF']:
                    return jsonify({"success": False, "message": "Invalid state"}), 400
                latest_data["status"]["relay_state"] = state
                # Optionally publish to MQTT (best effort)
                try:
                    control_message = {
                        "command": "all_on" if state == 'ON' else "all_off",
                        "source": "server",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "deviceid": device_id
                    }
                    # Publish on a generic control topic if available
                    for client in mqtt_clients.values():
                        try:
                            client.publish("dustrak/control", json.dumps(control_message), qos=1)
                        except Exception:
                            pass
                except Exception:
                    pass

                # Notify frontend
                try:
                    emit_websocket_update(device_id)
                except Exception:
                    pass

                return jsonify({"success": True})

            # Auto mode threshold update (handled already by update_thresholds endpoint)
            if data.get('mode') == 'auto' and device['has_relay']:
                # No-op here; UI uses dedicated endpoint to update thresholds
                return jsonify({"success": True})

            return jsonify({"success": False, "message": "Unsupported operation or device has no relay"}), 400
        finally:
            if conn:
                put_db_connection(conn)
    except Exception as e:
        logging.error(f"Relay control error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

def publish_thresholds(thresholds, device_id):
    """Publish thresholds to MQTT"""
    if device_id in mqtt_clients and mqtt_clients[device_id].is_connected():
        try:
            message = {
                "thresholds": {
                    "pm1": float(thresholds.get("pm1")),
                    "pm2.5": float(thresholds.get("pm2.5")),
                    "pm4": float(thresholds.get("pm4")),
                    "pm10": float(thresholds.get("pm10")),
                    "tsp": float(thresholds.get("tsp"))
                },
                "averaging_window": int(thresholds.get("averaging_window", 15)),
                "timestamp": datetime.now().isoformat(),
                "deviceid": device_id
            }
            mqtt_clients[device_id].publish("dustrak/control", json.dumps(message), qos=1)
            logging.info("Thresholds published to MQTT")
        except Exception as e:
            logging.error(f"Error publishing thresholds: {e}")

@app.route('/api/admin/users', methods=['GET'])
@login_required
def get_users():
    """Get all users"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, username, email, created_at, is_admin FROM dust_users ORDER BY created_at DESC")
        users = cur.fetchall()
        return jsonify({"users": users})
    except Exception as e:
        logging.error(f"Error fetching users: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            put_db_connection(conn)

@app.route('/api/admin/users', methods=['POST'])
@login_required
def add_user():
    """Add a new user"""
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        is_admin = data.get('is_admin', False)

        if not username or not email or not password:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id FROM dust_users WHERE username = %s OR email = %s", (username, email))
            if cur.fetchone():
                return jsonify({"status": "error", "message": "Username or email already exists"}), 400

            password_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO dust_users (username, email, password_hash, is_admin) VALUES (%s, %s, %s, %s) RETURNING id",
                (username, email, password_hash, is_admin)
            )
            user_id = cur.fetchone()[0]
            conn.commit()

            return jsonify({"status": "success", "user_id": user_id})
        except Exception as e:
            logging.error(f"Error adding user: {e}")
            if conn:
                conn.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
        finally:
            if conn:
                put_db_connection(conn)

    except Exception as e:
        logging.error(f"Error in add_user: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    """Update a user"""
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        is_admin = data.get('is_admin', False)

        if not username or not email:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("SELECT id FROM dust_users WHERE (username = %s OR email = %s) AND id != %s", (username, email, user_id))
            if cur.fetchone():
                return jsonify({"status": "error", "message": "Username or email already exists"}), 400

            if password:
                password_hash = generate_password_hash(password)
                cur.execute(
                    "UPDATE dust_users SET username = %s, email = %s, password_hash = %s, is_admin = %s WHERE id = %s",
                    (username, email, password_hash, is_admin, user_id)
                )
            else:
                cur.execute(
                    "UPDATE dust_users SET username = %s, email = %s, is_admin = %s WHERE id = %s",
                    (username, email, is_admin, user_id)
                )

            conn.commit()
            return jsonify({"status": "success"})
        except Exception as e:
            logging.error(f"Error updating user: {e}")
            if conn:
                conn.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
        finally:
            if conn:
                put_db_connection(conn)

    except Exception as e:
        logging.error(f"Error in update_user: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    

@app.route('/api/device_locations')
@login_required
def get_device_locations():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if current_user.is_admin:
            cur.execute("""
                SELECT DISTINCT ON (d.id)
                    d.id, d.deviceid, COALESCE(d.name, d.deviceid) AS name, d.has_relay,
                    ed.gps_lat, ed.gps_lon, ed.timestamp
                FROM dust_devices d
                LEFT JOIN dust_extended_data ed ON ed.device_id = d.id
                WHERE ed.gps_lat IS NOT NULL AND ed.gps_lon IS NOT NULL
                ORDER BY d.id, ed.timestamp DESC
            """)
        else:
            cur.execute("""
                SELECT DISTINCT ON (d.id)
                    d.id, d.deviceid, COALESCE(d.name, d.deviceid) AS name, d.has_relay,
                    ed.gps_lat, ed.gps_lon, ed.timestamp
                FROM dust_devices d
                LEFT JOIN dust_extended_data ed ON ed.device_id = d.id
                WHERE d.user_id = %s AND ed.gps_lat IS NOT NULL AND ed.gps_lon IS NOT NULL
                ORDER BY d.id, ed.timestamp DESC
            """, (current_user.id,))
        rows = cur.fetchall()
        devices = []
        for r in rows:
            devices.append({
                "id": r["id"],
                "deviceid": r["deviceid"],
                "name": r["name"],
                "has_relay": r["has_relay"],
                "gps_lat": float(r["gps_lat"]) if r["gps_lat"] is not None else None,
                "gps_lon": float(r["gps_lon"]) if r["gps_lon"] is not None else None,
                "last_update": r["timestamp"].isoformat() if r["timestamp"] else None
            })
        return jsonify({"devices": devices})
    except Exception as e:
        logging.error(f"Error fetching device locations: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            put_db_connection(conn)


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Delete a user"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("DELETE FROM dust_devices WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM dust_users WHERE id = %s", (user_id,))
        conn.commit()

        return jsonify({"status": "success"})
    except Exception as e:
        logging.error(f"Error deleting user: {e}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn:
            put_db_connection(conn)

# Add Socket.IO HTTP endpoints for fallback
@app.route('/api/socket/join', methods=['POST'])
@login_required
def socket_join():
    """Handle join room requests via HTTP"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        if device_id:
            # Store user-device association in session or database
            session[f'joined_device_{device_id}'] = True
            logging.info(f"User {current_user.id} joined device {device_id}")
        return jsonify({"status": "success"})
    except Exception as e:
        logging.error(f"Socket join error: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/api/socket/leave', methods=['POST'])
@login_required
def socket_leave():
    """Handle leave room requests via HTTP"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        if device_id and f'joined_device_{device_id}' in session:
            del session[f'joined_device_{device_id}']
            logging.info(f"User {current_user.id} left device {device_id}")
        return jsonify({"status": "success"})
    except Exception as e:
        logging.error(f"Socket leave error: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/stream')
@login_required
def stream():
    """Server-Sent Events stream for real-time updates"""
    def event_stream():
        while True:
            # Send a heartbeat every 30 seconds
            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"
            time.sleep(30)
    
    return Response(event_stream(), mimetype="text/plain")


@app.route('/api/export_csv')
@login_required
def export_csv():
    """Export sensor data as CSV"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    device_id = request.args.get('deviceid')

    if not start_date or not end_date:
        return jsonify({"error": "Both start_date and end_date parameters are required"}), 400

    if not device_id:
        return jsonify({"error": "Device ID parameter is required"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # For demo/testing purposes, temporarily bypass ownership validation
        # TODO: Remove this bypass in production
        try:
            # Validate device ownership (will fail if not logged in properly during demo)
            cur.execute("SELECT id FROM dust_devices WHERE id = %s AND user_id = %s", (device_id, current_user.id))
            if not cur.fetchone():
                # For demo purposes, check if device exists at all
                cur.execute("SELECT id FROM dust_devices WHERE id = %s", (device_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Device not found"}), 404
                # Allow export for demo if device exists (bypass ownership)
                logging.warning(f"Export allowed for demo purposes - device {device_id} owned by different user")
        except Exception as e:
            # If current_user is not available (demo mode), allow export if device exists
            cur.execute("SELECT id FROM dust_devices WHERE id = %s", (device_id,))
            if not cur.fetchone():
                return jsonify({"error": "Device not found"}), 404
            logging.warning(f"Export allowed for demo purposes - auth bypassed for device {device_id}")

        cur.execute("""
            SELECT timestamp, pm1, pm2_5, pm4, pm10, tsp
            FROM dust_sensor_data
            WHERE device_id = %s
            AND timestamp BETWEEN %s AND %s
            ORDER BY timestamp ASC
        """, (device_id, start_date, end_date))

        data = cur.fetchall()

        if not data:
            return jsonify({"error": "No data found for the selected date range"}), 404

        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(["Timestamp", "PM1", "PM2.5", "PM4", "PM10", "TSP"])

        for row in data:
            cw.writerow([
                row[0].isoformat(),
                row[1] or 0,
                row[2] or 0,
                row[3] or 0,
                row[4] or 0,
                row[5] or 0
            ])

        output = make_response(si.getvalue())
        filename = f"dust_data_{device_id}_{start_date}_to_{end_date}.csv"
        output.headers["Content-Disposition"] = f"attachment; filename={filename}"
        output.headers["Content-type"] = "text/csv"

        logging.info(f"CSV exported: {filename}")
        return output

    except Exception as e:
        logging.error(f"Error exporting CSV: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            put_db_connection(conn)

@socketio.on('join')
def handle_join(data):
    device_id = data.get('device_id')
    # For demo mode, use user_id from session or default to 1
    user_id = getattr(current_user, 'get_id', lambda: None)()
    if not user_id:
        # Demo mode - use session or default user ID
        user_id = session.get('demo_user_id', 1)

    if device_id and user_id:
        room_name = f"user_{user_id}_device_{device_id}"
        join_room(room_name)
        logging.info(f'Joined room: {room_name}')
        emit('message', {'status': f'Joined {room_name}'})

@socketio.on('leave')
def handle_leave(data):
    device_id = data.get('device_id')
    # For demo mode, use user_id from session or default to 1
    user_id = getattr(current_user, 'get_id', lambda: None)()
    if not user_id:
        # Demo mode - use session or default user ID
        user_id = session.get('demo_user_id', 1)

    if device_id and user_id:
        room_name = f"user_{user_id}_device_{device_id}"  # Match join format
        leave_room(room_name)
        logging.info(f'Left room: {room_name}')
        emit('message', {'status': f'Left {room_name}'})

def emit_device_update(device_id, data):
    socketio.emit('new_data', data, room=f'device_{device_id}')


# Initialize MQTT clients when module is imported (for Railway)
logging.info("[STARTUP] 🚀 Railway Flask app initialization...")
logging.info("[STARTUP] Environment check:")
logging.info(f"[STARTUP]   RAILWAY_ENVIRONMENT: {os.getenv('RAILWAY_ENVIRONMENT', 'NOT SET')}")
logging.info(f"[STARTUP]   DATABASE_URL: {'SET' if os.getenv('DATABASE_URL') else 'NOT SET'}")
logging.info(f"[STARTUP]   PORT: {os.getenv('PORT', 'NOT SET')}")

logging.info("[STARTUP] 🗄️ Initializing database...")
initialize_database()

logging.info("[STARTUP] 📡 Initializing MQTT clients...")
initialize_mqtt_clients()

logging.info("[STARTUP] ✨ Railway Flask app ready!")

if __name__ == '__main__':
    # Local development startup
    try:
        logging.info("[LOCAL] Starting Flask application for local development...")
        socketio.run(app,
                    host=os.getenv('FLASK_HOST', '0.0.0.0'),
                    port=int(os.getenv('FLASK_PORT', 5000)),
                    debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
    except KeyboardInterrupt:
        logging.info("[LOCAL] Application shutting down...")
    except Exception as e:
        logging.error(f"[LOCAL] 💥 Application startup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
