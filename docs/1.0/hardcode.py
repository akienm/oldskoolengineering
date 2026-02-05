import os
import requests



comment='Session key'
def lookup_structured_citation():
    key = os.getenv("COURTLISTENER_KEY", None)
    url = "https://www.courtlistener.com/api/rest/v4/citation-lookup/"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Token {key}"
    }
    data = {
        "text": "United States Ex Rel. Meyer v. Horizon Health Corp.",
        "reporter": "",  # F.3d",
        "volume": "565",
        "page": "1200"
    }

    print(f'')
    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        result = response.json()
        print("✅ Found citation:")
        print(f"  Case: {result}")
    else:
        print(f'headers: {headers}')
        print(f"❌ Error {response.status_code}: {response.text}")

# Run it
lookup_structured_citation()