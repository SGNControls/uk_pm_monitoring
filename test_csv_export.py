#!/usr/bin/env python3
"""Test script for CSV export functionality"""

import requests
import os
from datetime import datetime, timedelta

# Flask app URL (adjust if running on different port)
BASE_URL = "http://localhost:8000"

def test_csv_export():
    """Test the CSV export endpoint"""

    # Test parameters
    device_id = "1"  # Assuming device ID 1 exists
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')

    print(f"Testing CSV export with:")
    print(f"  Device ID: {device_id}")
    print(f"  Start Date: {start_date}")
    print(f"  End Date: {end_date}")

    # Construct the URL
    url = f"{BASE_URL}/api/export_csv?deviceid={device_id}&start_date={start_date}&end_date={end_date}"

    print(f"Request URL: {url}")

    try:
        # Make the request
        response = requests.get(url, allow_redirects=True)

        print(f"Response Status Code: {response.status_code}")
        print(f"Response Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"Response Content-Length: {response.headers.get('Content-Length', 'N/A')}")

        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'text/csv' in content_type:
                print("✅ SUCCESS: CSV file returned")
                # Print first few lines of CSV
                lines = response.text.split('\n')[:5]
                print("CSV Preview:")
                for line in lines:
                    print(f"  {line}")
                return True
            else:
                print(f"❌ ERROR: Expected CSV content-type, got: {content_type}")
                print(f"Response content: {response.text[:500]}")
                return False
        else:
            print(f"❌ ERROR: HTTP {response.status_code}")
            print(f"Response content: {response.text[:500]}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to Flask app. Is it running?")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_error_conditions():
    """Test error conditions"""

    print("\nTesting error conditions...")

    # Test missing parameters
    test_cases = [
        ("Missing deviceid", f"{BASE_URL}/api/export_csv?start_date=2024-01-01&end_date=2024-01-02"),
        ("Missing start_date", f"{BASE_URL}/api/export_csv?deviceid=1&end_date=2024-01-02"),
        ("Missing end_date", f"{BASE_URL}/api/export_csv?deviceid=1&start_date=2024-01-01"),
        ("Invalid device", f"{BASE_URL}/api/export_csv?deviceid=999&start_date=2024-01-01&end_date=2024-01-02"),
    ]

    for test_name, url in test_cases:
        print(f"\nTesting: {test_name}")
        try:
            response = requests.get(url, allow_redirects=True)
            if response.status_code == 400:
                print(f"✅ Expected error response (400) for: {test_name}")
            else:
                print(f"❌ Unexpected status {response.status_code} for: {test_name}")
        except Exception as e:
            print(f"❌ Connection error for {test_name}: {str(e)}")

if __name__ == "__main__":
    print("CSV Export Test Script")
    print("=" * 50)

    # Test successful export
    success = test_csv_export()

    # Test error conditions
    test_error_conditions()

    print("\n" + "=" * 50)
    if success:
        print("🎉 CSV export functionality appears to be working!")
    else:
        print("❌ CSV export functionality needs more work.")
