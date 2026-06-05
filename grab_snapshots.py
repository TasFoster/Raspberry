"""Сделать N снимков на Raspberry Pi через raspistill и забрать их по SFTP."""
import os
import sys
import time
import paramiko
from datetime import datetime

HOST = "192.168.11.1"
USER = "pi"
PASSWORD = "raspberry"

N_SHOTS = 3
WIDTH, HEIGHT = 1920, 1080
SHUTTER_DELAY_MS = 800           # время прогрева сенсора перед кадром
INTER_SHOT_SLEEP_S = 1.0         # пауза между снимками

LOCAL_DIR = r"D:\Projects\Raspberry\snapshots"


def main() -> int:
    os.makedirs(LOCAL_DIR, exist_ok=True)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[+] Connecting to {USER}@{HOST} ...")
    client.connect(
        HOST, username=USER, password=PASSWORD, timeout=15,
        allow_agent=False, look_for_keys=False,
    )
    print("[+] Connected.")

    sftp = client.open_sftp()
    session_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    remote_paths: list[str] = []

    try:
        for i in range(1, N_SHOTS + 1):
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            remote = f"/tmp/snap_{session_ts}_{i:02d}_{ts}.jpg"
            cmd = (
                f"raspistill -n -t {SHUTTER_DELAY_MS} "
                f"-w {WIDTH} -h {HEIGHT} -q 90 -o {remote}"
            )
            print(f"[{i}/{N_SHOTS}] {cmd}")
            stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
            rc = stdout.channel.recv_exit_status()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            if rc != 0:
                print(f"    !! raspistill exit={rc}, stderr: {err}")
                continue

            # проверим размер удалённого файла
            st = sftp.stat(remote)
            print(f"    remote size: {st.st_size} bytes")

            local = os.path.join(LOCAL_DIR, os.path.basename(remote))
            sftp.get(remote, local)
            print(f"    -> {local}  ({os.path.getsize(local)} bytes)")

            remote_paths.append(remote)
            if i < N_SHOTS:
                time.sleep(INTER_SHOT_SLEEP_S)

        # подчистим /tmp на Pi
        if remote_paths:
            rm_cmd = "rm -f " + " ".join(remote_paths)
            client.exec_command(rm_cmd)
            print(f"[+] Cleaned up {len(remote_paths)} file(s) on Pi.")
    finally:
        sftp.close()
        client.close()

    print(f"[=] Saved {len(remote_paths)} snapshot(s) to {LOCAL_DIR}")
    return 0 if len(remote_paths) == N_SHOTS else 1


if __name__ == "__main__":
    sys.exit(main())
