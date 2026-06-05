#!/usr/bin/env python3
"""Diagnose whether the Pixhawk is visible to the Raspberry Pi at all."""
import subprocess

def run(cmd):
    print("$ " + cmd)
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        print((out.stdout + out.stderr).rstrip() or "(no output)")
    except Exception as e:
        print("ERROR:", e)
    print("-" * 50)

run("ls -l /dev/ttyACM* /dev/ttyUSB* /dev/serial* 2>&1")
run("lsusb")
run("dmesg | grep -iE 'usb|cdc_acm|ttyACM|pixhawk|px4|fmu|3dr' | tail -n 25")
