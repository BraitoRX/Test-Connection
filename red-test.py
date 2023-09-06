import base64
import functions_framework
import connectToMachine as cn
import json
# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def hello_pubsub(cloud_event):
    # Print out the data from Pub/Sub, to prove that it worked
    
    pubsub_data = base64.b64decode(cloud_event.data["message"]["data"])
    # Convertir los datos decodificados en un objeto JSON
    try:
        json_data = json.loads(pubsub_data.decode('utf-8'))
        instance_id = json_data["incident"]["resource"]["labels"]["instance_id"]
        
        # Ahora puedes consultar el objeto JSON según tus necesidades
    except json.JSONDecodeError as e:
        print(f"Error al decodificar los datos JSON: {e}")
    cn.main("mkdir awa", "analitica-demos", hostname="10.142.0.22")
    return "uwu"


