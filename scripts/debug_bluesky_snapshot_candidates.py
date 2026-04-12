#!/usr/bin/env python3
import json
import os
import pathlib
import sys

from dotenv import load_dotenv
import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bluesky_client import BlueSkyClient

load_dotenv(ROOT / '.env')

TARGET_SERIAL = os.getenv('BLUESKY_TARGET_SERIAL', '').strip() or '81442510005'
TARGET_DEVICE_ID = os.getenv('BLUESKY_TARGET_DEVICE_ID', '').strip()


def main():
    client = BlueSkyClient()
    if not client.configured():
        raise RuntimeError('BlueSky client is not fully configured in .env')

    device_id = TARGET_DEVICE_ID
    serial = TARGET_SERIAL

    devices = client.get_devices()
    items = devices if isinstance(devices, list) else devices.get('items') or devices.get('data') or devices.get('devices') or []

    match = None
    for item in items:
        if str(item.get('serial') or item.get('serialNumber') or '').strip() == serial:
            match = item
            break
    if not match:
        raise RuntimeError(f'No BlueSky device found for serial {serial}')

    if not device_id:
        device_id = str(match.get('device_id') or match.get('deviceId') or match.get('id')).strip()

    print('MATCHED_DEVICE=')
    print(json.dumps(match, indent=2))

    token = client._get_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
    }
    base = client.api_base_url.rstrip('/')

    candidates = [
        f'{base}/devices/{device_id}/snapshot',
        f'{base}/devices/{device_id}/snapshots/latest',
        f'{base}/devices/{device_id}/latest',
        f'{base}/devices/{device_id}/telemetry/latest',
        f'{base}/devices/{device_id}/measurements/latest',
        f'{base}/devices/{device_id}/data/latest',
        f'{base}/devices/{serial}/snapshot',
        f'{base}/devices/{serial}/snapshots/latest',
        f'{base}/devices/{serial}/latest',
        f'{base}/devices/{serial}/telemetry/latest',
        f'{base}/device/{device_id}/snapshot',
        f'{base}/snapshot/{device_id}',
    ]

    for url in candidates:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            print('\nURL=', url)
            print('STATUS=', resp.status_code)
            text = resp.text[:2000]
            try:
                payload = resp.json()
                print(json.dumps(payload, indent=2)[:4000])
            except Exception:
                print(text)
            if resp.ok:
                print('\nFIRST_SUCCESS_URL=', url)
                return
        except Exception as exc:
            print('\nURL=', url)
            print('ERROR=', repr(exc))

    print('\nNo candidate snapshot endpoint succeeded.')


if __name__ == '__main__':
    main()
