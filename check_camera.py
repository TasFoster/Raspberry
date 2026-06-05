"""
SSH к Raspberry Pi 3 (192.168.11.1, user: raspberry), проверка камеры
и создание лог-файла на хосте при её наличии.
"""
import sys
import paramiko
from datetime import datetime

HOST = "192.168.11.1"
USER = "pi"
PASSWORD = "raspberry"

CHECKS = [
    ("hostname",                "hostname"),
    ("os_release",              "cat /etc/os-release 2>/dev/null || true"),
    ("uname",                   "uname -a"),
    ("home_dirs",               "ls -la /home 2>&1 || true"),
    ("raspberry_home_check",    "[ -d /home/raspberry ] && echo EXISTS || echo MISSING"),
    ("libcamera-hello",         "libcamera-hello --list-cameras 2>&1 || true"),
    ("vcgencmd_get_camera",     "vcgencmd get_camera 2>&1 || true"),
    ("dev_video",               "ls -la /dev/video* 2>&1 || true"),
    ("v4l2-ctl_list",           "v4l2-ctl --list-devices 2>&1 || true"),
    ("dmesg_camera",            "dmesg 2>/dev/null | grep -iE 'camera|bcm2835|imx|ov5647|video' | tail -n 30 || true"),
    ("lsmod_video",             "lsmod 2>/dev/null | grep -iE 'bcm2835|v4l|video' || true"),
    ("usb_devices",             "lsusb 2>&1 || true"),
    ("clover_camera_service",   "systemctl status clover 2>&1 | head -n 20 || true"),
]


def detect_camera(results: dict) -> tuple[bool, str]:
    """Возвращает (camera_present, reason)."""
    # libcamera
    lc = results.get("libcamera-hello", "").lower()
    if "available cameras" in lc and "no cameras available" not in lc:
        return True, "libcamera-hello detected camera"
    # vcgencmd
    vc = results.get("vcgencmd_get_camera", "")
    if "detected=1" in vc:
        return True, "vcgencmd reports detected=1"
    # /dev/video*
    dv = results.get("dev_video", "")
    if "/dev/video" in dv and "No such file" not in dv and "cannot access" not in dv.lower():
        return True, "/dev/video* device(s) present"
    return False, "no camera signals from any check"


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[+] Connecting to {USER}@{HOST} ...")
    try:
        client.connect(
            hostname=HOST,
            username=USER,
            password=PASSWORD,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )
    except Exception as e:
        print(f"[!] SSH connect failed: {e}")
        return 2
    print("[+] Connected.")

    results: dict[str, str] = {}
    for name, cmd in CHECKS:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        combined = (out + ("\n[stderr]\n" + err if err.strip() else "")).strip()
        results[name] = combined
        head = combined.splitlines()[0] if combined else "(empty)"
        print(f"  - {name}: {head[:90]}")

    present, reason = detect_camera(results)
    status = "CAMERA_OK" if present else "CAMERA_NOT_DETECTED"
    print(f"[=] Camera status: {status} ({reason})")

    log_path = None
    if present:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        # Если папка /home/raspberry/ существует — пишем туда (как просил пользователь),
        # иначе кладём в домашнюю директорию текущего пользователя (pi).
        raspberry_home = results.get("raspberry_home_check", "").strip()
        if raspberry_home.endswith("EXISTS"):
            log_path = f"/home/raspberry/camera_status_{ts}.log"
        else:
            log_path = f"/home/{USER}/camera_status_{ts}.log"
        body_lines = [
            "=== Raspberry Pi Camera Status Log ===",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Host:      {HOST}",
            f"User:      {USER}",
            f"Status:    {status}",
            f"Reason:    {reason}",
            "",
        ]
        for name, _ in CHECKS:
            body_lines.append(f"--- [{name}] ---")
            body_lines.append(results.get(name, "(no output)"))
            body_lines.append("")
        body = "\n".join(body_lines)

        # safe heredoc-style write
        marker = "EOF_CAMERA_LOG_2026"
        write_cmd = f"cat > {log_path} <<'{marker}'\n{body}\n{marker}\n"
        stdin, stdout, stderr = client.exec_command(write_cmd, timeout=20)
        exit_status = stdout.channel.recv_exit_status()
        err = stderr.read().decode("utf-8", errors="replace")
        if exit_status == 0:
            print(f"[+] Log written to {log_path}")
        else:
            print(f"[!] Failed to write log (exit={exit_status}): {err}")
            return 3

        stdin, stdout, stderr = client.exec_command(
            f"ls -la {log_path}; echo '---'; wc -l {log_path}", timeout=10
        )
        print(stdout.read().decode("utf-8", errors="replace"))

    # сохраним полную выгрузку локально для отчёта
    local_dump = "D:/Projects/Raspberry/ssh_session.log"
    with open(local_dump, "w", encoding="utf-8") as f:
        f.write(f"# SSH session to {USER}@{HOST}\n")
        f.write(f"# Generated: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"# Status: {status} ({reason})\n")
        if log_path:
            f.write(f"# Remote log: {log_path}\n")
        f.write("\n")
        for name, cmd in CHECKS:
            f.write(f"=== [{name}]  $ {cmd}\n")
            f.write(results.get(name, "(no output)") + "\n\n")
    print(f"[+] Local dump saved: {local_dump}")

    client.close()
    return 0 if present else 1


if __name__ == "__main__":
    sys.exit(main())
