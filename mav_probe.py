#!/usr/bin/env python3
"""Probe a PX4/ArduPilot flight controller over MAVLink from the Raspberry Pi.
Tries serial devices at common bauds, then common UDP/TCP router endpoints,
and waits for a HEARTBEAT on each."""
import sys, glob

try:
    from pymavlink import mavutil
except ImportError:
    print("PYMAVLINK_MISSING: install with  sudo pip3 install pymavlink")
    sys.exit(2)


def ename(enum, val):
    try:
        return mavutil.mavlink.enums[enum][val].name
    except Exception:
        return str(val)


serial_ports = []
for pat in ("/dev/ttyACM*", "/dev/ttyUSB*", "/dev/serial0", "/dev/serial1", "/dev/ttyAMA0"):
    serial_ports += glob.glob(pat)
serial_ports = sorted(set(serial_ports))
print("Detected serial devices:", serial_ports if serial_ports else "(none)")

candidates = []
for p in serial_ports:
    for b in (115200, 57600, 921600):
        candidates.append((p, b))
for ep in ("udpin:0.0.0.0:14550", "udp:127.0.0.1:14540", "tcp:127.0.0.1:5760"):
    candidates.append((ep, None))

found = False
for conn, baud in candidates:
    desc = conn + (("@" + str(baud)) if baud else "")
    try:
        m = mavutil.mavlink_connection(conn, baud=baud) if baud else mavutil.mavlink_connection(conn)
    except Exception as e:
        print("SKIP", desc, "->", e)
        continue
    print("Trying", desc, "...")
    hb = m.wait_heartbeat(timeout=5)
    if hb is None:
        print("  no heartbeat")
        m.close()
        continue
    found = True
    print("=== HEARTBEAT on", desc, "===")
    print("  system:", m.target_system, " component:", m.target_component)
    print("  autopilot:", ename('MAV_AUTOPILOT', hb.autopilot))
    print("  type:", ename('MAV_TYPE', hb.type))
    print("  base_mode:", hb.base_mode, " status:", ename('MAV_STATE', hb.system_status))
    try:
        m.mav.command_long_send(
            m.target_system, m.target_component,
            mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 0,
            mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION, 0, 0, 0, 0, 0, 0)
        msg = m.recv_match(type='AUTOPILOT_VERSION', blocking=True, timeout=3)
        if msg:
            v = msg.flight_sw_version
            print("  flight_sw_version: %d.%d.%d" % ((v >> 24) & 0xFF, (v >> 16) & 0xFF, (v >> 8) & 0xFF))
    except Exception:
        pass
    m.close()
    break

if not found:
    print("RESULT: NO_MAVLINK_HEARTBEAT (check wiring / port / baud / power, or a router may hold the port)")
    sys.exit(1)
print("RESULT: MAVLINK_OK")
