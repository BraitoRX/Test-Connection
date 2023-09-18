import functions_framework
import google.auth
import google.auth.transport.requests
import requests
from google.cloud import compute_v1
import json
import connectToMachine as cn


@functions_framework.http
def hello_http(request):
    request_json = request.get_json(silent=True)
    credentials, your_project_id = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    project_id = request_json["project_id"]
    zona = request_json["zone"]
    diskName = request_json["diskName"]
    disk_size_gb = request_json["newSize"]
    instance_id = request_json["instance_id"]

    payload = {"sizeGb": disk_size_gb}

    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zona}/disks/{diskName}/resize"
    bearer_token = credentials.token
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }
    instance_details = get_instance_details(project_id, instance_id, zona)
    response = compute_v1.Instance.to_json(instance_details)
    response = json.loads(response)
    internalIP = response["networkInterfaces"][0]["networkIP"]

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        cn.main(
            [
                "echo -e 'resizepart\nFix\n1\nYes\n100%\nquit' | sudo parted /dev/sda ---pretend-input-tty",
                "sudo partprobe /dev/sda",
                "sudo resize2fs /dev/sda1",
            ],
            project_id,
            hostname=internalIP,
        )
    else:
        print(f"Request failed with status code {response.status_code}")
        print(response.text)
    return "ok"

def get_instance_details(project_id: str, instance_id: str, zone: str) -> dict:
    """
    Returns detailed information about a specific instance in a project.

    Args:
        project_id: Project ID or project number of the Cloud project you want to use.
        instance_id: ID of the instance you want to retrieve details for.
        zone: zone of the instace you want to retrieve details for

    Returns:
        A dictionary with information about the specified instance.
    """
    instance_client = compute_v1.InstancesClient()
    request = compute_v1.GetInstanceRequest()
    request.project = project_id
    request.zone = zone
    request.instance = instance_id

    try:
        response = instance_client.get(request=request)
        return response
    except Exception as e:
        print(f"Error fetching instance details: {e}")
        return {}
