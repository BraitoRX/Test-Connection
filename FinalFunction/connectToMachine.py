import argparse
import logging
import subprocess
import time
import uuid

import googleapiclient.discovery
import requests

# URL y encabezados para obtener la dirección de correo electrónico de la cuenta de servicio desde el metadato de la instancia.
SERVICE_ACCOUNT_METADATA_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/email"
)
HEADERS = {"Metadata-Flavor": "Google"}

def main(cmds, project, instance=None, zone=None,
         oslogin=None, account=None, hostname=None, username=None,quantity=None):
    """
    Ejecuta un comando en un sistema remoto.

    Args:
        cmds: Lista de comandos a ejecutar en el sistema remoto.
        project: ID del proyecto de GCP.
        instance: Nombre de la instancia de GCP.
        zone: Zona donde se encuentra la instancia.
        oslogin: Cliente del API de OS Login.
        account: Cuenta de servicio de GCP para autenticación.
        hostname: Nombre de host del sistema remoto.
        username: Nombre de usuario POSIX en el sistema remoto.
        quantity: Parámetro no utilizado en la implementación actual.
    """
    
    # Crear el objeto API de OS Login si no se proporciona.
    oslogin = oslogin or googleapiclient.discovery.build('oslogin', 'v1')

    # Identificar el ID de la cuenta de servicio si no se proporciona.
    account = account or requests.get(
        SERVICE_ACCOUNT_METADATA_URL, headers=HEADERS).text
    if not account.startswith('users/'):
        account = 'users/' + account

    # Crear un nuevo par de claves SSH y asociarlo con la cuenta de servicio.
    private_key_file = create_ssh_key(oslogin, account)

    # Utilizando la API de OS Login, obtener el nombre de usuario POSIX del perfil de inicio de sesión.
    profile = oslogin.users().getLoginProfile(name=account).execute()
    username = username or profile.get('posixAccounts')[0].get('username')
    
    # Crear el nombre de host de la instancia objetivo usando el nombre de la instancia, la zona y el proyecto.
    hostname = hostname or '{instance}.{zone}.c.{project}.internal'.format(
        instance=instance, zone=zone, project=project)

    # Ejecutar un comando en la instancia remota a través de SSH.
    result = run_ssh(cmds, private_key_file, username, hostname)

    # Imprimir la salida de la línea de comandos de la instancia remota.
    for line in result:
        print(line.decode('utf-8').strip())
    
    # Destruir la clave privada y eliminar el par de claves.
    execute(['shred', private_key_file])
    execute(['rm', private_key_file])
    execute(['rm', private_key_file + '.pub'])

def create_ssh_key(oslogin, account, private_key_file=None, expire_time=300):
    """
    Genera un par de claves SSH y las aplica a la cuenta especificada.

    Args:
        oslogin: Objeto cliente del API de OS Login.
        account: Cuenta de usuario en la que se aplicará la clave SSH.
        private_key_file: Ruta al archivo de clave privada SSH. Si no se provee, se generará una.
        expire_time: Tiempo en segundos después del cual la clave expirará.

    Returns:
        La ruta al archivo de clave privada SSH generado.

    Esta función crea un par de claves SSH, almacena la clave pública en el perfil de OS Login del usuario
    y devuelve la ruta a la clave privada para su uso en conexiones SSH.
    """
    private_key_file = private_key_file or '/tmp/key-' + str(uuid.uuid4())
    execute(['ssh-keygen', '-t', 'rsa', '-N', '', '-f', private_key_file])

    with open(private_key_file + '.pub', 'r') as original:
        public_key = original.read().strip()

    # El tiempo de expiración se calcula en microsegundos.
    expiration = int((time.time() + expire_time) * 1000000)

    body = {
        'key': public_key,
        'expirationTimeUsec': expiration,
    }
    oslogin.users().importSshPublicKey(parent=account, body=body).execute()
    return private_key_file

def execute(cmd, cwd=None, capture_output=False, env=None, raise_errors=True):
    """
    Ejecuta un comando externo, es un envoltorio para subprocess de Python.

    Args:
        cmd: Comando y argumentos a ejecutar como una lista.
        cwd: Directorio de trabajo actual para el comando.
        capture_output: Si es True, captura la salida del comando.
        env: Diccionario de variables de entorno para el comando.
        raise_errors: Si es True, lanza una excepción si el comando devuelve un error.

    Returns:
        Una tupla con el código de retorno y la salida del comando.

    Esta función ejecuta un comando en el sistema y opcionalmente captura y devuelve su salida.
    Si el comando falla y raise_errors es True, se lanza una excepción.
    """
    logging.info('Executing command: {cmd}'.format(cmd=str(cmd)))
    stdout = subprocess.PIPE if capture_output else None
    process = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=stdout)
    output = process.communicate()[0]
    returncode = process.returncode
    if returncode:
        # Error
        if raise_errors:
            raise subprocess.CalledProcessError(returncode, cmd)
        else:
            logging.info('Command returned error status %s', returncode)
    if output:
        logging.info(output)
    return returncode, output

def run_ssh(cmds, private_key_file, username, hostname):
    """
    Ejecuta un comando en un sistema remoto a través de SSH.

    Args:
        cmds: Lista de comandos a ejecutar en el sistema remoto.
        private_key_file: Ruta al archivo de clave privada SSH.
        username: Nombre de usuario para la conexión SSH.
        hostname: Nombre de host del sistema remoto.

    Returns:
        La salida del comando ejecutado en el sistema remoto.

    Esta función construye y ejecuta un comando SSH, utilizando la clave privada y las credenciales
    proporcionadas, para correr los comandos especificados en el sistema remoto.
    """
    ssh_command = [
        'ssh', '-i', private_key_file, '-o', 'StrictHostKeyChecking=no',
        '{username}@{hostname}'.format(username=username, hostname=hostname),
        ';'.join(cmds),
    ]
    ssh = subprocess.Popen(
        ssh_command, shell=False, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    result = ssh.stdout.readlines()
    return result if result else ssh.stderr.readlines()