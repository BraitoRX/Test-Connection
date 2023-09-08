from __future__ import annotations
import base64
import functions_framework
import connectToMachine as cn
import json
from google.cloud import compute_v1
import google.auth
import google.auth.transport.requests
import requests


# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def hello_pubsub(cloud_event):
    # Print out the data from Pub/Sub, to prove that it worked
    pubsub_data = base64.b64decode(cloud_event.data["message"]["data"])
    # Convertir los datos decodificados en un objeto JSON
    try:
        json_data = json.loads(pubsub_data.decode("utf-8"))
        instance_id = json_data["incident"]["resource"]["labels"]["instance_id"]
        project_id = json_data["incident"]["resource"]["labels"]["project_id"]
        zona = json_data["incident"]["resource"]["labels"]["zone"]
        instance_details = get_instance_details(project_id, instance_id, zona)
        response = compute_v1.Instance.to_json(instance_details)
        response = json.loads(response)
        diskName = ""
        disk_size_gb = 0
        internalIP = response["networkInterfaces"][0]["networkIP"]
        for disk in response.get("disks", []):
            if disk["deviceName"] == response["name"]:
                disk_size_gb = disk.get("diskSizeGb")
                diskName = disk["deviceName"]

        # getting the credentials and project details for gcp project
        credentials, your_project_id = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zona}/disks/{diskName}/resize"
        bearer_token = credentials.token
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }
        porcentaje = 0.1
        payload = {"sizeGb": str(round(int(disk_size_gb) * (1 + porcentaje)))}
        newSize = payload["sizeGb"]
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            print("Request successful")
            cn.main(
                [
                    f"echo `Se redimensionó el disco {diskName} con {disk_size_gb} a {newSize} correctamente`",
                    "echo -e 'resizepart\nFix\n1\nYes\n100%\nquit' | sudo parted /dev/sda ---pretend-input-tty",
                    "sudo partprobe /dev/sda",
                    "sudo resize2fs /dev/sda1"
                ],
                project_id,
                hostname=internalIP,
            )
        else:
            print(f"Request failed with status code {response.status_code}")
            print(response.text)

    except json.JSONDecodeError as e:
        print(f"Error al decodificar los datos JSON: {e}")


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
