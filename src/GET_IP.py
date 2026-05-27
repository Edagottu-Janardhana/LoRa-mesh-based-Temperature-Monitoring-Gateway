# --------------------------------------------------------------------
# PURPOSE:
#   - Continuously check UART buffer.
#   - When a command arrives:
#        • If command == "GET_IP" → return Pi's IP address.
#        • Otherwise → return "INVALID_CMD".
# --------------------------------------------------------------------
'''
import serial
import subprocess

ser = serial.Serial("/dev/ttyAMA4", baudrate=115200, timeout=1)

print("UART listener running. Waiting for command...")

while True:
    if ser.in_waiting > 0:
        cmd = ser.readline().decode().strip()
        print(f"Received: {cmd}")
        if cmd == "GET_IP":
            # Get the IP address
            ip_output = subprocess.getoutput("hostname -I")
            ip = ip_output.strip().split()[0] if ip_output else "NO_IP"
            print(f"Sending IP: {ip}")
            ser.write((ip + "\n").encode())
        else:
            ser.write(b"INVALID_CMD\n")
'''
# --------------------------------------------------------------------
# PURPOSE:
#   - Continuously check UART buffer.
#   - When a command arrives:
#        • If command == "GET_IP" → return Pi's IP address.
#        • Otherwise → return "INVALID_CMD".
#   - Exit cleanly on CTRL+C
# --------------------------------------------------------------------

import serial
import subprocess
import time

PORT = "/dev/ttyAMA4"
BAUD = 115200

try:
    ser = serial.Serial(PORT, baudrate=BAUD, timeout=1)
    print("UART listener running. Waiting for command...")

    while True:
        try:
            if ser.in_waiting > 0:
                raw = ser.readline()

                if not raw:
                    continue

                try:
                    cmd = raw.decode(errors="ignore").strip()
                except Exception:
                    continue

                print(f"Received: {cmd}")

                if cmd == "GET_IP":
                    ip_output = subprocess.getoutput("hostname -I")
                    ip = ip_output.strip().split()[0] if ip_output else "NO_IP"
                    print(f"Sending IP: {ip}")
                    ser.write((ip + "\n").encode())
                else:
                    ser.write(b"INVALID_CMD\n")

            time.sleep(0.05)

        except KeyboardInterrupt:
            print("GET_IP UART exiting cleanly")
            break

finally:
    try:
        if ser and ser.is_open:
            ser.close()
            print("Serial port closed")
    except:
        pass
