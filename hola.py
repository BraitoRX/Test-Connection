import paramiko


hostname = "35.223.165.86"
username = "brivera_procibernetica_com"

key = paramiko.RSAKey.from_private_key_file("C:/Users/brall/.ssh/id_rsa")

commands = ["sudo apt update"]

client = paramiko.SSHClient()

client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=hostname, username=username, pkey=key)

for command in commands:
    print("=" * 50, command, "=" * 50)
    stdin, stdout, stderr = client.exec_command(command)
    xd = stdout.read().decode()
    err = stderr.read().decode()
    if err:
        print(err)

stdin.close()

print(xd)
