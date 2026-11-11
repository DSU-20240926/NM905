import paramiko
import re

# Read credentials
with open('pc_password.txt', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.strip().splitlines()
user_host = lines[1].strip()
password = lines[2].strip()

username, host = user_host.split('@')
print(f"Connecting to {username}@{host}...")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(host, port=22, username=username, password=password, timeout=10)
    print("SSH Connection successful!")

    commands = [
        "hostname",
        "whoami",
        "nvidia-smi",
        "docker ps -a",
        "docker images",
        "curl -s http://localhost:11434/api/tags"
    ]

    for cmd in commands:
        print(f"\n--- Running: {cmd} ---")
        stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if out:
            print("[STDOUT]:")
            print(out.strip())
        if err:
            print("[STDERR]:")
            print(err.strip())

except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
