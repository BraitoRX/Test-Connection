from google.cloud import pubsub_v1

def publish_error(message: str,project_id_host, error_topic_id,instance_id,project_id,zona,partitionX):
    """Publica un mensaje en el tópico de errores.

    Args:
        message (str): El mensaje de error a publicar.
    """
    try:
        publisher = pubsub_v1.PublisherClient()
        basic_message = f"Error message: {message}\n"
        basic_message += f"Instance ID: {instance_id}\n"
        basic_message += f"Project ID: {project_id}\n"
        basic_message += f"Zone: {zona}\n"
        basic_message += f"Partition: {partitionX}\n"
        message = basic_message
        error_topic_path = publisher.topic_path(project_id_host, error_topic_id)
        # Publica el mensaje de error
        publish_future = publisher.publish(error_topic_path, message.encode("utf-8"))
        # Espera a que la publicación se complete.
        publish_future.result()
        print(f"Error message published to {error_topic_path}.")
    except Exception as e:
        print(f"An error occurred when publishing the error message: {e}")