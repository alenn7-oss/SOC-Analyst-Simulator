import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("WAZUH_INDEXER_URL")
user = os.getenv("WAZUH_INDEXER_USER")
password = os.getenv("WAZUH_INDEXER_PASS")

query = {
    "size": 1,
    "sort": [{"timestamp": "desc"}],
    "query": {
        "bool": {
            "must": [
                {"match": {"rule.groups": "authentication_failed"}},
                {"match": {"agent.name": "win-lab"}}
            ]
        }
    }
}

response = requests.get(
    f"{url}/wazuh-alerts-4.x-*/_search",
    auth=(user, password),
    headers={"Content-Type": "application/json"},
    json=query,
    verify=False
)

result = response.json()
alert = result["hits"]["hits"][0]["_source"]

# Save it as a readable file so we can look at it
with open("docs/sample_alert.json", "w") as f:
    json.dump(alert, f, indent=2)

print("Saved one real alert to docs/sample_alert.json")
print(f"Rule: {alert['rule']['description']}")
print(f"Agent: {alert['agent']['name']}")
print(f"Time: {alert['timestamp']}")
