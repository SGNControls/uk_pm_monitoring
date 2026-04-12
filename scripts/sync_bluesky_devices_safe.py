#!/usr/bin/env python3
import os
import sys
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from bluesky_client import BlueSkyClient
import app as legacy_app

load_dotenv(ROOT / '.env')

MODEL_FILTER = os.getenv('BLUESKY_MODEL_FILTER', '').strip() or None
ASSIGN_USER_ID = os.getenv('BLUESKY_ASSIGN_USER_ID', '').strip()
ASSIGN_MODE = os.getenv('BLUESKY_ASSIGN_MODE', 'first_admin').strip().lower()


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
            """
            SELECT id FROM dust_data_sources
            WHERE source_type = 'api' AND api_device_id = %s
            """,
            (api_device_id,),
        )
        row = cur.fetchone()
        if row:
            return row['id']

        cur.execute(
            """
            INSERT INTO dust_data_sources (source_type, api_device_id, description)
            VALUES ('api', %s, %s)
            RETURNING id
            """,
            (api_device_id, description),
        )
        return row['id'] if row else cur.fetchone()['id']


def ensure_device(conn, *, deviceid: str, name: str, user_id: int, data_source_id: int):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id FROM dust_devices
            WHERE deviceid = %s AND data_source_id = %s
            """,
            (deviceid, data_source_id),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                """
                UPDATE dust_devices
                SET name = %s, user_id = %s
                WHERE id = %s
                """,
                (name, user_id, row['id']),
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


def main():
    client = BlueSkyClient()
    if not client.configured():
        raise RuntimeError(
            'BlueSky client is not fully configured. Set BLUESKY_TOKEN_URL, BLUESKY_API_BASE_URL, BLUESKY_CLIENT_ID, BLUESKY_CLIENT_SECRET in .env'
        )

    conn = legacy_app.get_db_connection()
    try:
        user_id = resolve_target_user_id(conn)
        devices_payload = client.get_devices(model=MODEL_FILTER)
        items = devices_payload.get('items') or devices_payload.get('data') or []
        synced = []

        for item in items:
            api_device_id = str(item.get('id') or item.get('deviceId') or '').strip()
            serial_number = str(item.get('serialNumber') or item.get('serial') or '').strip()
            friendly_name = str(item.get('friendlyName') or item.get('name') or serial_number or api_device_id).strip()
            model = str(item.get('model') or '').strip()

            if not api_device_id:
                continue

            description = f'BlueSky API device | model={model} | serial={serial_number}'.strip()
            source_id = ensure_api_source(conn, api_device_id, description)
            deviceid = serial_number or api_device_id
            ensure_device(
                conn,
                deviceid=deviceid,
                name=friendly_name,
                user_id=user_id,
                data_source_id=source_id,
            )
            synced.append({
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
        legacy_app.put_db_connection(conn)


if __name__ == '__main__':
    main()
