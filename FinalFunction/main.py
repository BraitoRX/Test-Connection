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
import publicatePubSubAlert as pp

project_id_host = "analitica-demos"
error_topic_id = "error-cf-resize-disk"


@functions_framework.cloud_event
def disk_resize(cloud_event):
    """
    Esta función se dispara en respuesta a un evento de Cloud Pub/Sub, específicamente diseñado para 
    redimensionar el disco de una instancia de Compute Engine cuando se alcanza un cierto umbral.

    Args:
        cloud_event: El evento de Cloud que activó la función, que contiene los datos del mensaje de Pub/Sub.

    Los pasos realizados por la función son:
    1. Decodificar los datos de Pub/Sub que están en base64 a un objeto JSON.
    2. Extraer la información relevante como el ID de la instancia, el ID del proyecto y la zona.
    3. Obtener los detalles de la instancia y determinar el nombre y tamaño actual del disco.
    4. Calcular el nuevo tamaño del disco basado en el umbral y el valor observado.
    5. Enviar una solicitud a la API de Compute Engine para cambiar el tamaño del disco.
    6. Si la solicitud es exitosa, ejecutar comandos en la máquina para ajustar el sistema de archivos.
    7. Manejar errores y excepciones a lo largo del proceso.

    La función imprime mensajes a lo largo del proceso para proporcionar un registro del progreso y de cualquier error.
    """
    # Decodificación de los datos recibidos en el mensaje de Pub/Sub
    pubsub_data = base64.b64decode(cloud_event.data["message"]["data"])

    try:
        rootPartition_by_interface = {
            "SCSI": "/dev/sda",
            "NVME": "/dev/nvme0n1"
        }
        # Carga de los datos decodificados como un objeto JSON
        json_data = json.loads(pubsub_data.decode("utf-8"))
        # Extracción de detalles de la instancia de la carga de datos JSON
        instance_id = json_data["incident"]["resource"]["labels"]["instance_id"]
        project_id = json_data["incident"]["resource"]["labels"]["project_id"]
        zona = json_data["incident"]["resource"]["labels"]["zone"]
        # Obtención de detalles de la instancia de Compute Engine
        instance_details = get_instance_details(project_id, instance_id, zona)
        # Conversión de la instancia de detalles a JSON y posteriormente a objeto para su manipulación
        response = compute_v1.Instance.to_json(instance_details)
        response = json.loads(response)
        # Inicialización de variables para almacenar el nombre y tamaño del disco
        diskName = ""
        disk_size_gb = 0
        # Extracción de la IP interna de la primera interfaz de red
        internalIP = response["networkInterfaces"][0]["networkIP"]
        # Búsqueda del disco que coincide con el nombre de la instancia para obtener su tamaño actual
        partitionX = json_data["incident"]["metric"]["labels"]["device"]
        print(f"Partición: {partitionX}")
        print(f"JSON: {json_data}")
        print(f"response {response}")
        for disk in response.get("disks", []):
            url = disk["source"] 
            extracted_value = url.split("/")[-1]
            diska= get_disk_details (project_id,extracted_value, zona,instance_id,partitionX)
            response_disk = compute_v1.Disk.to_json(diska)
            response_disk = json.loads(response_disk)
            print(f"Disco: {response_disk}")
            type_disk = response_disk["labels"].get("type")
            print(f"Tipo de disco: {type_disk}")
            if type_disk != None and type_disk == "root":
                type_partition = disk.get('interface')
                if type_partition == None:
                    report_error(f"no se encuentra el tipo de interfaz de disco para el disco {disk['deviceName']}",instance_id,project_id,zona,partitionX)
                root = rootPartition_by_interface.get(type_partition)
                if root == None:
                    report_error(f"El tipo de interfaz de disco no está admitida! solo SCSI y NVME se encontró {type_partition}",instance_id,project_id,zona,partitionX)
                print(f"Root: {root}")
                disk_size_gb = disk.get("diskSizeGb")
                diskName = disk["deviceName"]
                break


        if diskName == "":
            report_error("Falló la CF de redimensionamiento de disco, revisar las restricciones de etiquetado o partición secundaria detectada.",instance_id,project_id,zona,partitionX)

        print(f"Disco de la instancia: {diskName}")
        # Autenticación y preparación para realizar la solicitud de cambio de tamaño del disco
        credentials, your_project_id = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        # Conversión del tamaño del disco a entero
        disk_size_gb = int(disk_size_gb)
        # Extracción de valores umbral y observado de los datos del incidente
        threshold_value = float(
            json_data["incident"]["condition"]["conditionThreshold"]["thresholdValue"]
        )
        observerd_value = float(json_data["incident"]["observed_value"])
        
        # Refresco de credenciales y preparación de la solicitud HTTP
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zona}/disks/{diskName}/resize"
        bearer_token = credentials.token
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }
        
        # Cálculo del nuevo tamaño de disco requerido
        porcentaje = 10
        b = (100-observerd_value) / 100
        c = (100-threshold_value + porcentaje) / 100
        a = disk_size_gb
        x = (c * a - b * a) / (1 - c)
        final_value = math.ceil(disk_size_gb + x)
        
        # Creación del cuerpo de la solicitud con el nuevo tamaño del disco
        payload = {"sizeGb": str(final_value)}
        newSize = payload["sizeGb"]
        # Envío de la solicitud POST a la API de Compute Engine para cambiar el tamaño
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        # Manejo de la respuesta a la solicitud de cambio de tamaño
        if response.status_code == 200:
            print("Request successful")
            # Si la solicitud es exitosa, se ejecutan comandos en la instancia para ajustar el sistema de archivos
            cn.main(
                [
                    f"echo -e 'resizepart\nfix\n1\nYes\n100%\nquit' | sudo parted {root} ---pretend-input-tty",
                    f"sudo partprobe {root}",
                    f"sudo resize2fs {partitionX}",
                    f"echo 'Se redimensionó el disco {diskName} de {disk_size_gb} GB a {newSize} GB correctamente, quedando con un porcentaje de {100-threshold_value + porcentaje}% de espacio disponible'",
                ],
                project_id,
                hostname=internalIP,
            )
        else:
            # Si la solicitud falla, se imprimen mensajes de error
            print(f"Request failed with status code {response.status_code}")
            print(response.text)
            report_error(f"No se pudo redimensionar el disco {diskName} de {disk_size_gb} GB a {newSize} GB correctamente debido a: {response.text}",instance_id,project_id,zona,partitionX)

    except json.JSONDecodeError as e:
        # Manejo de errores en la decodificación de JSON
        print(f"Error al decodificar los datos JSON: {e}")
        report_error(f"Error al decodificar los datos JSON: {e}",instance_id,project_id,zona,partitionX)

def report_error(error:str,instancia,project, zona, partition):
    pp.publish_error(error,project_id_host,error_topic_id,instancia,project,zona,partition)
    raise Exception(error)

def get_instance_details(project_id: str, instance_id: str, zone: str) -> dict:
    """
    Función auxiliar para obtener detalles de una instancia específica en un proyecto de GCP.
    
    Args:
        project_id: ID del proyecto o número de proyecto en el que se desea operar.
        instance_id: ID de la instancia de la cual se quieren obtener detalles.
        zone: Zona en la que se encuentra la instancia.
    
    Returns:
        Un diccionario con información detallada sobre la instancia especificada.
    
    Esta función hace uso de la API de Compute Engine para recuperar los datos de la instancia.
    """
    # Cliente de la API de Compute Engine
    instance_client = compute_v1.InstancesClient()
    # Creación de la solicitud para obtener detalles de la instancia
    request = compute_v1.GetInstanceRequest()
    

    request.project = project_id
    request.zone = zone
    request.instance = instance_id

    try:
        # Envío de la solicitud y retorno de la respuesta
        response = instance_client.get(request=request)
        return response
    except Exception as e:
        # Manejo de errores al obtener detalles de la instancia
        print(f"Error fetching instance details: {e}")
        return {}

def get_disk_details(project_id: str, disk_name: str, zone: str,instance_id_: str,partitionXx: str) -> dict:	
    # Cliente de la API de Compute Engine para discos
    disk_client = compute_v1.DisksClient()
    # Creación de la solicitud para obtener detalles del disco
    request = compute_v1.GetDiskRequest(
        project=project_id,
        zone=zone,
        disk=disk_name  # Asegúrate de que este sea el nombre correcto del disco
    )
    try:
        # Envío de la solicitud y retorno de la respuesta
        response = disk_client.get(request=request)
        return response
    except Exception as e:
        # Manejo de errores al obtener detalles del disco
        print(f"Error fetching disk details: {e}")
        report_error(f"Error fetching disk details: {e}",instance_id_,project_id,zone,partitionXx)
        return {}