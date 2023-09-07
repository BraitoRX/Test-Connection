import json

from google.oauth2 import service_account
from google.cloud import compute_v1



json_acct_info = json.loads(function_to_get_json_creds())
credentials = service_account.Credentials.from_service_account_info(
    json_acct_info)

scoped_credentials = credentials.with_scopes(
    ['https://www.googleapis.com/auth/cloud-platform'])

networks_client = compute_v1.NetworksClient(credentials=scoped_credentials)
for network in networks_client.list(project='YOUR_PROJECT'):
    print(network)


POST 

{
 "sizeGb": "11"
}