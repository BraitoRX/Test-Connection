from __future__ import annotations
import base64
import functions_framework
import connectToMachine as cn
import json
from google.cloud import compute_v1
import google.auth
import google.auth.transport.requests
import requests
import math


@functions_framework.cloud_event
def disk_resize(cloud_event):
    pubsub_data = base64.b64decode(cloud_event.data["message"]["data"])
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

        credentials, your_project_id = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        disk_size_gb = int(disk_size_gb)
        threshold_value = float(
            json_data["incident"]["condition"]["conditionThreshold"]["thresholdValue"]
        )
        observerd_value = float(json_data["incident"]["observed_value"])

        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zona}/disks/{diskName}/resize"
        bearer_token = credentials.token
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }

        print(f"threshold_value: {threshold_value}")
        print(f"observerd_value: {observerd_value}")
        print(f"disk_size_gb: { disk_size_gb}")
        porcentaje = 10
        b = observerd_value / 100
        c = (threshold_value+porcentaje) / 100
        a = disk_size_gb
        x = (c * a - b * a) / (1 - c)
        final_value = math.ceil(disk_size_gb + x)
        print(f"final_value: {final_value}")
        payload = {"sizeGb": str(final_value)}
        newSize = payload["sizeGb"]
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            print("Request successful")
            cn.main(
                [
                    "echo -e 'resizepart\nFix\n1\nYes\n100%\nquit' | sudo parted /dev/sda ---pretend-input-tty",
                    "sudo partprobe /dev/sda",
                    "sudo resize2fs /dev/sda1",
                    f"echo 'Se redimensionó el disco {diskName} de {disk_size_gb} GB a {newSize} GB correctamente, quedando con un porcentaje de {threshold_value+porcentaje}% de espacio disponible'",
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
