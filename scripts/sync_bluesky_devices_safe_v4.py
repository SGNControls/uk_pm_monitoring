#!/usr/bin/env python3
import json
import os
import pathlib
import sys

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bluesky_client import BlueSkyClient

load_dotenv(ROOT / '.env')

MODEL_FILTER = os.getenv('BLUESKY_MODEL_FILTER', '').strip() or None
ASSIGN_USER_ID = os.getenv('BLUESKY_ASSIGN_USER_ID', '').strip()
ASSIGN_MODE = os.getenv('BLUESKY_ASSIGN_MODE', 'first_admin').strip().lower()
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()


def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=int(os.getenv('DB_PORT', '5432')),
    )


def resolve_target_user_id(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if ASSIGN_USER_ID:
            cur.execute('SELECT id FROM dust_users WHERE id = %s', (ASSIGN_USER_ID,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f'BLUESKY_ASSIGN_USER_ID={ASSIGN_USER_ID} not found in dust_users')
            return row['id']

        if ASSIGN_MODE == 'first_admin':
            cur.execute('SELECT id FROM dust_users WHERE is_admin = TRUE ORDER BY id ASC LIMIT 1')
            row = cur.fetchone()
            if row:
                return row['id']

        cur.execute('SELECT id FROM dust_users ORDER BY id ASC LIMIT 1')
        row = cur.fetchone()
        if row:
            return row['id']

    raise RuntimeError('No dashboard user found in dust_users. Create at least one user before syncing BlueSky devices.')


def ensure_api_source(conn, api_device_id: str, description: str):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM dust_data_sources WHERE source_type = 'api' AND api_device_id = %s",
            (api_device_id,),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE dust_data_sources SET description = %s WHERE id = %s",
                (description, row['id']),
            )
            return row['id']

        cur.execute(
            """
            INSERT INTO dust_data_sources (source_type, api_device_id, description)
            VALUES ('api', %s, %s)
            RETURNING id
            """,
            (api_device_id, description),
        )
        return cur.fetchone()['id']


def ensure_device(conn, *, deviceid: str, name: str, user_id: int, data_source_id: int):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM dust_devices WHERE data_source_id = %s",
            (data_source_id,),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                """
                UPDATE dust_devices
                SET deviceid = %s, name = %s, user_id = %s
                WHERE id = %s
                """,
                (deviceid, name, user_id, row['id']),
            )
            return row['id']

        cur.execute(
            """
            INSERT INTO dust_devices (deviceid, name, user_id, has_relay, data_source_id)
            VALUES (%s, %s, %s, FALSE, %s)
            RETURNING id
            """,
            (deviceid, name, user_id, data_source_id),
        )
        return cur.fetchone()['id']


def extract_items(devices_payload):
    if isinstance(devices_payload, list):
        return devices_payload
    if isinstance(devices_payload, dict):
        return devices_payload.get('items') or devices_payload.get('data') or devices_payload.get('devices') or []
    raise RuntimeError(f'Unsupported BlueSky device payload type: {type(devices_payload).__name__}')


def main():
    client = BlueSkyClient()
    if not client.configured():
        raise RuntimeError(
            'BlueSky client is not fully configured. Set BLUESKY_TOKEN_URL, BLUESKY_API_BASE_URL, BLUESKY_CLIENT_ID, BLUESKY_CLIENT_SECRET in .env'
        )

    conn = get_db_connection()
    try:
        user_id = resolve_target_user_id(conn)
        devices_payload = client.get_devices(model=MODEL_FILTER)
        items = extract_items(devices_payload)
        synced = []

        for item in items:
            api_device_id = str(item.get('device_id') or item.get('deviceId') or item.get('id') or '').strip()
            serial_number = str(item.get('serial') or item.get('serialNumber') or '').strip()
            metadata = item.get('metadata') or {}
            friendly_name = str(metadata.get('friendlyName') or item.get('friendlyName') or item.get('name') or serial_number or api_device_id).strip()
            model = str(item.get('model') or '').strip()
            status = str(item.get('status') or '').strip()

            if not api_device_id:
                continue

            description = f'BlueSky API device | model={model} | serial={serial_number} | status={status}'.strip()
            source_id = ensure_api_source(conn, api_device_id, description)
            deviceid = serial_number or api_device_id
            device_pk = ensure_device(
                conn,
                deviceid=deviceid,
                name=friendly_name,
                user_id=user_id,
                data_source_id=source_id,
            )
            synced.append({
                'db_device_id': device_pk,
                'api_device_id': api_device_id,
                'deviceid': deviceid,
                'friendly_name': friendly_name,
                'model': model,
                'serial_number': serial_number,
                'data_source_id': source_id,
                'user_id': user_id,
            })

        conn.commit()
        print(json.dumps({'synced_count': len(synced), 'devices': synced}, indent=2))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
