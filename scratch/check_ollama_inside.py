import paramiko

with open('pc_password.txt', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.strip().splitlines()
user_host = lines[1].strip()
password = lines[2].strip()
username, host = user_host.split('@')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(host, port=22, username=username, password=password, timeout=10)
    
    commands = [
        "docker exec open-webui ollama list",
        "docker exec open-webui ollama ps",
        "docker exec open-webui curl -s http://localhost:11434/api/tags",
        "where ollama",
        "netstat -ano | findstr 11434",
        "netstat -ano | findstr 3000"
    ]

    for cmd in commands:
        print(f"\n--- Running: {cmd} ---")
        stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        if out:
            print("[STDOUT]:\n" + out)
        if err:
            print("[STDERR]:\n" + err)

except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
