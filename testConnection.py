import paramiko

# Configuración de la conexión SSH
hostname = '10.128.0.5'
port = 22
username = 'procibernetica\brivera@PCBTI-124'
private_key_path = './Claves/id_rsa.pem'
# Crear una instancia de la clase SSHClient
client = paramiko.SSHClient()

# Cargar automáticamente las claves del archivo known_hosts
client.load_system_host_keys()

# Aceptar automáticamente la clave del host si es desconocida
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Cargar la clave privada
private_key = paramiko.RSAKey.from_private_key_file(private_key_path)

# Conectar al servidor utilizando la clave privada
client.connect(hostname, port=port, username=username, pkey=private_key)

# Ejecutar un comando en el servidor
stdin, stdout, stderr = client.exec_command('ls -l')

# Imprimir la salida del comando
print(stdout.read().decode())

# Cerrar la conexión SSH
client.close()
