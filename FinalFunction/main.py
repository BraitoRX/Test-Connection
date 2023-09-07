from __future__ import annotations
import base64
import functions_framework
import connectToMachine as cn
import json
from google.cloud import compute_v1

# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def hello_pubsub(cloud_event):
    # Print out the data from Pub/Sub, to prove that it worked
    pubsub_data = base64.b64decode(cloud_event.data["message"]["data"])
    # Convertir los datos decodificados en un objeto JSON
    try:
        json_data = json.loads(pubsub_data.decode('utf-8'))
        instance_id = json_data["incident"]["resource"]["labels"]["instance_id"]
        project_id = json_data["incident"]["resource"]["labels"]["project_id"]
        zona = json_data["incident"]["resource"]["labels"]["zone"]
        instance_details=get_instance_details(project_id,instance_id,zona)
        response= compute_v1.Instance.to_json(instance_details)
        response= json.loads(response)
        internalIP=response["networkInterfaces"][0]["networkIP"]
        cn.main("mkdir ewe", project_id, hostname=internalIP)
    except json.JSONDecodeError as e:
        print(f"Error al decodificar los datos JSON: {e}")



def get_instance_details(
    project_id: str,
    instance_id: str,
    zone: str
) -> dict:
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

