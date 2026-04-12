#!/usr/bin/env python3
import json
import os
import pathlib
import sys

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bluesky_client import BlueSkyClient, normalize_bluesky_snapshot

load_dotenv(ROOT / '.env')

TARGET_SERIAL = os.getenv('BLUESKY_TARGET_SERIAL', '').strip() or '81442510005'
TARGET_DEVICE_ID = os.getenv('BLUESKY_TARGET_DEVICE_ID', '').strip()


def main():
    client = BlueSkyClient()
    if not client.configured():
        raise RuntimeError('BlueSky client is not fully configured in .env')

    device_id = TARGET_DEVICE_ID
    if not device_id:
        devices = client.get_devices()
        items = devices if isinstance(devices, list) else devices.get('items') or devices.get('data') or devices.get('devices') or []
        match = None
        for item in items:
            if str(item.get('serial') or item.get('serialNumber') or '').strip() == TARGET_SERIAL:
                match = item
                break
        if not match:
            raise RuntimeError(f'No BlueSky device found for serial {TARGET_SERIAL}')
        device_id = str(match.get('device_id') or match.get('deviceId') or match.get('id')).strip()
        print('MATCHED_DEVICE=', json.dumps(match, indent=2))

    snapshot = client.get_device_snapshot(device_id)
    print('RAW_SNAPSHOT=')
    print(json.dumps(snapshot, indent=2))
    print('\nNORMALIZED=')
    print(json.dumps(normalize_bluesky_snapshot(snapshot), indent=2))


if __name__ == '__main__':
    main()
