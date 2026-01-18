import paho.mqtt.client as mqtt
import ssl
import time
import json

# Same config as user's script
MQTT_HOST = "461dec45331a4366882762ab7221c726.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "hivemq.webclient.1765452496255"
MQTT_PASSWORD = "24csnE%<MLVSQ#6d9!zb"
MQTT_TOPIC = "sensor/data"

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[TEST] Connected with result code: {rc}")
    if rc == 0:
        print("[TEST] Successfully connected to MQTT broker")
        client.subscribe(MQTT_TOPIC)
        print(f"[TEST] Subscribed to {MQTT_TOPIC}")
    else:
        print(f"[TEST] Connection failed with code: {rc}")

def on_message(client, userdata, msg):
    print(f"[TEST] Received message on topic: {msg.topic}")
    print(f"[TEST] Payload: {msg.payload.decode()}")

def test_connection():
    print("[TEST] Testing MQTT connection...")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # Try the same TLS config as user's script
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print(f"[TEST] Connecting to {MQTT_HOST}:{MQTT_PORT}")
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()

        # Wait a bit to see if connection works
        time.sleep(5)

        # Try to publish a test message
        test_payload = {
            "i": "test_device",
            "t": "2026-01-18T12:00:00Z",
            "e": [25.0, 50.0, 1013.0, 0.0, 100.0, 25000, 0.5, 60.0],
            "pm": [10.0, 15.0, 20.0, 25.0, 30.0],
            "g": {"lat": None, "lon": None, "alt": None, "spd": None}
        }

        client.publish(MQTT_TOPIC, json.dumps(test_payload))
        print(f"[TEST] Published test message to {MQTT_TOPIC}")

        # Wait a bit more to see if we receive it
        time.sleep(10)

    except Exception as e:
        print(f"[TEST] Connection error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    test_connection()
