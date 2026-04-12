import os
import time
from typing import Any, Dict, List, Optional

import requests


class BlueSkyLiveClient:
    def __init__(self):
        self.token_url = os.getenv('BLUESKY_TOKEN_URL', '').strip()
        self.api_base_url = os.getenv('BLUESKY_API_BASE_URL', '').strip().rstrip('/')
        self.client_id = os.getenv('BLUESKY_CLIENT_ID', '').strip()
        self.client_secret = os.getenv('BLUESKY_CLIENT_SECRET', '').strip()
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def configured(self) -> bool:
        return all([self.token_url, self.api_base_url, self.client_id, self.client_secret])

    def _get_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        if not self.configured():
            raise RuntimeError('BlueSky client is not fully configured')

        resp = requests.post(
            self.token_url,
            data={'grant_type': 'client_credentials'},
            auth=(self.client_id, self.client_secret),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data['access_token']
        self._token_expires_at = now + int(data.get('expires_in', 3600))
        return self._access_token

    def _headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self._get_token()}',
            'Accept': 'application/json',
        }

    def get_devices_by_serial(self, serial: str) -> List[Dict[str, Any]]:
        url = f'{self.api_base_url}/devices'
        resp = requests.get(url, headers=self._headers(), params={'serial': serial}, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list):
            return payload
        return payload.get('items') or payload.get('data') or payload.get('devices') or []

    def resolve_device_id(self, serial: str) -> str:
        items = self.get_devices_by_serial(serial)
        if not items:
            raise RuntimeError(f'BlueSky serial not found: {serial}')
        item = items[0]
        device_id = str(item.get('device_id') or item.get('deviceId') or item.get('id') or '').strip()
        if not device_id:
            raise RuntimeError(f'No device_id returned for serial {serial}')
        return device_id

    def get_flat_telemetry(self, *, device_id: str) -> List[Dict[str, Any]]:
        telem = [
            'model', 'serial', 'mcpm1x0', 'mcpm2x5', 'mcpm4x0', 'mcpm10',
            'temperature', 'rh', 'tpsize', 'baro_inhg',
            'co2_ppm', 'co_ppm', 'o3_ppb', 'no2_ppb', 'so2_ppb', 'ch2o_ppb', 'voc_mgm3',
            'timestamp'
        ]
        params = [('device_id', device_id)] + [('telem[]', t) for t in telem]
        url = f'{self.api_base_url}/telemetry/flat-format'
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list):
            return payload
        return payload.get('items') or payload.get('data') or payload.get('devices') or []

    def get_latest_by_serial(self, serial: str) -> Dict[str, Any]:
        device_id = self.resolve_device_id(serial)
        items = self.get_flat_telemetry(device_id=device_id)
        if not items:
            raise RuntimeError(f'No telemetry returned for serial {serial}')
        return items[0]


def normalize_flat_telemetry(row: Dict[str, Any]) -> Dict[str, Any]:
    pm1 = row.get('mcpm1x0')
    pm25 = row.get('mcpm2x5')
    pm4 = row.get('mcpm4x0')
    pm10 = row.get('mcpm10')
    tpsize = row.get('tpsize')
    return {
        'timestamp': row.get('timestamp'),
        'model': row.get('model'),
        'serial': row.get('serial'),
        'pm1': pm1,
        'pm2_5': pm25,
        'pm4': pm4,
        'pm10': pm10,
        'tsp': tpsize,
        'temperature_c': row.get('temperature'),
        'humidity_percent': row.get('rh'),
        'pressure_hpa': row.get('baro_inhg'),
        'co2_ppm': row.get('co2_ppm'),
        'co_ppm': row.get('co_ppm'),
        'o3_ppb': row.get('o3_ppb'),
        'no2_ppb': row.get('no2_ppb'),
        'so2_ppb': row.get('so2_ppb'),
        'ch2o_ppb': row.get('ch2o_ppb'),
        'voc_mgm3': row.get('voc_mgm3'),
        'raw': row,
    }
