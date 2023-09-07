import time
import boto3

ec2_client = boto3.client("ec2")
ssm_client = boto3.client("ssm")


#target_size --> Escribe el porcenjae que desea incrementar,  Ejem si quieres incrementar el tamaño al 20 % solo debes colocar el numero 20. 
#volume_id": --> El id del volumen a incrementar Ejem 'vol-039bb9f8dadff1182'
#instance_id": --> El id de la instancia a incrementar Ejem 'i-02db3471c0426bdb8'
#drive_letter": --> Si el sistema operativo es windows escribe la letra de la unidad Ejem 'c' de lo contrario se puede dejar vacio
#keep_snapshot": --> Si requiere tomar una instantanea coloque true de lo contrario false
#mount_point": --> Si el sistema operativo es linux escribe el moint point donde esta montado el disco Ejem '/mnt/data'  de lo contrario lo puede dejar vacio
#disk_name": --> Debe escribir el nombre del disco donde esta montada la particion si el tipo de particion es LVM, si no es LVM se puede dajar vacio Ejem. 
#               xvdf                  202:80   0   5G  0 disk
#                └─vg_prueba-lv_prueba 253:0    0   5G  0 lvm  /mnt/data"   como se puede ver la particion /mnt/data tiene un disco con el nombre xvdf.
#               El valor que debe escribir "/dev/xvdf"

def lambda_handler(event, context):
    platform_type = None
    if event["instance_id"] != "":
        platform_type = get_operating_system_by_instance_id(
            event["instance_id"]
        )

    #snapshot_id = create_snapshot(
    #    event["volume_id"], event["instance_id"]
    #)
    
    target_size = validacion(event["volume_id"], event["target_size"])

    extend_ebs_volume(event["volume_id"], int(target_size))

    if not event["keep_snapshot"]:
        delete_snapshot(snapshot_id)

    if event["instance_id"] != "":
        if platform_type == "Linux":
            return extend_file_system_for_linux(
                event["instance_id"], event["mount_point"], event["disk_name"]
            )
        elif platform_type == "Windows":
            return extend_file_system_for_windows(
                event["instance_id"],
                event["drive_letter"],
                target_size,
            )
        else:
            raise Exception("Unsupported Platform")
    return "volume extended successfully"

def validacion(volume_id, target_size):
    try:
        response = ec2_client.describe_volumes(VolumeIds=[volume_id])
        sizeCurrent = response["Volumes"][0]["Size"]
        if target_size.isnumeric():
            equivalente_decimal = int(target_size) / 100
            target_size_percentage = (sizeCurrent) * (equivalente_decimal)
        else:
            print("Debes ingresar un valor numerico en target_size y un valor mayor o igual a 10")
            exit(1)
    except Exception as e:
            raise Exception(e)
    if int(target_size_percentage) == 0:
        print("El valor a incrementar es {}, por favor escribe un valor mas grande".format(equivalente_decimal))
        exit(1)
    else:
        return int(sizeCurrent + target_size_percentage)


#def validacion(volume_id, target_size):
#    response = ec2_client.describe_volumes(VolumeIds=[volume_id])
#    sizeCurrent = response["Volumes"][0]["Size"]
#    return int(sizeCurrent) + int(target_size)
    
def extend_ebs_volume(volume_id, target_size):
    ec2_client.modify_volume(
        VolumeId=volume_id,
        Size=target_size,
    )
    while True:
        response = ec2_client.describe_volumes(VolumeIds=[volume_id])
        if response["Volumes"][0]["Size"] == target_size:
            return "success"
        time.sleep(3)


def get_operating_system_by_instance_id(instance_id):
    try:
        os_type = ssm_client.describe_instance_information(
            InstanceInformationFilterList=[
                {"key": "InstanceIds", "valueSet": [instance_id]}
            ]
        )
        if len(os_type["InstanceInformationList"]) > 0:
            return os_type["InstanceInformationList"][0]["PlatformType"]
        else:
            raise Exception("The instance must be managed by system manager")
    except Exception as e:
        raise Exception(e)


def extend_file_system_for_linux(instance_id, mount_point, diskName):
    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        TimeoutSeconds=500,
        Parameters={
            "commands": [
                "#!/bin/bash",
                "# Verificamos si el punto de montaje existe",
                "if ! [ -d {} ]; then".format(mount_point),
                    "echo 'El punto de montaje {} no existe.'".format(mount_point),
                    "exit 1",
                "fi",
                "# Buscamos el dispositivo asociado al punto de montaje",
                "DEVICE_NAME=$(df -P " + mount_point + " | awk 'END{print $1}')",
                "echo $DEVICE_NAME",
                "if ! [ -b $DEVICE_NAME ]; then",
                    "echo 'El dispositivo $DEVICE_NAME no existe.'",
                    "exit 1",
                "fi",
                "type=`lsblk -no TYPE $DEVICE_NAME`",
                "if [ $type = 'lvm' ]; then",
                    "echo 'lvm'",
                    "pvresize {}".format(diskName),
                    "pach=`df -P " + mount_point + " | awk 'NR==2{print $1}'`",
                    "name_vg=`lvs --noheadings -o vg_name $pach`",
                    "prueba=${name_vg// /}",
                    "lv_pach=`lvdisplay --no-headings -C -o lv_path /dev/$prueba`",
                    "lvextend -r -l+100%FREE $lv_pach",
                "else",
                    "fstype=`lsblk -no FSTYPE $DEVICE_NAME`",
                    "if [ $fstype = 'ext4' ]; then",
                        "# Redimensionamos el sistema de archivos a su tamaño completo",
                        "echo 'ext4'",
                        "deviceName=`lsblk -npo pkname $DEVICE_NAME`",
                        "partitionNumber=${DEVICE_NAME: -1}",
                        "sudo growpart $deviceName $partitionNumber",
                        "sudo resize2fs $DEVICE_NAME",
                    "elif [ $fstype = 'xfs' ]; then",
                        "echo 'xfs'",
                        "deviceName=`lsblk -npo pkname $DEVICE_NAME`",
                        "partitionNumber=${DEVICE_NAME: -1}",
                        "sudo growpart $deviceName $partitionNumber",
                        "sudo xfs_growfs $DEVICE_NAME",
                    "fi",
                "fi",
                "echo 'El disco $DEVICE_NAME se ha redimensionado a su tamaño completo.'",
            ]
        },
    )
    command_id = response["Command"]["CommandId"]
    status, status_details = get_command_status_with_wait(
        instance_id, command_id
    )
    if status_details == "Failed":
        raise Exception("Error extending the file system")
    return "volume extended successfully"


def create_snapshot(volume_id, exec_id):
    try:
        response = ec2_client.create_snapshot(
            Description="a snapshot before the volume resizing",
            VolumeId=volume_id,
            TagSpecifications=[
                {
                    "ResourceType": "snapshot",
                    "Tags": [{"Key": "execution_id", "Value": exec_id}],
                },
            ],
        )
        return response["SnapshotId"]
    except Exception as e:
        raise Exception(e)


def delete_snapshot(snapshot_id):
    try:
        ec2_client.delete_snapshot(
            SnapshotId=snapshot_id,
        )
    except Exception as e:
        raise Exception(e)


def extend_file_system_for_windows(instance_id, drive_letter, size):
    size = int(size)
    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunPowerShellScript",
        TimeoutSeconds=500,
        Parameters={
            "commands": [
                    "Resize-Partition -DriveLetter " + drive_letter + " -Size (Get-PartitionSupportedSize -DriveLetter " + drive_letter + ").sizeMax"
            ]
        },
    )
    command_id = response["Command"]["CommandId"]
    status, status_details = get_command_status_with_wait(
        instance_id, command_id
    )
    if status_details == "Failed":
        raise Exception("Failed Extending the partition")
    return "volume extended successfully"


def validate_windows_partition_size(instance_id, drive_letter, size):
    try:
        MAX_RETRIALS_NUM = 3
        WAITING_STATUS = ["Pending", "InProgress", "Delayed"]
        size = int(size)
        resp = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunPowerShellScript",
            TimeoutSeconds=500,
            Parameters={
                "commands": [
                    "$maxSize = Get-PartitionSupportedSize -DriveLetter {}".format(
                        drive_letter
                    ),
                    "if($maxSize.SizeMax -lt {} * 1024 * 1024 * 1024)".format(
                        size
                    ),
                    "{exit 1}",
                ]
            },
        )
        cmd_id = resp["Command"]["CommandId"]
        status, status_details = get_command_status_with_wait(
            instance_id, cmd_id
        )

        for retries in range(MAX_RETRIALS_NUM):
            if status in WAITING_STATUS:
                time.sleep(10)
                status, status_details = get_command_status_with_wait(
                    instance_id, cmd_id
                )

        if status_details == "Failed":
            raise Exception(
                "The target size is greater than the max size of the partition"
            )
    except Exception as e:
        raise Exception(e)
    return True


def get_command_status_with_wait(instance_id, command_id):
    time.sleep(10)
    response = ssm_client.get_command_invocation(
        CommandId=command_id, InstanceId=instance_id
    )
    status = response["Status"]
    details = response["StatusDetails"]
    return status, details