#!/usr/bin/env python3
"""Collect extended telemetry from a PX4 flight controller over MAVLink.
Connects (USB /dev/ttyACM0 by default, with fallbacks), requests data streams,
then reports battery/load, GPS, attitude, VFR_HUD and the active flight mode."""
import sys, time, math, glob
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


# --- connect (prefer the known USB port, then fall back) ---
candidates = [("/dev/ttyACM0", 115200)]
for p in sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/serial0")):
    candidates.append((p, 115200))
candidates += [("udp:127.0.0.1:14540", None), ("udpin:0.0.0.0:14550", None)]

m = None
for conn, baud in candidates:
    try:
        c = mavutil.mavlink_connection(conn, baud=baud) if baud else mavutil.mavlink_connection(conn)
    except Exception as e:
        print("SKIP", conn, "->", e)
        continue
    print("Trying", conn, ("@%d" % baud) if baud else "", "...")
    if c.wait_heartbeat(timeout=6) is not None:
        m = c
        link = conn + (("@%d" % baud) if baud else "")
        break
    c.close()

if m is None:
    print("RESULT: NO_HEARTBEAT")
    sys.exit(1)
print("Connected on %s  (sys=%d comp=%d)\n" % (link, m.target_system, m.target_component))

# --- ask PX4 to stream what we need ---
for mid, hz in [
    (mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS, 2),
    (mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT, 2),
    (mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, 5),
    (mavutil.mavlink.MAVLINK_MSG_ID_VFR_HUD, 2),
    (mavutil.mavlink.MAVLINK_MSG_ID_BATTERY_STATUS, 1),
    (mavutil.mavlink.MAVLINK_MSG_ID_HEARTBEAT, 1),
]:
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                            mid, int(1e6 / hz), 0, 0, 0, 0, 0)
# legacy fallback for older stacks
m.mav.request_data_stream_send(m.target_system, m.target_component,
                               mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)

# --- collect latest of each type for a few seconds ---
wanted = {"HEARTBEAT", "SYS_STATUS", "GPS_RAW_INT", "ATTITUDE", "VFR_HUD", "BATTERY_STATUS"}
latest = {}
deadline = time.time() + 8
while time.time() < deadline:
    msg = m.recv_match(blocking=True, timeout=1)
    if msg and msg.get_type() in wanted:
        latest[msg.get_type()] = msg
    if wanted.issubset(latest.keys()) and time.time() > deadline - 6:
        break

print("Messages received:", ", ".join(sorted(latest.keys())) or "(none)")
print("-" * 48)

hb = latest.get("HEARTBEAT")
if hb:
    armed = "ARMED" if (hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) else "DISARMED"
    try:
        mode = mavutil.mode_string_v10(hb)
    except Exception:
        mode = "custom=%d" % hb.custom_mode
    print("FLIGHT MODE : %s   [%s]" % (mode, armed))
    print("SYSTEM STATE: %s" % ename("MAV_STATE", hb.system_status))

ss = latest.get("SYS_STATUS")
if ss:
    v = ss.voltage_battery
    print("BATTERY     : %.2f V, %s A, %d%%" % (
        (v / 1000.0) if v != 0xFFFF else float("nan"),
        ("%.2f" % (ss.current_battery / 100.0)) if ss.current_battery != -1 else "n/a",
        ss.battery_remaining if ss.battery_remaining != -1 else -1))
    print("CPU LOAD    : %.1f%%" % (ss.load / 10.0))

bs = latest.get("BATTERY_STATUS")
if bs:
    cells = [c for c in bs.voltages if c != 0xFFFF]
    if cells:
        print("CELLS       : " + ", ".join("%.2f" % (c / 1000.0) for c in cells) + " V")

gps = latest.get("GPS_RAW_INT")
if gps:
    print("GPS FIX     : %s  sats=%d  hdop=%.2f" % (
        ename("GPS_FIX_TYPE", gps.fix_type), gps.satellites_visible,
        gps.eph / 100.0 if gps.eph != 0xFFFF else float("nan")))
    if gps.fix_type >= 2:
        print("GPS POS     : lat=%.7f lon=%.7f alt=%.1f m" % (
            gps.lat / 1e7, gps.lon / 1e7, gps.alt / 1000.0))

att = latest.get("ATTITUDE")
if att:
    print("ATTITUDE    : roll=%.1f  pitch=%.1f  yaw=%.1f  (deg)" % (
        math.degrees(att.roll), math.degrees(att.pitch), math.degrees(att.yaw)))

hud = latest.get("VFR_HUD")
if hud:
    print("VFR_HUD     : alt=%.1f m  climb=%.1f m/s  groundspeed=%.1f m/s  throttle=%d%%" % (
        hud.alt, hud.climb, hud.groundspeed, hud.throttle))

print("-" * 48)
print("RESULT: TELEMETRY_OK")
m.close()
