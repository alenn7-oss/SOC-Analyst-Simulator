import requests
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("WAZUH_API_URL")
user = os.getenv("WAZUH_API_USER")
password = os.getenv("WAZUH_API_PASS")

# Step 1: log in and get a token
auth_response = requests.post(
    f"{url}/security/user/authenticate",
    auth=(user, password),
    verify=False
)
token = auth_response.json()["data"]["token"]
print("Got token successfully.")

# Step 2: use the token to ask for recent alerts
headers = {"Authorization": f"Bearer {token}"}
alerts_response = requests.get(
    f"{url}/manager/logs",
    headers=headers,
    verify=False
)
print(alerts_response.json())
