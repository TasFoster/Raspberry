#!/usr/bin/env python3
"""Open the PX4 nsh shell over MAVLink SERIAL_CONTROL and run diagnostic
commands ('commander check', 'ekf2 status', 'uorb top') to learn why the
autopilot stays in UNINIT and refuses to arm. READ-ONLY."""
import sys, time, glob
try:
    from pymavlink import mavutil
except ImportError:
    print("PYMAVLINK_MISSING"); sys.exit(2)

DEV_SHELL = mavutil.mavlink.SERIAL_CONTROL_DEV_SHELL
F_RESPOND = mavutil.mavlink.SERIAL_CONTROL_FLAG_RESPOND
F_EXCLUSIVE = mavutil.mavlink.SERIAL_CONTROL_FLAG_EXCLUSIVE
F_MULTI = mavutil.mavlink.SERIAL_CONTROL_FLAG_MULTI

m = None
for p in sorted(glob.glob("/dev/ttyACM*")):
    try:
        c = mavutil.mavlink_connection(p, baud=115200)
    except Exception:
        continue
    if c.wait_heartbeat(timeout=6) is not None:
        m = c; break
    c.close()
if m is None:
    print("RESULT: NO_HEARTBEAT"); sys.exit(1)
print("Connected (sys=%d comp=%d)\n" % (m.target_system, m.target_component))


def shell_send(text):
    b = text.encode()
    buf = list(b) + [0] * (70 - len(b))
    m.mav.serial_control_send(DEV_SHELL, F_RESPOND | F_EXCLUSIVE | F_MULTI,
                              0, 0, len(b), buf)


def pump(seconds):
    """Read shell output for N seconds, nudging the FC to flush."""
    out = []
    end = time.time() + seconds
    while time.time() < end:
        m.mav.serial_control_send(DEV_SHELL, F_RESPOND, 0, 0, 0, [0] * 70)
        msg = m.recv_match(type="SERIAL_CONTROL", blocking=True, timeout=0.5)
        if msg and msg.count > 0:
            out.append(bytes(msg.data[:msg.count]).decode(errors="replace"))
    return "".join(out)


for cmd in ["\n", "commander check", "ekf2 status", "sensors status"]:
    print("=" * 55)
    print("$ %s" % cmd.strip())
    print("-" * 55)
    shell_send(cmd + "\n")
    time.sleep(0.3)
    txt = pump(3.5)
    print(txt if txt.strip() else "(no output)")

print("=" * 55)
m.close()
