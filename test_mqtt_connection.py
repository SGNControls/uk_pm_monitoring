#!/usr/bin/env python3
"""
Test MQTT connection to HiveMQ broker for device 1225
"""

import paho.mqtt.client as mqtt
import ssl
import time
import json

# MQTT Configuration from device script
MQTT_HOST = "461dec45331a4366882762ab7221c726.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "hivemq.webclient.1765452496255"
MQTT_PASSWORD = "24csnE%<MLVSQ#6d9!zb"
MQTT_TOPIC = "sensor/data"

# Global variables
messages_received = []
connected = False

def on_connect(client, userdata, flags, rc, properties=None):
    global connected
    print(f"🔌 MQTT Connection result: {rc}")
    if rc == 0:
        connected = True
        print("✅ Connected to HiveMQ broker!")
        client.subscribe(MQTT_TOPIC, qos=1)
        print(f"📡 Subscribed to topic: {MQTT_TOPIC}")
    else:
        print(f"❌ Connection failed with code: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        device_id = payload.get("i") or payload.get("deviceid")

        print("📨 Received message:")
        print(f"   Topic: {msg.topic}")
        print(f"   Device ID: {device_id}")
        print(f"   Payload size: {len(msg.payload)} bytes")

        if device_id == "1225":
            print("   🎯 This is device 1225!")
            print("   📊 Data keys:")
            print(f"      {list(payload.keys())}")
            if "e" in payload:
                print(f"      Environmental data: {len(payload['e'])} values")
            if "pm" in payload:
                print(f"      PM data: {len(payload['pm'])} values")
            if "g" in payload:
                print(f"      GPS data: {payload['g']}")
        else:
            print(f"   📱 Other device: {device_id}")

        messages_received.append({
            'timestamp': time.time(),
            'device_id': device_id,
            'topic': msg.topic,
            'payload': payload
        })

        print()

    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
    except Exception as e:
        print(f"❌ Error processing message: {e}")

def test_mqtt_connection():
    """Test MQTT connection and listen for messages"""
    print("🧪 Testing MQTT connection to HiveMQ...")
    print(f"📍 Broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f"👤 Username: {MQTT_USERNAME}")
    print(f"📡 Topic: {MQTT_TOPIC}")
    print("=" * 60)

    # Create MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # Configure TLS
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    client.tls_insecure_set(False)  # Use secure TLS

    # Set callbacks
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print("🔌 Connecting to broker...")
        client.connect(MQTT_HOST, MQTT_PORT, 60)

        # Start the loop
        client.loop_start()

        # Wait for connection
        timeout = 10
        start_time = time.time()
        while not connected and (time.time() - start_time) < timeout:
            time.sleep(0.5)

        if not connected:
            print("❌ Failed to connect within timeout period")
            return False

        print("⏳ Listening for messages... (Press Ctrl+C to stop)")
        print("   Will listen for 30 seconds to capture device 1225 messages")
        print()

        # Listen for messages for 30 seconds
        listen_duration = 30
        start_listen = time.time()

        while (time.time() - start_listen) < listen_duration:
            time.sleep(1)
            elapsed = int(time.time() - start_listen)
            if elapsed % 5 == 0 and elapsed > 0:
                print(f"⏰ Still listening... {elapsed}/{listen_duration} seconds")

        # Stop the loop
        client.loop_stop()
        client.disconnect()

        print("\n📊 Test Results:")
        print("=" * 30)

        device_1225_messages = [msg for msg in messages_received if msg['device_id'] == '1225']

        print(f"📨 Total messages received: {len(messages_received)}")
        print(f"🎯 Device 1225 messages: {len(device_1225_messages)}")

        if device_1225_messages:
            print("✅ Device 1225 is ACTIVE and publishing data!")
            latest_msg = max(device_1225_messages, key=lambda x: x['timestamp'])
            age = time.time() - latest_msg['timestamp']
            print(f"      Latest message: {age:.1f} seconds ago")
            return True
        else:
            print("❌ No messages from device 1225 received")
            if messages_received:
                print("📱 Other devices active:")
                other_devices = set(msg['device_id'] for msg in messages_received if msg['device_id'] != '1225')
                for device in other_devices:
                    count = len([msg for msg in messages_received if msg['device_id'] == device])
                    print(f"   - Device {device}: {count} messages")
            else:
                print("🤷 No messages from any devices - broker might be quiet")
            return False

    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        client.loop_stop()
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == '__main__':
    success = test_mqtt_connection()
    print(f"\n🏁 Test {'PASSED' if success else 'FAILED'}")
    if success:
        print("🎉 Device 1225 is publishing data correctly!")
    else:
        print("🔍 Device 1225 is not publishing or Flask app can't receive data")
