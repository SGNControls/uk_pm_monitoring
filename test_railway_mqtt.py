#!/usr/bin/env python3
"""
Test MQTT connection using Railway-compatible approach
"""

import os
import paho.mqtt.client as mqtt
import ssl
import time
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MQTT Configuration
MQTT_HOST = "461dec45331a4366882762ab7221c726.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "hivemq.webclient.1765452496255"
MQTT_PASSWORD = "24csnE%<MLVSQ#6d9!zb"
MQTT_TOPIC = "sensor/data"

messages_received = []
connected = False

def on_connect(client, userdata, flags, rc, properties=None):
    global connected
    logger.info(f"[TEST] Connected to broker: {MQTT_HOST}, rc={rc}")
    if rc == 0:
        connected = True
        logger.info("[TEST] ✅ Connection successful!")
        client.subscribe(MQTT_TOPIC, qos=1)
        logger.info(f"[TEST] 📡 Subscribed to topic: {MQTT_TOPIC}")
    else:
        logger.error(f"[TEST] ❌ Connection failed with rc={rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        device_id = payload.get("i") or payload.get("deviceid")

        logger.info(f"[TEST] 📨 Message from device: {device_id}")
        logger.info(f"[TEST] Topic: {msg.topic}, Size: {len(msg.payload)} bytes")

        if device_id == "1225":
            logger.info("[TEST] 🎯 Device 1225 message received!")
            logger.info(f"[TEST] Keys: {list(payload.keys())}")

            if "e" in payload and "pm" in payload:
                logger.info("[TEST] ✅ Compact format detected")
                logger.info(f"[TEST] Environmental: {len(payload['e'])} values")
                logger.info(f"[TEST] PM: {len(payload['pm'])} values")

        messages_received.append({
            'timestamp': time.time(),
            'device_id': device_id,
            'payload': payload
        })

    except Exception as e:
        logger.error(f"[TEST] Error processing message: {e}")

def test_mqtt_connection():
    """Test MQTT connection with Railway-compatible settings"""
    logger.info("🧪 Testing Railway-compatible MQTT connection...")
    logger.info(f"📍 Broker: {MQTT_HOST}:{MQTT_PORT}")
    logger.info("=" * 60)

    try:
        # Create MQTT client (Railway compatible)
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            userdata={"test": True}
        )

        # Set authentication
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        logger.info(f"[TEST] Auth configured for user: {MQTT_USERNAME}")

        # Configure TLS for Railway
        import ssl
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        client.tls_set_context(context)

        # Set callbacks
        client.on_connect = on_connect
        client.on_message = on_message

        # Set connection parameters
        client.max_inflight_messages_set(10)
        client.max_queued_messages_set(100)

        logger.info("[TEST] 🔌 Attempting connection...")
        client.connect(MQTT_HOST, MQTT_PORT, 60)

        # Start loop
        client.loop_start()

        # Wait for connection
        timeout = 15
        start_time = time.time()
        while not connected and (time.time() - start_time) < timeout:
            time.sleep(0.5)
            logger.info(f"[TEST] Waiting for connection... {int(time.time() - start_time)}/{timeout}s")

        if not connected:
            logger.error("[TEST] ❌ Failed to connect within timeout")
            client.loop_stop()
            return False

        logger.info("[TEST] ⏳ Listening for messages (60 seconds)...")

        # Listen for 60 seconds
        listen_duration = 60
        start_listen = time.time()

        while (time.time() - start_listen) < listen_duration:
            elapsed = int(time.time() - start_listen)
            if elapsed % 10 == 0 and elapsed > 0:
                logger.info(f"[TEST] Still listening... {elapsed}/{listen_duration}s")
            time.sleep(1)

        # Stop and cleanup
        client.loop_stop()
        client.disconnect()

        # Analyze results
        logger.info("\n📊 Test Results:")
        logger.info("=" * 30)

        device_1225_messages = [msg for msg in messages_received if msg['device_id'] == '1225']

        logger.info(f"📨 Total messages received: {len(messages_received)}")
        logger.info(f"🎯 Device 1225 messages: {len(device_1225_messages)}")

        if device_1225_messages:
            logger.info("✅ SUCCESS: Device 1225 is sending data!")
            latest_msg = max(device_1225_messages, key=lambda x: x['timestamp'])
            age = time.time() - latest_msg['timestamp']
            logger.info(f"      Latest message: {age:.1f} seconds ago")
            return True
        else:
            logger.info("❌ No messages from device 1225")
            if messages_received:
                other_devices = set(msg['device_id'] for msg in messages_received if msg['device_id'] != '1225')
                logger.info(f"📱 Other active devices: {list(other_devices)}")
            else:
                logger.info("🤷 No messages from any devices")
            return False

    except Exception as e:
        logger.error(f"[TEST] Test failed with error: {e}")
        return False

if __name__ == '__main__':
    success = test_mqtt_connection()
    logger.info(f"\n🏁 Test {'PASSED' if success else 'FAILED'}")
    if success:
        logger.info("🎉 MQTT connection working - device should be visible in dashboard!")
    else:
        logger.info("🔍 MQTT connection issue - check Railway logs for MQTT client startup")
