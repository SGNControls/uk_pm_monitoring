from functools import wraps
from flask import jsonify, request
from flask_login import login_required
from psycopg2.extras import RealDictCursor

import aws_app as patched_app
from bluesky_live_client import BlueSkyLiveClient, normalize_flat_telemetry

app = patched_app.app
legacy_app = patched_app.legacy_app
client = BlueSkyLiveClient()

INHG_TO_HPA = 33.8639


def _as_float(value):
    try:
        if value is None or value == '':
            return None
        return float(value)
    except Exception:
        return None


def _compat_voc_ppb(norm):
    # BlueSky returns voc_mgm3. The existing frontend expects voc_ppb.
    # Without species-specific conversion basis, provide a compatibility alias
    # so the current dashboard can render values without frontend changes.
    return norm.get('voc_mgm3')


def _empty_history_with_current(norm):
    ts = norm.get('timestamp')
    return {
        'timestamps': [ts] if ts else [],
        'pm1': [norm.get('pm1')] if norm.get('pm1') is not None else [],
        'pm2_5': [norm.get('pm2_5')] if norm.get('pm2_5') is not None else [],
        'pm4': [norm.get('pm4')] if norm.get('pm4') is not None else [],
        'pm10': [norm.get('pm10')] if norm.get('pm10') is not None else [],
        'tsp': [norm.get('tsp')] if norm.get('tsp') is not None else [],
        'extended': {
            'timestamps': [ts] if ts else [],
            'temperature_c': [norm.get('temperature_c')] if norm.get('temperature_c') is not None else [],
            'humidity_percent': [norm.get('humidity_percent')] if norm.get('humidity_percent') is not None else [],
            'pressure_hpa': [norm.get('pressure_hpa')] if norm.get('pressure_hpa') is not None else [],
            'voc_ppb': [_compat_voc_ppb(norm)] if _compat_voc_ppb(norm) is not None else [],
            'no2_ppb': [norm.get('no2_ppb')] if norm.get('no2_ppb') is not None else [],
            'gps_speed_kmh': [],
            'cloud_cover_percent': [],
            'lux': [],
            'uv_index': [],
            'noise_db': [],
        }
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


def _build_api_response(device_row):
    serial = device_row['deviceid']
    row = client.get_latest_by_serial(serial)
    norm = normalize_flat_telemetry(row)

    pressure_inhg = _as_float(norm.get('pressure_hpa'))
    pressure_hpa = round(pressure_inhg * INHG_TO_HPA, 2) if pressure_inhg is not None else None
    voc_ppb_compat = _compat_voc_ppb(norm)

    sensor = {
        'timestamp': norm.get('timestamp'),
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

    extended = {
        'timestamp': norm.get('timestamp'),
        'temperature_c': norm.get('temperature_c'),
        'humidity_percent': norm.get('humidity_percent'),
        'pressure_hpa': pressure_hpa,
        'voc_ppb': voc_ppb_compat,
        'voc_mgm3': norm.get('voc_mgm3'),
        'no2_ppb': norm.get('no2_ppb'),
        'co2_ppm': norm.get('co2_ppm'),
        'co_ppm': norm.get('co_ppm'),
        'o3_ppb': norm.get('o3_ppb'),
        'so2_ppb': norm.get('so2_ppb'),
        'ch2o_ppb': norm.get('ch2o_ppb'),
        'cloud_cover_percent': None,
        'noise_db': None,
        'lux': None,
        'uv_index': None,
        'battery_percent': None,
        'pm2_5': norm.get('pm2_5'),
        'raw': {
            **(norm.get('raw') or {}),
            'baro_inhg': pressure_inhg,
            'pressure_hpa_compat': pressure_hpa,
            'voc_ppb_compat': voc_ppb_compat,
        },
    }

    # history.extended is intentionally populated with one-point values so existing
    # frontend charts can render for API devices without frontend changes.
    history = _empty_history_with_current({
        **norm,
        'pressure_hpa': pressure_hpa,
        'voc_ppb': voc_ppb_compat,
    })

    return {
        'sensor': sensor,
        'status': {
            'system': 'operational',
            'mode': 'api',
            'relay_state': 'N/A',
            'thresholds': _default_thresholds(),
        },
        'history': history,
        'extended': extended,
    }


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
            return jsonify(_build_api_response(device_row))
        except Exception as exc:
            legacy_app.logging.error(f'BlueSky flat telemetry fetch failed for device {device_id}: {exc}')
            return jsonify({'error': f'BlueSky telemetry fetch failed: {exc}'}), 502

    return _original_get_data(*args, **kwargs)


app.view_functions['get_data'] = get_data_with_bluesky_support
