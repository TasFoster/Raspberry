#!/usr/bin/env python3
"""Local driver: connect to the Clover Pi over SSH (paramiko, password auth),
upload mav_probe.py, run it, stream output back."""
import sys, base64, paramiko

HOST = "192.168.11.1"
USER = "pi"
PASSWORD = "raspberry"
LOCAL_SCRIPT = sys.argv[1] if len(sys.argv) > 1 else r"D:\Projects\Raspberry\mav_probe.py"
REMOTE_PATH = "/tmp/" + LOCAL_SCRIPT.replace("\\", "/").split("/")[-1]

with open(LOCAL_SCRIPT, "rb") as f:
    payload = base64.b64encode(f.read()).decode()

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {USER}@{HOST} ...")
cli.connect(HOST, username=USER, password=PASSWORD, timeout=15, look_for_keys=False, allow_agent=False)
print("Connected.\n")

# deploy script
cmd = f"echo {payload} | base64 -d > {REMOTE_PATH} && python3 {REMOTE_PATH}"
stdin, stdout, stderr = cli.exec_command(cmd, timeout=120)
out = stdout.read().decode(errors="replace")
err = stderr.read().decode(errors="replace")
rc = stdout.channel.recv_exit_status()

print(out, end="")
if err.strip():
    print("\n[stderr]\n" + err, end="")
print(f"\n[exit code] {rc}")
cli.close()
sys.exit(rc)
