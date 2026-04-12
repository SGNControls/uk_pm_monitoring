import os
import time
import logging
from typing import Any, Dict, Optional

import requests

log = logging.getLogger(__name__)


class BlueSkyClient:
    """Minimal TSI Link / BlueSky client using OAuth2 client credentials.

    Environment variables:
    - BLUESKY_TOKEN_URL
    - BLUESKY_API_BASE_URL
    - BLUESKY_CLIENT_ID
    - BLUESKY_CLIENT_SECRET
    """

    def __init__(self):
        self.token_url = os.getenv("BLUESKY_TOKEN_URL", "").strip()
        self.api_base_url = os.getenv("BLUESKY_API_BASE_URL", "").strip().rstrip("/")
        self.client_id = os.getenv("BLUESKY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("BLUESKY_CLIENT_SECRET", "").strip()
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def configured(self) -> bool:
        return all([self.token_url, self.api_base_url, self.client_id, self.client_secret])

    def _get_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        if not self.configured():
            raise RuntimeError("BlueSky client is not fully configured")

        resp = requests.post(
            self.token_url,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expires_at = now + int(data.get("expires_in", 3600))
        return self._access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Accept": "application/json",
        }

    def get_devices(self, model: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if model:
            params["model"] = model
        resp = requests.get(
            f"{self.api_base_url}/devices",
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_device_snapshot(self, device_id: str) -> Dict[str, Any]:
        resp = requests.get(
            f"{self.api_base_url}/devices/{device_id}/snapshot",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def find_device_by_serial(self, serial_number: str) -> Optional[Dict[str, Any]]:
        devices = self.get_devices()
        items = devices.get("items") or devices.get("data") or []
        for item in items:
            if str(item.get("serialNumber", "")).strip() == str(serial_number).strip():
                return item
        return None


def normalize_bluesky_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Map BlueSky snapshot to dashboard-friendly structure.

    This keeps the return contract close to existing dashboard fields.
    Unknown fields are preserved under `raw`.
    """
    data = snapshot.get("data", snapshot)
    telemetry = data.get("telemetry", data)

    return {
        "timestamp": data.get("timestamp") or telemetry.get("timestamp"),
        "pm1": telemetry.get("pm1") or telemetry.get("PM1"),
        "pm2_5": telemetry.get("pm2_5") or telemetry.get("pm25") or telemetry.get("PM2.5"),
        "pm10": telemetry.get("pm10") or telemetry.get("PM10"),
        "temperature_c": telemetry.get("temperature_c") or telemetry.get("temperature") or telemetry.get("tempC"),
        "humidity_percent": telemetry.get("humidity_percent") or telemetry.get("humidity") or telemetry.get("rh"),
        "pressure_hpa": telemetry.get("pressure_hpa") or telemetry.get("pressure"),
        "gps_lat": telemetry.get("gps_lat") or telemetry.get("latitude"),
        "gps_lon": telemetry.get("gps_lon") or telemetry.get("longitude"),
        "raw": snapshot,
    }
