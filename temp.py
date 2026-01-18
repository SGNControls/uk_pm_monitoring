import requests
import time
import sys
from datetime import datetime, timedelta

# ================== CONFIGURATION ==================
TSI_CLIENT_ID     = 'kPecWhWAzU9GCB0isWW5ece8Q6bkUHqMM6MvL9GIwLuc577j'
TSI_CLIENT_SECRET = 'gcXUlWxlCOYMAi7oAYgiSEDAWSn30FomMtqzcZd055ZigVP32TGGdZmXpG7Ol2Lk'
TSI_DEVICE_ID     = 'cpg3cgvkons02hel22og'
MIN_INTERVAL      = 10  # seconds between polls
# ====================================================

BASE_URL = "https://api-prd.tsilink.com/api/v3/external"

def get_access_token():
    url = f"{BASE_URL}/oauth/client_credential/accesstoken?grant_type=client_credentials"
    data = {
        "client_id": TSI_CLIENT_ID,
        "client_secret": TSI_CLIENT_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        resp.raise_for_status()
        token = resp.json()
        access_token = token["access_token"]
        expires_in = int(token.get("expires_in", 3599))
        expiry_time = datetime.utcnow() + timedelta(seconds=expires_in - 60)
        return access_token, expiry_time
    except Exception as e:
        print(f"Error fetching access token: {e}")
        sys.exit(1)

def fetch_realtime_data(token, device_id):
    url = f"{BASE_URL}/telemetry/flat-format"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    # Get current UTC time in RFC3339 format for latest_as_of_date
    current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    params = [
        ("telem[]", "mcpm1x0"),
        ("telem[]", "mcpm2x5"),
        ("telem[]", "mcpm4x0"),
        ("telem[]", "mcpm10"),
        ("telem[]", "tpsize"),
        ("device_id", device_id),
        ("latest_as_of_date", current_time),  # Get most recent data up to now
    ]
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None

def main():
    token, expiry = get_access_token()
    print("Authenticated! Starting TSI real-time data polling...")
    print(f"Polling device {TSI_DEVICE_ID} every {MIN_INTERVAL} seconds")
    
    while True:
        # Refresh OAuth token if expiring
        if datetime.utcnow() >= expiry:
            token, expiry = get_access_token()
            print("Refreshed OAuth token")

        try:
            data = fetch_realtime_data(token, TSI_DEVICE_ID)
            if not data or len(data) == 0:
                print(f"[{datetime.utcnow().isoformat()}] No recent data available")
            else:
                latest = data[0]  # Get most recent record
                
                # Extract timestamp and PM data
                timestamp = latest.get("cloud_timestamp", "N/A")
                pm_data = {
                    "PM1": latest.get('mcpm1x0', 'N/A'),
                    "PM2.5": latest.get('mcpm2x5', 'N/A'),
                    "PM4": latest.get('mcpm4x0', 'N/A'),
                    "PM10": latest.get('mcpm10', 'N/A'),
                    "TSP": latest.get('tpsize', 'N/A')
                }
                
                # Print the timestamp and PM data
                print(f"\nTimestamp: {timestamp}")
                print("PM Data:")
                for key, value in pm_data.items():
                    print(f"{key}: {value} µg/m³" if key != "TSP" else f"{key}: {value} µm")
                print("-" * 30)
                
        except Exception as e:
            print(f"[{datetime.utcnow().isoformat()}] Error: {str(e)}")

        time.sleep(MIN_INTERVAL)

if __name__ == "__main__":
    main()