#!/usr/bin/env python3
import json
import os
import pathlib
import sys

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bluesky_client import BlueSkyClient

load_dotenv(ROOT / '.env')


def main():
    client = BlueSkyClient()
    if not client.configured():
        raise RuntimeError('BlueSky client is not fully configured in .env')

    payload = client.get_devices(model=os.getenv('BLUESKY_MODEL_FILTER') or None)
    print('PAYLOAD_TYPE=', type(payload).__name__)
    if isinstance(payload, list):
        print('ITEM_COUNT=', len(payload))
        print(json.dumps(payload[:5], indent=2))
    elif isinstance(payload, dict):
        print('TOP_LEVEL_KEYS=', list(payload.keys()))
        items = payload.get('items') or payload.get('data') or payload.get('devices') or []
        print('ITEM_COUNT=', len(items))
        print(json.dumps(items[:5], indent=2))
    else:
        print(repr(payload))


if __name__ == '__main__':
    main()
