from google.cloud import compute_v1
import json
from google.protobuf.json_format import MessageToDict  # Assuming you're using the google.protobuf library

def sample_get():
    # Create a client
    client = compute_v1.InstancesClient()

    # Initialize request argument(s)
    request = compute_v1.GetInstanceRequest(
        instance="7162207394860725366",
        project="analitica-demos",
        zone="us-central1-a",
    )

    # Make the request
    response = client.get(request=request)
    response= compute_v1.Instance.to_json(response)
    response= json.loads(response)
    print(response)
    internalIP=response["networkInterfaces"][0]["networkIP"]
    

sample_get()

