import requests
import json

def test_psx_json():
    print("--- PSX Summary Index ---")
    headers = {"X-Requested-With": "XMLHttpRequest", "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get("https://dps.psx.com.pk/summary/index", headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        # Not sure if it returns JSON or HTML
        print(r.text[:500])
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- PSX Get Indices ---")
    try:
        # Some endpoints require POST or different URL
        r = requests.get("https://dps.psx.com.pk/summary/get_indices", headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        print(r.text[:500])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_psx_json()
