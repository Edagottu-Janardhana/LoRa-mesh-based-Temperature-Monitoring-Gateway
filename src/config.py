import serial
import struct
import time
import RPi.GPIO as GPIO

UART_PORT = "/dev/ttyAMA3"
BAUD_RATE = 115200
TIMEOUT = 1

BUTTON_PIN = 27

NUM_ENTRIES = 20
HEADER_SIZE = 3
ENTRY_SIZE = 2
PACKET_SIZE = HEADER_SIZE + NUM_ENTRIES * ENTRY_SIZE  # 35 bytes

# ---------------- GPIO SETUP ----------------
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ---------------- UART SETUP ----------------
ser = serial.Serial(UART_PORT, BAUD_RATE, timeout=TIMEOUT)


def read_exact(size):
    """Read exactly <size> bytes from UART."""
    data = b""
    while len(data) < size:
        chunk = ser.read(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def parse_packet(data):
    """Parse STM32 repeater topology packet."""
    fmt = "<HB" + ("BB" * NUM_ENTRIES)
    unpacked = struct.unpack(fmt, data)

    net_id = unpacked[0]
    pkt_type = unpacked[1]

    entries = []
    idx = 2
    for _ in range(NUM_ENTRIES):
        parent = unpacked[idx]
        child = unpacked[idx + 1]
        entries.append((parent, child))
        idx += 2

    return net_id, pkt_type, entries


def save_topology_to_file(net_id, pkt_type, entries):
    """Store parsed packet text into output file."""
    lines = []
    lines.append(f"Net ID: {net_id}")
    lines.append(f"Type  : 0x{pkt_type:02X}")
    lines.append("Entries:")

    for i, (p, c) in enumerate(entries):
        lines.append(f"  {i:02d}. Parent={p}  Child={c}")

    text = "\n".join(lines)

    with open("repeater_topology_packet.txt", "w") as f:
        f.write(text)

    print("[SAVED] repeater_topology_packet.txt")


def send_config_cmd():
    """Sends CONFIG command (0x01) over UART."""
    ser.write(bytes([0x01]))
    print("[UART] Sent CONFIG (0x01)")


# ---------------- MAIN LOOP ----------------
print("Ready. Press button on GPIO 27 to request topology...")

try:
    while True:
        if GPIO.input(BUTTON_PIN) == 0:   # Button pressed (active low)
            print("\n[BUT] Button pressed ? sending CONFIG request")
            send_config_cmd()
            time.sleep(0.2)

            print("[UART] Waiting for topology packet (35 bytes)...")
            data = read_exact(PACKET_SIZE)

            if not data:
                print("[ERR] No data received!")
                continue

            print("[UART] Received raw:", " ".join(f"{b:02X}" for b in data))

            try:
                net_id, pkt_type, entries = parse_packet(data)

                if pkt_type != 0x16:
                    print(f"[WARN] Wrong packet type: 0x{pkt_type:02X}")
                    continue

                print("[OK] Topology packet received.")
                save_topology_to_file(net_id, pkt_type, entries)

            except Exception as e:
                print("[ERR] Parse error:", e)

            # Wait for release to avoid multiple triggers
            while GPIO.input(BUTTON_PIN) == 0:
                time.sleep(0.05)

        time.sleep(0.05)

except KeyboardInterrupt:
    print("Exiting...")

finally:
    GPIO.cleanup()
    ser.close()
