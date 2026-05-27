'''
UART Receiver with File Logging
-------------------------------
Reads 169-byte packets from /dev/ttyAMA3 corresponding to SensorDataPacket_t.
Each packet includes header + 20 SensorDataEntry_t.

Logs each sensor entry into uart_data.txt in format:
|##|net_id|DEV_ID|t1|battery|rssi|**|
'''
import serial
import struct
import os

# UART Configuration
UART_PORT = '/dev/ttyAMA3'
BAUD_RATE = 115200
PACKET_SIZE = 169
ENTRY_SIZE = 8
MAX_SENSORS = 20
DATA_FILE = "uart_data.txt"

# Open serial port
ser = serial.Serial(UART_PORT, BAUD_RATE, timeout=1)
print("?? UART open. Waiting for data...")

# Create file if not exists
if not os.path.exists(DATA_FILE):
    open(DATA_FILE, "w").close()

while True:
    data = ser.read(PACKET_SIZE)

    if len(data) == PACKET_SIZE:
        print(f"\n?? {len(data)} bytes received")

        # -------------------------------
        # Unpack header
        # -------------------------------
        header_fmt = "<H B 3s B B B"
        header_size = struct.calcsize(header_fmt)
        net_id, pkt_type, repeater_id, sender, receiver, count = struct.unpack_from(header_fmt, data, 0)

        repeater_hex = repeater_id.hex().upper()

        print(f"Net ID: {net_id} | Type: {pkt_type} | Repeater: {repeater_hex} "
              f"| Sender: {sender} | Receiver: {receiver} | Count: {count}")

        # -------------------------------
        # Unpack all sensor entries
        # -------------------------------
        entry_fmt = "<3sHHb"   # DEV_ID(3) | T1(2) | BAT | RSSI(1)
        entries = []

        for i in range(MAX_SENSORS):
            offset = header_size + i * ENTRY_SIZE
            dev_id_bytes, t1, battery, rssi = struct.unpack_from(entry_fmt, data, offset)

            dev_id = dev_id_bytes.hex().upper()
            
            # Decode 16-bit temperature to float
            temp_c = (t1 - 500) / 10.0
            
            # Decode 16-bit battery
            bat = (battery - 500) / 10.0
            
            entries.append({
                "net_id": net_id,
                "repeater_id":repeater_hex,
                "dev_id": dev_id,
                "t1": temp_c,
                "battery": bat,
                "rssi": rssi               # raw signed value
            })

        # -------------------------------
        # Log entries to file (NEW FORMAT)
        # -------------------------------
        with open(DATA_FILE, "w") as f:
            for e in entries:
                packet = f"|##|{e['net_id']}|{e['repeater_id']}|{e['dev_id']}|{e['t1']:.1f}|{e['battery']}|{e['rssi']}|**|\n"
                f.write(packet)

        print(f"?? Logged {MAX_SENSORS} entries to {DATA_FILE}")

#    else:
#        print("? Waiting for valid packet...")
