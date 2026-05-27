"""
UART Receiver for SensorDataPacket_t
------------------------------------
This script reads 168-byte packets from /dev/ttyS0,
corresponding to SensorDataPacket_t in C.
Each packet includes header + 20 SensorDataEntry_t.
"""

import serial
import struct

# UART configuration
ser = serial.Serial('/dev/ttyAMA3', 115200, timeout=1)

PACKET_SIZE = 169  # bytes
ENTRY_SIZE = 8
MAX_SENSORS = 20

while True:
    data = ser.read(PACKET_SIZE)
    print(data)

    if len(data) == PACKET_SIZE:
        print(f"\n {len(data)} bytes received")

        # -------------------------------
        # Unpack header
        # -------------------------------
        header_fmt = "<H B 3s B B B"  # little-endian (<)
        header_size = struct.calcsize(header_fmt)
        header = struct.unpack_from(header_fmt, data, 0)

        net_id, pkt_type, repeater_id, sender, receiver, count = header
        print(f"Net ID: {net_id}")
        print(f"Type: {pkt_type}")
        print(f"Repeater ID: {repeater_id.hex()}")
        print(f"Sender: {sender}")
        print(f"Receiver: {receiver}")
        print(f"Sensor Count: {count}")

        # -------------------------------
        # Unpack all entries
        # -------------------------------
        entry_fmt = "<3sHHb"
        entries = []

        for i in range(MAX_SENSORS):
            offset = header_size + i * ENTRY_SIZE
            entry_data = struct.unpack_from(entry_fmt, data, offset)
            dev_id_bytes, temp1, temp2, rssi = entry_data
            dev_id = dev_id_bytes.hex().upper()

            entries.append({
                "dev_id": dev_id,
                "temp1": temp1,
                "temp2": temp2,
                "rssi": rssi
            })

        # -------------------------------
        # Print received entries
        # -------------------------------
        print("\n--- Sensor Entries ---")
        for i, e in enumerate(entries, start=1):
            print(f"{i:02d}: DEV={e['dev_id']} T1={e['temp1']} T2={e['temp2']} RSSI={e['rssi']}")

    else:
        print("Waiting for valid packet...")
