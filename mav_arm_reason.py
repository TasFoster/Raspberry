#!/usr/bin/env python3
"""Send ARM and capture the exact PX4 denial reason (STATUSTEXT) + current state.
Safe: if rejected, motors do not spin (props are off anyway)."""
import sys, time, glob
try:
    from pymavlink import mavutil
except ImportError:
    print("PYMAVLINK_MISSING"); sys.exit(2)


def ename(enum, val):
    try:
        return mavutil.mavlink.enums[enum][val].name
    except Exception:
        return str(val)


m = None
for conn, baud in [("/dev/ttyACM0", 115200)] + [(p, 115200) for p in sorted(glob.glob("/dev/ttyUSB*"))]:
    try:
        c = mavutil.mavlink_connection(conn, baud=baud)
    except Exception:
        continue
    if c.wait_heartbeat(timeout=6) is not None:
        m = c; break
    c.close()
if m is None:
    print("RESULT: NO_HEARTBEAT"); sys.exit(1)
tgt = (m.target_system, m.target_component)
print("Connected (sys=%d comp=%d)\n" % tgt)

# current state snapshot
hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=3)
if hb:
    print("State:", ename("MAV_STATE", hb.system_status),
          " mode:", mavutil.mode_string_v10(hb),
          " armed:", bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED))

print("\nSending ARM and capturing all STATUSTEXT for 4s ...\n")
m.mav.command_long_send(tgt[0], tgt[1], mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                        1, 0, 0, 0, 0, 0, 0)
ack_result = None
deadline = time.time() + 4
while time.time() < deadline:
    msg = m.recv_match(type=["STATUSTEXT", "COMMAND_ACK"], blocking=True, timeout=1)
    if not msg:
        continue
    if msg.get_type() == "STATUSTEXT":
        print("  [%s] %s" % (ename("MAV_SEVERITY", msg.severity), msg.text))
    elif msg.get_type() == "COMMAND_ACK" and msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
        ack_result = ename("MAV_RESULT", msg.result)
        print("  >> ARM ACK:", ack_result)

# make sure it's disarmed
m.mav.command_long_send(tgt[0], tgt[1], mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                        0, 0, 0, 0, 0, 0, 0)
print("\nARM ack was:", ack_result)
m.close()
