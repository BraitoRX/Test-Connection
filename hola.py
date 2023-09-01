from __future__ import annotations
from collections.abc import Iterable
from google.cloud import compute_v1
import paramiko


hostname = "10.128.0.13"
username = "brivera_procibernetica_com"
key_filename = "claves/braito"


commands = ["mkdir uwu"]


client = paramiko.SSHClient()


client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(hostname=hostname,port=22, username=username, key_filename=key_filename)
except Exception as e:
    print("[!] Cannot connect to the SSH Server")
    print(e)
    exit()

for command in commands:
    print("=" * 50, command, "=" * 50)
    stdin, stdout, stderr = client.exec_command(command)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(err)

stdin.close()

# def list_instances(project_id: str, zone: str) -> Iterable[compute_v1.Instance]:
#     """
#     List all instances in the given zone in the specified project.

#     Args:
#         project_id: project ID or project number of the Cloud project you want to use.
#         zone: name of the zone you want to use. For example: “us-west3-b”
#     Returns:
#         An iterable collection of Instance objects.
#     """
#     instance_client = compute_v1.InstancesClient()
#     instance_list = instance_client.list(project=project_id, zone=zone)

#     print(f"Instances found in zone {zone}:")
#     for instance in instance_list:
#         print(f" - {instance.getDescription()}")

#     return instance_list

# list_instances("analitica-demos", "us-central1-a")
