import app as legacy_app
from datetime import datetime, timezone
import json

app = legacy_app.app
socketio = legacy_app.socketio


def get_mqtt_client_for_device(device_id):
    """Resolve MQTT client by device -> data_source_id mapping."""
    conn = None
    try:
        conn = legacy_app.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT data_source_id FROM dust_devices WHERE id = %s", (device_id,))
        row = cur.fetchone()
        if not row:
            return None
        data_source_id = row[0]
        return legacy_app.mqtt_clients.get(data_source_id)
    except Exception as exc:
        legacy_app.logging.error(f"Error resolving MQTT client for device {device_id}: {exc}")
        return None
    finally:
        if conn:
            legacy_app.put_db_connection(conn)



def fixed_process_sensor_data(payload, device_id, timestamp, data_source_id):
    """Patched version of process_sensor_data with payload-safe extended check."""
    conn = None
    try:
        conn = legacy_app.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, has_relay
            FROM dust_devices
            WHERE deviceid = %s AND data_source_id = %s
            """,
            (device_id, data_source_id),
        )
        device = cur.fetchone()
        if not device:
            legacy_app.logging.warning(f"Unauthorized device creation attempted: {device_id}")
            return

        device_id_db, user_id, has_relay = device
        pm_data = payload.get("PM_data", {})
        db_record = {
            "timestamp": timestamp,
            "device_id": device_id_db,
            "data_source_id": data_source_id,
            "pm1": float(pm_data.get("PM1", 0)) * 1000,
            "pm2_5": float(pm_data.get("PM2_5", 0)) * 1000,
            "pm4": float(pm_data.get("PM4", 0)) * 1000,
            "pm10": float(pm_data.get("PM10", 0)) * 1000,
            "tsp": float(pm_data.get("TSP_um", 0)) * 1000,
        }
        cur.execute(
            """
            INSERT INTO dust_sensor_data
            (timestamp, device_id, data_source_id, pm1, pm2_5, pm4, pm10, tsp)
            VALUES (%(timestamp)s, %(device_id)s, %(data_source_id)s, %(pm1)s, %(pm2_5)s, %(pm4)s, %(pm10)s, %(tsp)s)
            """,
            db_record,
        )
        conn.commit()

        if has_relay:
            legacy_app.process_thresholds(device_id_db, user_id)

        legacy_app.emit_websocket_update(device_id_db)

        if hasattr(payload, 'get') and (
            'e' in payload or 'extended' in payload or 'Temperature_C' in payload
        ):
            legacy_app.emit_extended_websocket_update(device_id_db)
    except Exception as exc:
        legacy_app.logging.error(f"Error processing sensor data: {exc}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            legacy_app.put_db_connection(conn)



def fixed_publish_thresholds(thresholds, device_id):
    client = get_mqtt_client_for_device(device_id)
    if client and client.is_connected():
        try:
            message = {
                "thresholds": {
                    "pm1": float(thresholds.get("pm1")),
                    "pm2.5": float(thresholds.get("pm2.5")),
                    "pm4": float(thresholds.get("pm4")),
                    "pm10": float(thresholds.get("pm10")),
                    "tsp": float(thresholds.get("tsp")),
                },
                "averaging_window": int(thresholds.get("averaging_window", 15)),
                "timestamp": datetime.now().isoformat(),
                "deviceid": device_id,
            }
            client.publish("dustrak/control", json.dumps(message), qos=1)
            legacy_app.logging.info("Thresholds published to MQTT")
        except Exception as exc:
            legacy_app.logging.error(f"Error publishing thresholds: {exc}")



def fixed_process_thresholds(device_id, user_id):
    conn = None
    try:
        conn = legacy_app.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
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
            SELECT AVG(pm1), AVG(pm2_5), AVG(pm4), AVG(pm10), AVG(tsp)
            FROM recent_data
            """,
            (device_id, device_id),
        )
        averages = cur.fetchone()

        cur.execute(
            """
            SELECT pm1, pm2_5, pm4, pm10, tsp, averaging_window
            FROM dust_thresholds
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (device_id,),
        )
        threshold_row = cur.fetchone()
        thresholds = {
            "pm1": threshold_row[0] if threshold_row else legacy_app.latest_data["status"]["thresholds"]["pm1"],
            "pm2.5": threshold_row[1] if threshold_row else legacy_app.latest_data["status"]["thresholds"]["pm2.5"],
            "pm4": threshold_row[2] if threshold_row else legacy_app.latest_data["status"]["thresholds"]["pm4"],
            "pm10": threshold_row[3] if threshold_row else legacy_app.latest_data["status"]["thresholds"]["pm10"],
            "tsp": threshold_row[4] if threshold_row else legacy_app.latest_data["status"]["thresholds"]["tsp"],
            "averaging_window": threshold_row[5] if threshold_row else 15,
        }

        trigger_relay = False
        if averages and any([
            averages[0] and averages[0] > thresholds["pm1"],
            averages[1] and averages[1] > thresholds["pm2.5"],
            averages[2] and averages[2] > thresholds["pm4"],
            averages[3] and averages[3] > thresholds["pm10"],
            averages[4] and averages[4] > thresholds["tsp"],
        ]):
            trigger_relay = True
            legacy_app.create_alert(device_id, "threshold_exceeded", "One or more thresholds exceeded", thresholds, averages)

        control_message = {
            "command": "all_on" if trigger_relay else "all_off",
            "source": "server",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "deviceid": device_id,
        }
        client = get_mqtt_client_for_device(device_id)
        if client and client.is_connected():
            client.publish("dustrak/control", json.dumps(control_message), qos=1)
    except Exception as exc:
        legacy_app.logging.error(f"Error processing thresholds: {exc}")
    finally:
        if conn:
            legacy_app.put_db_connection(conn)


# Apply runtime patches
legacy_app.process_sensor_data = fixed_process_sensor_data
legacy_app.publish_thresholds = fixed_publish_thresholds
legacy_app.process_thresholds = fixed_process_thresholds
