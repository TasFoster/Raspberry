#!/usr/bin/env python3
"""Bench-arm test for PX4 (PROPS MUST BE OFF).
Relaxes RC/GPS/USB arming checks, switches to STABILIZED, ARMs, holds a few
seconds while reading motor/throttle telemetry, then DISARMs. Prints COMMAND_ACKs."""
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


# ---- connect ----
m = None
for conn, baud in [("/dev/ttyACM0", 115200)] + [(p, 115200) for p in sorted(glob.glob("/dev/ttyUSB*"))]:
    try:
        c = mavutil.mavlink_connection(conn, baud=baud)
    except Exception as e:
        print("SKIP", conn, e); continue
    if c.wait_heartbeat(timeout=6) is not None:
        m = c; link = "%s@%d" % (conn, baud); break
    c.close()
if m is None:
    print("RESULT: NO_HEARTBEAT"); sys.exit(1)
print("Connected on %s (sys=%d comp=%d)\n" % (link, m.target_system, m.target_component))
tgt = (m.target_system, m.target_component)


def set_param(name, value, ptype=mavutil.mavlink.MAV_PARAM_TYPE_INT32):
    m.mav.param_set_send(tgt[0], tgt[1], name.encode(), float(value), ptype)
    t = time.time() + 3
    while time.time() < t:
        pv = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=2)
        if pv and pv.param_id.strip("\x00") == name:
            ok = abs(pv.param_value - value) < 1e-3
            print("  param %-16s -> %s  %s" % (name, int(pv.param_value), "OK" if ok else "MISMATCH"))
            return ok
    print("  param %-16s -> NO RESPONSE (may not exist on this build)" % name)
    return False


def wait_ack(cmd, timeout=4):
    t = time.time() + timeout
    while time.time() < t:
        ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=timeout)
        if ack and ack.command == cmd:
            return ename("MAV_RESULT", ack.result), ack.result
    return "NO_ACK", None


print("Relaxing arming checks:")
set_param("COM_RC_IN_MODE", 4)
set_param("COM_ARM_WO_GPS", 1)
set_param("CBRK_USB_CHK", 197848)
time.sleep(1)

print("\nSwitching to STABILIZED mode ...")
# PX4 main_mode STABILIZED = 7
m.mav.command_long_send(tgt[0], tgt[1], mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 7, 0, 0, 0, 0, 0)
print("  set_mode ack:", wait_ack(mavutil.mavlink.MAV_CMD_DO_SET_MODE)[0])
time.sleep(1)

hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=3)
if hb:
    print("  state now:", ename("MAV_STATE", hb.system_status),
          " mode:", (mavutil.mode_string_v10(hb) if hb else "?"))

print("\n>>> Sending ARM ...")
m.mav.command_long_send(tgt[0], tgt[1], mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                        1, 0, 0, 0, 0, 0, 0)
name, code = wait_ack(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM)
print("  ARM ack:", name)

# verify armed flag + watch throttle for a few seconds
armed = False
t = time.time() + 5
while time.time() < t:
    msg = m.recv_match(type=["HEARTBEAT", "VFR_HUD", "STATUSTEXT"], blocking=True, timeout=1)
    if not msg:
        continue
    if msg.get_type() == "HEARTBEAT":
        armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    elif msg.get_type() == "VFR_HUD":
        print("  throttle=%d%%  (armed=%s)" % (msg.throttle, armed))
    elif msg.get_type() == "STATUSTEXT":
        print("  [%s] %s" % (ename("MAV_SEVERITY", msg.severity), msg.text))

print("\nARMED flag in heartbeat:", armed)

print("\n<<< Sending DISARM (safety) ...")
m.mav.command_long_send(tgt[0], tgt[1], mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                        0, 0, 0, 0, 0, 0, 0)
print("  DISARM ack:", wait_ack(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM)[0])

print("\nRESULT:", "ARM_SUCCEEDED" if armed else ("ARM_REJECTED (%s)" % name))
m.close()
