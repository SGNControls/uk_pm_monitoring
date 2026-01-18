
import json
import ssl
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable
import paho.mqtt.client as mqtt
from dataclasses import dataclass
import threading
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hivemq_client.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class MQTTConfig:
    """MQTT broker configuration"""
    broker_host: str = "77e035371a244f58963809fced8d7b87.s1.eu.hivemq.cloud"  # Free HiveMQ public broker
    broker_port: int = 8883  # TLS port (1883 for non-TLS)
    username: str = "hivemq.webclient.1755269567809"
    password: str = "34xqA,L8!Mo7Yrgi%>TH"
    use_tls: bool = True
    keepalive: int = 60
    client_id: str = f"hivemq_client_{int(time.time())}"
    
    def __post_init__(self):
        """Validate configuration"""
        if self.broker_host.endswith('.hivemq.cloud') and not (self.username and self.password):
            logger.warning("HiveMQ Cloud instance detected but no credentials provided!")
            logger.warning("Please set username and password for HiveMQ Cloud authentication.")
        
        if self.use_tls and self.broker_port == 1883:
            logger.warning("TLS enabled but using non-TLS port 1883. Consider using port 8883.")
        elif not self.use_tls and self.broker_port == 8883:
            logger.warning("TLS disabled but using TLS port 8883. Consider using port 1883.")

class HiveMQRealTimeClient:
    """Real-time MQTT client for HiveMQ broker"""
    
    def __init__(self, config: MQTTConfig, topics: List[str]):
        self.config = config
        self.topics = topics
        self.client = None
        self.connected = False
        self.running = False
        self.message_handlers: Dict[str, Callable] = {}
        self.message_count = 0
        self.last_message_time = None
        
        # Thread-safe storage for latest messages
        self.latest_messages: Dict[str, Dict] = {}
        self.message_lock = threading.Lock()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for when the client receives a CONNACK response"""
        if rc == 0:
            self.connected = True
            logger.info("Successfully connected to HiveMQ broker")
            
            # Subscribe to all configured topics
            for topic in self.topics:
                client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
        else:
            self.connected = False
            logger.error(f"Failed to connect to broker. Return code: {rc}")
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            logger.error(f"Error: {error_messages.get(rc, 'Unknown error')}")
    
    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """Callback for when the client disconnects"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection. Return code: {rc}")
        else:
            logger.info("Disconnected from broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            timestamp = datetime.now(timezone.utc)
            
            self.message_count += 1
            self.last_message_time = timestamp
            
            logger.info(f"Received message on topic '{topic}': {payload[:100]}...")
            
            # Try to parse JSON payload
            try:
                data = json.loads(payload)
                message_data = {
                    'topic': topic,
                    'payload': data,
                    'timestamp': timestamp.isoformat(),
                    'raw_payload': payload
                }
            except json.JSONDecodeError:
                # Handle non-JSON messages
                message_data = {
                    'topic': topic,
                    'payload': payload,
                    'timestamp': timestamp.isoformat(),
                    'raw_payload': payload
                }
            
            # Store latest message for this topic (thread-safe)
            with self.message_lock:
                self.latest_messages[topic] = message_data
            
            # Call custom handler if registered for this topic
            if topic in self.message_handlers:
                self.message_handlers[topic](message_data)
            
            # Call default message processor
            self._process_message(message_data)
            
        except Exception as e:
            logger.error(f"Error processing message from topic {msg.topic}: {e}")
    
    def _process_message(self, message_data: Dict):
        """Default message processor - override or extend as needed"""
        topic = message_data['topic']
        payload = message_data['payload']
        timestamp = message_data['timestamp']
        
        # Example processing for different message types
        if isinstance(payload, dict):
            # Process DustRAK sensor data specifically
            if topic == 'dustrak/data' and 'deviceid' in payload:
                self._process_dustrak_data(payload, topic, timestamp)
            elif 'dustrak' in topic.lower() and 'status' in topic:
                self._process_device_status(payload, topic, timestamp)
            # Process other structured data
            elif 'sensor_data' in payload:
                self._process_sensor_data(payload['sensor_data'], topic, timestamp)
            elif 'device_status' in payload:
                self._process_device_status(payload, topic, timestamp)
            elif 'temperature' in payload or 'humidity' in payload:
                self._process_environmental_data(payload, topic, timestamp)
            else:
                self._process_generic_data(payload, topic, timestamp)
        else:
            # Process raw string data
            logger.info(f"Raw message from {topic}: {payload}")
    
    def _process_dustrak_data(self, data: Dict, topic: str, timestamp: str):
        """Process DustRAK air quality sensor data"""
        device_id = data.get('deviceid', 'Unknown')
        sensor_time = data.get('timestamp_utc', timestamp)
        
        print(f"\n🌬️  === DUSTRAK AIR QUALITY DATA ===")
        print(f"📍 Device ID: {device_id}")
        print(f"⏰ Sensor Time: {sensor_time}")
        print(f"📡 Received: {timestamp}")
        
        # Environmental conditions
        print(f"\n🌡️  ENVIRONMENTAL CONDITIONS:")
        if 'Temperature_C' in data:
            temp = round(float(data['Temperature_C']), 2)
            print(f"   Temperature: {temp}°C ({temp * 9/5 + 32:.1f}°F)")
        
        if 'Humidity_%' in data:
            humidity = round(float(data['Humidity_%']), 1)
            print(f"   Humidity: {humidity}%")
        
        if 'Pressure_hPa' in data:
            pressure = round(float(data['Pressure_hPa']), 1)
            print(f"   Pressure: {pressure} hPa")
        
        if 'Cloud_cover_%' in data:
            cloud_cover = round(float(data['Cloud_cover_%']), 1)
            print(f"   Cloud Cover: {cloud_cover}%")
        
        # Air quality measurements
        print(f"\n🌫️  AIR QUALITY:")
        if 'VOC_ppb' in data:
            voc = round(float(data['VOC_ppb']), 1)
            voc_status = "🟢 Good" if voc < 220 else "🟡 Moderate" if voc < 660 else "🔴 Poor"
            print(f"   VOC: {voc} ppb {voc_status}")
        
        if 'NO2_ppb' in data:
            no2 = round(float(data['NO2_ppb']), 1)
            no2_status = "🟢 Good" if no2 < 53 else "🟡 Moderate" if no2 < 100 else "🔴 Poor"
            print(f"   NO2: {no2} ppb {no2_status}")
        
        # Particulate Matter data
        if 'PM_data' in data and isinstance(data['PM_data'], dict):
            pm_data = data['PM_data']
            print(f"\n💨 PARTICULATE MATTER:")
            
            pm_metrics = [
                ('PM1', 'PM1.0', 12.0, 35.0),
                ('PM2_5', 'PM2.5', 12.0, 35.0),  # EPA standards
                ('PM4', 'PM4.0', 15.0, 40.0),
                ('PM10', 'PM10', 54.0, 154.0),   # EPA standards
                ('TSP_um', 'TSP', 75.0, 150.0)
            ]
            
            for key, display_name, good_threshold, poor_threshold in pm_metrics:
                if key in pm_data:
                    value = round(float(pm_data[key]), 2)
                    if value <= good_threshold:
                        status = "🟢 Good"
                    elif value <= poor_threshold:
                        status = "🟡 Moderate"
                    else:
                        status = "🔴 Unhealthy"
                    print(f"   {display_name}: {value} μg/m³ {status}")
        
        # GPS location
        if 'GPS' in data and isinstance(data['GPS'], dict):
            gps_data = data['GPS']
            print(f"\n📍 LOCATION:")
            if 'Latitude' in gps_data and 'Longitude' in gps_data:
                lat = round(float(gps_data['Latitude']), 6)
                lon = round(float(gps_data['Longitude']), 6)
                print(f"   Coordinates: {lat}, {lon}")
                
            if 'Altitude_m' in gps_data:
                alt = round(float(gps_data['Altitude_m']), 1)
                print(f"   Altitude: {alt} m ({alt * 3.28084:.1f} ft)")
                
            if 'Speed_kmh' in gps_data:
                speed_kmh = round(float(gps_data['Speed_kmh']), 1)
                speed_mph = round(speed_kmh * 0.621371, 1)
                print(f"   Speed: {speed_kmh} km/h ({speed_mph} mph)")
        
        print("=" * 45)

    def _process_sensor_data(self, sensor_data: Dict, topic: str, timestamp: str):
        """Process generic sensor data messages"""
        logger.info(f"[SENSOR DATA] Topic: {topic}")
        for key, value in sensor_data.items():
            logger.info(f"  {key}: {value}")
    
    def _process_device_status(self, status_data: Dict, topic: str, timestamp: str):
        """Process device status messages"""
        logger.info(f"[DEVICE STATUS] Topic: {topic}")
        logger.info(f"  Status: {status_data}")
    
    def _process_environmental_data(self, env_data: Dict, topic: str, timestamp: str):
        """Process environmental sensor data"""
        logger.info(f"[ENVIRONMENTAL] Topic: {topic} at {timestamp}")
        for param, value in env_data.items():
            if param in ['temperature', 'humidity', 'pressure', 'pm2_5', 'pm10']:
                logger.info(f"  {param.upper()}: {value}")
    
    def _process_generic_data(self, data: Dict, topic: str, timestamp: str):
        """Process generic structured data"""
        logger.info(f"[GENERIC DATA] Topic: {topic}")
        if len(data) <= 5:  # Show all fields if small payload
            for key, value in data.items():
                logger.info(f"  {key}: {value}")
        else:
            logger.info(f"  Keys: {list(data.keys())}")
    
    def register_message_handler(self, topic: str, handler: Callable):
        """Register a custom message handler for a specific topic"""
        self.message_handlers[topic] = handler
        logger.info(f"Registered custom handler for topic: {topic}")
    
    def connect(self):
        """Connect to the MQTT broker"""
        try:
            # Create MQTT client (using latest API version)
            self.client = mqtt.Client(
                client_id=self.config.client_id,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                protocol=mqtt.MQTTv311
            )
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Configure authentication if provided
            if self.config.username and self.config.password:
                self.client.username_pw_set(self.config.username, self.config.password)
                logger.info("Authentication configured")
            
            # Configure TLS if required
            if self.config.use_tls:
                context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                self.client.tls_set_context(context)
                logger.info("TLS configured")
            
            # Connect to broker
            logger.info(f"Connecting to {self.config.broker_host}:{self.config.broker_port}")
            self.client.connect(
                self.config.broker_host,
                self.config.broker_port,
                self.config.keepalive
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def start(self):
        """Start the MQTT client loop"""
        if not self.client:
            logger.error("Client not initialized. Call connect() first.")
            return False
        
        self.running = True
        logger.info("Starting MQTT client...")
        
        # Start the network loop in a separate thread
        self.client.loop_start()
        
        # Wait for connection
        timeout = 10  # seconds
        start_time = time.time()
        while not self.connected and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if not self.connected:
            logger.error("Failed to connect within timeout period")
            return False
        
        logger.info("MQTT client started successfully")
        return True
    
    def stop(self):
        """Stop the MQTT client"""
        self.running = False
        if self.client and self.connected:
            for topic in self.topics:
                self.client.unsubscribe(topic)
                logger.info(f"Unsubscribed from topic: {topic}")
            
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client stopped")
    
    def get_latest_message(self, topic: str) -> Optional[Dict]:
        """Get the latest message for a specific topic"""
        with self.message_lock:
            return self.latest_messages.get(topic)
    
    def get_all_latest_messages(self) -> Dict[str, Dict]:
        """Get all latest messages"""
        with self.message_lock:
            return self.latest_messages.copy()
    
    def get_statistics(self) -> Dict:
        """Get client statistics"""
        return {
            'connected': self.connected,
            'total_messages': self.message_count,
            'last_message_time': self.last_message_time.isoformat() if self.last_message_time else None,
            'subscribed_topics': len(self.topics),
            'topics': self.topics
        }
    
    def run_forever(self):
        """Run the client indefinitely with status updates"""
        if not self.start():
            return
        
        try:
            logger.info("Client running... Press Ctrl+C to stop")
            last_stats_time = time.time()
            
            while self.running:
                time.sleep(1)
                
                # Print periodic statistics
                if time.time() - last_stats_time >= 30:  # Every 30 seconds
                    stats = self.get_statistics()
                    logger.info(f"Stats: {stats['total_messages']} messages received, "
                              f"Connected: {stats['connected']}")
                    last_stats_time = time.time()
                
                # Check connection health
                if not self.connected:
                    logger.warning("Connection lost. Attempting to reconnect...")
                    self.connect()
        
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.stop()

# Example usage and custom message handlers
def custom_dustrak_handler(message_data):
    """Custom handler specifically for DustRAK sensor data"""
    payload = message_data['payload']
    topic = message_data['topic']
    
    if not isinstance(payload, dict):
        return
    
    # Extract key metrics for alert checking
    device_id = payload.get('deviceid', 'Unknown')
    
    # Check for air quality alerts
    alerts = []
    
    # VOC alert (>1000 ppb is concerning)
    if 'VOC_ppb' in payload:
        voc = float(payload['VOC_ppb'])
        if voc > 1000:
            alerts.append(f"🚨 HIGH VOC: {voc:.1f} ppb")
    
    # NO2 alert (>200 ppb is concerning)  
    if 'NO2_ppb' in payload:
        no2 = float(payload['NO2_ppb'])
        if no2 > 200:
            alerts.append(f"🚨 HIGH NO2: {no2:.1f} ppb")
    
    # PM2.5 alert (>55 μg/m³ is unhealthy)
    if 'PM_data' in payload and isinstance(payload['PM_data'], dict):
        pm_data = payload['PM_data']
        if 'PM2_5' in pm_data:
            pm25 = float(pm_data['PM2_5'])
            if pm25 > 55:
                alerts.append(f"🚨 HIGH PM2.5: {pm25:.1f} μg/m³")
    
    # Temperature alert (>40°C or <-10°C)
    if 'Temperature_C' in payload:
        temp = float(payload['Temperature_C'])
        if temp > 40:
            alerts.append(f"🌡️ HIGH TEMP: {temp:.1f}°C")
        elif temp < -10:
            alerts.append(f"🧊 LOW TEMP: {temp:.1f}°C")
    
    # Print alerts if any
    if alerts:
        print(f"\n⚠️  === ALERTS FOR DEVICE {device_id} ===")
        for alert in alerts:
            print(f"   {alert}")
        print("=" * 40)
    
    # Log data summary
    timestamp = message_data.get('timestamp', 'Unknown')
    logger.info(f"[DUSTRAK] Device {device_id} - {len(payload)} parameters - {len(alerts)} alerts")

def custom_sensor_handler(message_data):
    """Custom handler for generic sensor data"""
    payload = message_data['payload']
    topic = message_data['topic']
    
    print(f"\n=== CUSTOM SENSOR HANDLER ===")
    print(f"Topic: {topic}")
    print(f"Timestamp: {message_data['timestamp']}")
    
    if isinstance(payload, dict):
        if 'temperature' in payload:
            temp = payload['temperature']
            print(f"🌡️  Temperature: {temp}°C")
        
        if 'humidity' in payload:
            humidity = payload['humidity']
            print(f"💧 Humidity: {humidity}%")
        
        if 'pm2_5' in payload:
            pm25 = payload['pm2_5']
            print(f"🌫️  PM2.5: {pm25} μg/m³")
    
    print("=" * 30)

def main():
    """Main function - customize for your use case"""
    
    # Configuration - UPDATE THESE WITH YOUR HIVEMQ CLOUD CREDENTIALS
    config = MQTTConfig(
        broker_host="77e035371a244f58963809fced8d7b87.s1.eu.hivemq.cloud",
        broker_port=8883,
        use_tls=True,
        username="hivemq.webclient.1755269567809",    # REQUIRED: Replace with your HiveMQ username
        password="34xqA,L8!Mo7Yrgi%>TH",    # REQUIRED: Replace with your HiveMQ password
    )
    
    # Alternative: Use free public broker (no auth required)
    # config = MQTTConfig(
    #     broker_host="broker.hivemq.com",
    #     broker_port=8883,
    #     use_tls=True,
    #     username=None,
    #     password=None,
    # )
    
    # Topics to subscribe to - customize these for your data sources
    topics = [
                 # Environmental data
        "dustrak/data",            # Specific dust sensor data
                     # Test topic
        # Note: Shared subscriptions may not be available on all brokers
        # "$share/group1/shared/topic"
    ]
    
    # Create and configure client
    client = HiveMQRealTimeClient(config, topics)
    
    # Register custom handlers for specific topics
    client.register_message_handler("dustrak/data", custom_dustrak_handler)
    client.register_message_handler("sensors/+/data", custom_sensor_handler)
    
    # Connect and run
    if client.connect():
        client.run_forever()
    else:
        logger.error("Failed to connect to broker")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())