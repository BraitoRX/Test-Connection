from google.cloud import compute_v1
import json
from google.protobuf.json_format import MessageToDict  

def sample_get():
    # Create a client
    client = compute_v1.InstancesClient()

    request = compute_v1.GetInstanceRequest(
        instance="7162207394860725366",
        project="analitica-demos",
        zone="us-central1-a",
    )

    # Make the request
    response = client.get(request=request)
    response= compute_v1.Instance.to_json(response)
    response= json.loads(response)
    internalIP=response["networkInterfaces"][0]["networkIP"]
    for disk in response.get('disks', []):
        if disk['deviceName'] == 'maquina-agente-vm-disk':
            disk_size_gb = disk.get('diskSizeGb')
            print(f"Disk size for VM 'maquina-agente-vm-disk': {disk_size_gb} GB")
            break

sample_get()

