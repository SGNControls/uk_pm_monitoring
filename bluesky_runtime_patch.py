from functools import wraps
from flask import jsonify, request
from flask_login import login_required
from psycopg2.extras import RealDictCursor

import aws_app as patched_app
from bluesky_client import BlueSkyClient, normalize_bluesky_snapshot

app = patched_app.app
legacy_app = patched_app.legacy_app
client = BlueSkyClient()


def _serialize_timestamp(value):
    return value.isoformat() if hasattr(value, 'isoformat') else value


def _empty_history():
    return {
        'timestamps': [],
        'pm1': [],
        'pm2_5': [],
        'pm4': [],
        'pm10': [],
        'tsp': [],
    }


def _default_thresholds():
    return {
        'pm1': 50,
        'pm2.5': 75,
        'pm4': 100,
        'pm10': 150,
        'tsp': 200,
        'averaging_window': 15,
    }


def _get_device_and_source(device_id):
    conn = None
    try:
        conn = legacy_app.get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT d.id, d.deviceid, d.name, d.user_id, d.data_source_id,
                   ds.source_type, ds.api_device_id, ds.description
            FROM dust_devices d
            JOIN dust_data_sources ds ON d.data_source_id = ds.id
            WHERE d.id = %s
            """,
            (device_id,),
        )
        return cur.fetchone()
    finally:
        if conn:
            legacy_app.put_db_connection(conn)


def _build_bluesky_response(device_row):
    snapshot = client.get_device_snapshot(device_row['api_device_id'])
    norm = normalize_bluesky_snapshot(snapshot)

    sensor = {
        'timestamp': _serialize_timestamp(norm.get('timestamp')),
        'pm1': norm.get('pm1') or 0,
        'pm2_5': norm.get('pm2_5') or 0,
        'pm4': norm.get('pm4') or 0,
        'pm10': norm.get('pm10') or 0,
        'tsp': norm.get('tsp') or 0,
        'avg_pm1': norm.get('pm1') or 0,
        'avg_pm2_5': norm.get('pm2_5') or 0,
        'avg_pm4': norm.get('pm4') or 0,
        'avg_pm10': norm.get('pm10') or 0,
        'avg_tsp': norm.get('tsp') or 0,
    }

    response = {
        'sensor': sensor,
        'status': {
            'system': 'operational',
            'mode': 'api',
            'relay_state': 'N/A',
            'thresholds': _default_thresholds(),
        },
        'history': _empty_history(),
        'extended': {
            'timestamp': _serialize_timestamp(norm.get('timestamp')),
            'temperature_c': norm.get('temperature_c'),
            'humidity_percent': norm.get('humidity_percent'),
            'pressure_hpa': norm.get('pressure_hpa'),
            'gps_lat': norm.get('gps_lat'),
            'gps_lon': norm.get('gps_lon'),
            'raw': norm.get('raw'),
        },
    }
    return response


_original_get_data = app.view_functions.get('get_data')


@login_required
@wraps(_original_get_data)
def get_data_with_bluesky_support(*args, **kwargs):
    device_id = request.args.get('deviceid')
    if not device_id:
        return jsonify({'error': 'Device ID required'}), 400

    device_row = _get_device_and_source(device_id)
    if not device_row:
        return jsonify({'error': 'Device not found'}), 404

    if device_row['source_type'] == 'api':
        try:
            return jsonify(_build_bluesky_response(device_row))
        except Exception as exc:
            legacy_app.logging.error(f'BlueSky snapshot fetch failed for device {device_id}: {exc}')
            return jsonify({'error': f'BlueSky snapshot fetch failed: {exc}'}), 502

    return _original_get_data(*args, **kwargs)


app.view_functions['get_data'] = get_data_with_bluesky_support
