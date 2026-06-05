#!/usr/bin/env python3
"""READ-ONLY preflight/arm-readiness check for PX4. Does NOT arm.
Reports flight mode/state, streams STATUSTEXT, and decodes SYS_STATUS sensor health."""
import sys, time, glob
try:
    from pymavlink import mavutil
except ImportError:
    print("PYMAVLINK_MISSING: sudo pip3 install pymavlink")
    sys.exit(2)


def ename(enum, val):
    try:
        return mavutil.mavlink.enums[enum][val].name
    except Exception:
        return str(val)


candidates = [("/dev/ttyACM0", 115200)]
for p in sorted(glob.glob("/dev/ttyUSB*")):
    candidates.append((p, 115200))
candidates += [("udp:127.0.0.1:14540", None)]

m = None
for conn, baud in candidates:
    try:
        c = mavutil.mavlink_connection(conn, baud=baud) if baud else mavutil.mavlink_connection(conn)
    except Exception as e:
        print("SKIP", conn, "->", e)
        continue
    if c.wait_heartbeat(timeout=6) is not None:
        m = c
        link = conn + (("@%d" % baud) if baud else "")
        break
    c.close()
if m is None:
    print("RESULT: NO_HEARTBEAT")
    sys.exit(1)
print("Connected on %s (sys=%d comp=%d)\n" % (link, m.target_system, m.target_component))

# ask for SYS_STATUS + heartbeat
for mid, hz in [(mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS, 2),
                (mavutil.mavlink.MAVLINK_MSG_ID_HEARTBEAT, 1)]:
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                            mid, int(1e6 / hz), 0, 0, 0, 0, 0)

# SENSOR bit names (subset of MAV_SYS_STATUS_SENSOR)
SENSORS = {
    0x01: "3D_GYRO", 0x02: "3D_ACCEL", 0x04: "3D_MAG", 0x08: "ABS_PRESSURE",
    0x20: "GPS", 0x400: "RC_RECEIVER", 0x1000: "AHRS",
    0x4000000: "PREARM_CHECK",
}

statustexts = []
last_ss = None
last_hb = None
deadline = time.time() + 7
while time.time() < deadline:
    msg = m.recv_match(blocking=True, timeout=1)
    if not msg:
        continue
    t = msg.get_type()
    if t == "STATUSTEXT":
        statustexts.append((ename("MAV_SEVERITY", msg.severity), msg.text))
    elif t == "SYS_STATUS":
        last_ss = msg
    elif t == "HEARTBEAT":
        last_hb = msg

print("=" * 50)
if last_hb:
    try:
        mode = mavutil.mode_string_v10(last_hb)
    except Exception:
        mode = "custom=%d" % last_hb.custom_mode
    armed = bool(last_hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    print("MODE   :", mode, "  ARMED:" , armed)
    print("STATE  :", ename("MAV_STATE", last_hb.system_status),
          "  (STANDBY = ready to arm)")

if last_ss:
    present = last_ss.onboard_control_sensors_present
    enabled = last_ss.onboard_control_sensors_enabled
    health = last_ss.onboard_control_sensors_health
    print("\nSENSOR HEALTH (present/enabled/healthy):")
    for bit, nm in SENSORS.items():
        p = "Y" if present & bit else "-"
        e = "Y" if enabled & bit else "-"
        h = "OK" if health & bit else ("FAIL" if present & bit else "n/a")
        print("  %-14s present=%s enabled=%s health=%s" % (nm, p, e, h))
    bad = [nm for bit, nm in SENSORS.items() if (present & bit) and not (health & bit)]
    print("\nUNHEALTHY:", ", ".join(bad) if bad else "(none)")

print("\nSTATUSTEXT messages:")
if statustexts:
    for sev, txt in statustexts:
        print("  [%s] %s" % (sev, txt))
else:
    print("  (none received)")
print("=" * 50)
m.close()
