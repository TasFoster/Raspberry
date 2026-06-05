"""Probe several SSH auth combinations to find what works."""
import paramiko, socket

HOST = "192.168.11.1"
COMBOS = [
    ("raspberry", "raspberry"),
    ("pi",        "raspberry"),
    ("pi",        "raspberrypi"),
    ("pi",        "pi"),
]

def try_login(user, pw):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(HOST, username=user, password=pw, timeout=10,
                  allow_agent=False, look_for_keys=False)
    except paramiko.AuthenticationException as e:
        return f"AUTH_FAIL: {e}"
    except (socket.timeout, OSError) as e:
        return f"NET_FAIL: {e}"
    except Exception as e:
        # try keyboard-interactive
        try:
            t = paramiko.Transport((HOST, 22))
            t.connect()
            t.auth_interactive_dumb(user, lambda *_: [pw])
            if t.is_authenticated():
                t.close()
                return "OK (keyboard-interactive)"
            t.close()
            return f"FAIL: {e}"
        except Exception as e2:
            return f"FAIL: {e} / kbi: {e2}"
    stdin, stdout, stderr = c.exec_command("whoami; hostname")
    out = stdout.read().decode().strip()
    c.close()
    return f"OK: {out}"

for u, p in COMBOS:
    print(f"{u:>12} / {p:<14} -> {try_login(u, p)}")
