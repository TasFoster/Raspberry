#!/usr/bin/env python3
"""Reboot the PX4 flight controller, wait for re-init, then re-check state and
re-attempt a bench ARM (props off). Handles the USB port dropping during reboot."""
import sys, time, glob, os
try:
    from pymavlink import mavutil
except ImportError:
    print("PYMAVLINK_MISSING"); sys.exit(2)


def ename(enum, val):
    try:
        return mavutil.mavlink.enums[enum][val].name
    except Exception:
        return str(val)


def connect(timeout_total=40):
    """Wait for /dev/ttyACM* to appear and return a heartbeat-confirmed connection."""
    end = time.time() + timeout_total
    while time.time() < end:
        ports = sorted(glob.glob("/dev/ttyACM*"))
        for p in ports:
            try:
                c = mavutil.mavlink_connection(p, baud=115200)
            except Exception:
                continue
            if c.wait_heartbeat(timeout=4) is not None:
                return c, p
            c.close()
        time.sleep(1)
    return None, None


m, port = connect(15)
if m is None:
    print("RESULT: NO_HEARTBEAT (initial)"); sys.exit(1)
tgt = (m.target_system, m.target_component)
hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=3)
print("Before reboot: state=%s mode=%s on %s" % (
    ename("MAV_STATE", hb.system_status), mavutil.mode_string_v10(hb), port))

print("\n>>> Rebooting flight controller ...")
m.mav.command_long_send(tgt[0], tgt[1],
                        mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, 0,
                        1, 0, 0, 0, 0, 0, 0)  # param1=1 -> reboot autopilot
time.sleep(2)
m.close()

print("Waiting for FC to come back ...")
time.sleep(8)
m, port = connect(40)
if m is None:
    print("RESULT: FC_DID_NOT_RETURN"); sys.exit(1)
tgt = (m.target_system, m.target_component)
print("Reconnected on %s" % port)

# give the estimator time to settle, sampling state
print("\nWaiting for STANDBY (up to 25s) ...")
standby = False
end = time.time() + 25
last = None
while time.time() < end:
    hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
    if not hb:
        continue
    st = ename("MAV_STATE", hb.system_status)
    if st != last:
        print("  state:", st)
        last = st
    if hb.system_status == mavutil.mavlink.MAV_STATE_STANDBY:
        standby = True
        break

# re-apply bench params (reboot may not be needed for these, but ensure)
for n, v in [("COM_RC_IN_MODE", 4), ("COM_ARM_WO_GPS", 1), ("CBRK_USB_CHK", 197848)]:
    m.mav.param_set_send(tgt[0], tgt[1], n.encode(), float(v),
                         mavutil.mavlink.MAV_PARAM_TYPE_INT32)
time.sleep(1)

# set STABILIZED
m.mav.command_long_send(tgt[0], tgt[1], mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 7, 0, 0, 0, 0, 0)
time.sleep(1)

print("\n>>> Sending ARM ...")
m.mav.command_long_send(tgt[0], tgt[1], mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                        1, 0, 0, 0, 0, 0, 0)
ack_result, armed = None, False
end = time.time() + 5
while time.time() < end:
    msg = m.recv_match(type=["STATUSTEXT", "COMMAND_ACK", "HEARTBEAT"], blocking=True, timeout=1)
    if not msg:
        continue
    t = msg.get_type()
    if t == "STATUSTEXT":
        print("  [%s] %s" % (ename("MAV_SEVERITY", msg.severity), msg.text))
    elif t == "COMMAND_ACK" and msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
        ack_result = ename("MAV_RESULT", msg.result)
        print("  >> ARM ACK:", ack_result)
    elif t == "HEARTBEAT":
        armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

print("\nARMED flag:", armed)
# safety disarm
m.mav.command_long_send(tgt[0], tgt[1], mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                        0, 0, 0, 0, 0, 0, 0)
time.sleep(1)
print("Sent safety DISARM.")
print("\nRESULT:", "ARM_SUCCEEDED" if armed else ("ARM_REJECTED (%s)" % ack_result))
m.close()
