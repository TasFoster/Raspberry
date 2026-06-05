#!/usr/bin/env python3
"""Capture the FULL 'commander check' failure lines + 'commander status' from the
PX4 nsh shell over MAVLink. READ-ONLY."""
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
print("Connected\n")


def shell_send(text):
    b = (text + "\n").encode()
    buf = list(b) + [0] * (70 - len(b))
    m.mav.serial_control_send(DEV_SHELL, F_RESPOND | F_EXCLUSIVE | F_MULTI, 0, 0, len(b), buf)


def pump(seconds):
    out = []
    end = time.time() + seconds
    while time.time() < end:
        m.mav.serial_control_send(DEV_SHELL, F_RESPOND, 0, 0, 0, [0] * 70)
        msg = m.recv_match(type="SERIAL_CONTROL", blocking=True, timeout=0.4)
        if msg and msg.count > 0:
            out.append(bytes(msg.data[:msg.count]).decode(errors="replace"))
    return "".join(out)


shell_send("")
pump(1)
for cmd, secs in [("commander check", 6), ("commander status", 5)]:
    print("=" * 55)
    print("$ %s" % cmd)
    print("-" * 55)
    shell_send(cmd)
    time.sleep(0.3)
    print(pump(secs))
print("=" * 55)
m.close()
