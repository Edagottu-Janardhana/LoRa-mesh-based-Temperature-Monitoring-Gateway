import serial
import struct
import time

UART_PORT = "/dev/ttyAMA3"
BAUD_RATE = 115200
TIMEOUT = 1

NUM_ENTRIES = 20

# Sizes from STM struct
HEADER_SIZE = 3               # uint16_t net_id + uint8_t type
ENTRY_SIZE = 2                # parent + child
PACKET_SIZE = HEADER_SIZE + NUM_ENTRIES * ENTRY_SIZE  # 35 bytes


def read_exact(ser, size):
    data = b""
    while len(data) < size:
        chunk = ser.read(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def parse_topology_packet(data):
    """Parse RepeaterTopologyPacket_t received from STM32"""
    if len(data) != PACKET_SIZE:
        raise ValueError(f"Invalid size {len(data)}, expected {PACKET_SIZE}")

    # struct format:
    # <   little-endian
    # H   uint16_t net_id
    # B   uint8_t  type
    # then 16 entries: BB repeated 16 times
    fmt = "<HB" + ("BB" * NUM_ENTRIES)

    unpacked = struct.unpack(fmt, data)

    net_id = unpacked[0]
    pkt_type = unpacked[1]

    entries = []
    index = 2
    for _ in range(NUM_ENTRIES):
        parent = unpacked[index]
        child = unpacked[index + 1]
        entries.append((parent, child))
        index += 2

    return net_id, pkt_type, entries


def hexdump(prefix, data):
    print(prefix, " ".join(f"{b:02X}" for b in data))


def main():
    ser = serial.Serial(UART_PORT, BAUD_RATE, timeout=TIMEOUT)
    print(f"Listening ({PACKET_SIZE} bytes expected)...")

    while True:
        data = read_exact(ser, PACKET_SIZE)
        if not data:
            continue

        hexdump("RAW:", data)

        try:
            net_id, pkt_type, entries = parse_topology_packet(data)

            if pkt_type != 0x16:
                print(f"Warning: unexpected packet type: 0x{pkt_type:02X}")
                continue

            print("\nRepeater Topology Packet")
            print(f"Net ID  : {net_id}")
            print(f"Type    : 0x{pkt_type:02X}")

            for i, (p, c) in enumerate(entries):
                print(f"  Entry {i:02d}: Parent={p}, Child={c}")

            print("-------------------------------------------\n")

        except Exception as e:
            print("Parse error:", e)
            time.sleep(0.1)


if __name__ == "__main__":
    main()
