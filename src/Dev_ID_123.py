'''
#printing
import serial
import struct

MAX_REPEATERS = 20

# Open UART
ser = serial.Serial("/dev/ttyAMA3", 115200, timeout=1)

# Struct format:
# < = little-endian
# H = uint16_t (net_id)
# B = uint8_t (type)
# (BB)*20 = 20 parent/child pairs
# (3B B)*20 = 20 entries of dev_id[3] + repeater_num
fmt = "<HB" + ("BB" * MAX_REPEATERS) + ("BBB" + "B") * MAX_REPEATERS
PACKET_SIZE = struct.calcsize(fmt)

print("Expecting packet size:", PACKET_SIZE)

def read_exact(size):
    data = b""
    while len(data) < size:
        chunk = ser.read(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data

while True:
    print("Waiting for packet...")
    raw = read_exact(PACKET_SIZE)

    if raw is None:
        print("No data received")
        continue

    unpacked = struct.unpack(fmt, raw)

    # ---- Extract fields ----
    net_id = unpacked[0]
    pkt_type = unpacked[1]

    print("\n==============================")
    print(f"Net ID       : {net_id}")
    print(f"Packet Type  : {hex(pkt_type)}")

    idx = 2

    print("\n--- Repeater Topology (Parent → Child) ---")
    for i in range(MAX_REPEATERS):
        parent = unpacked[idx]
        child = unpacked[idx + 1]
        idx += 2
        print(f"Entry {i+1:02}: Parent={parent}, Child={child}")

    print("\n--- Repeater DevID Assignments ---")
    for i in range(MAX_REPEATERS):
        dev_id_0 = unpacked[idx]
        dev_id_1 = unpacked[idx + 1]
        dev_id_2 = unpacked[idx + 2]
        repeater_num = unpacked[idx + 3]
        idx += 4

        dev_id = (dev_id_0 << 16) | (dev_id_1 << 8) | dev_id_2

        print(f"Device {i+1:02}: DevID={dev_id:#06x}, RepeaterNum={repeater_num}")

    print("==============================\n")
'''
import serial
import struct

MAX_REPEATERS = 20

# Open UART
ser = serial.Serial("/dev/ttyAMA3", 115200, timeout=1)

# Struct format
fmt = "<HB" + ("BB" * MAX_REPEATERS) + ("BBB" + "B") * MAX_REPEATERS
PACKET_SIZE = struct.calcsize(fmt)
print("Expecting packet size:", PACKET_SIZE)


# ===============================================================
# Build ASCII Family Tree
# ===============================================================
'''
def build_family_tree(dev_entries, topology_entries):

    # repeater_num → dev_id mapping
    repeater_map = {rnum: devid for devid, rnum in dev_entries if rnum > 0}

    # Gateway is repeater_num = 1
    gateway_id = repeater_map.get(1, None)

    if gateway_id is None:
        gateway_id = 0
        print("WARNING: Gateway repeater_num=1 not found!")

    # Find children attached to gateway (Parent = 0)
    children = []
    for parent, child in topology_entries:
        if parent == 0 and child in repeater_map:
            children.append((child, repeater_map[child]))

    # Build ASCII tree
    tree = []
    tree.append(f"Gateway(0x{gateway_id:06x})")

    for idx, (rnum, devid) in enumerate(children):
        connector = "`--" if idx == len(children) - 1 else "|--"
        tree.append(f"{connector} R{rnum}(0x{devid:06x})")

    return "\n".join(tree)
##########################################
def build_family_tree(dev_entries, topology_entries):
    # repeater_num → dev_id
    repeater_map = {rnum: devid for devid, rnum in dev_entries if rnum > 0}

    gateway = 1  # Root repeater number
    gateway_dev = repeater_map.get(gateway, 0)

    fixed_topology = []
    for parent, child in topology_entries:
        if child == 0:
            continue

        # Convert parent=0 → gateway
        if parent == 0:
            parent = gateway

        # PREVENT SELF-LOOP (very important)
        if parent == child:
            continue

        fixed_topology.append((parent, child))

    # Build adjacency
    children_map = {}
    for parent, child in fixed_topology:
        children_map.setdefault(parent, []).append(child)

    # Recursive tree rendering
    def draw(node, prefix="", is_last=True):
        lines = []
        dev_id = repeater_map.get(node, 0)

        if node == gateway:
            lines.append(f"Gateway(0x{dev_id:06x})")
        else:
            connector = "`-- " if is_last else "|-- "
            lines.append(prefix + connector + f"R{node}(0x{dev_id:06x})")

        if node in children_map:
            new_prefix = prefix + ("    " if is_last else "|   ")
            kids = children_map[node]

            for i, c in enumerate(kids):
                last = (i == len(kids) - 1)
                lines.extend(draw(c, new_prefix, last))

        return lines

    return "\n".join(draw(gateway))
'''
def build_family_tree(dev_entries, topology_entries):
    # ================================
    # Build repeater_num → dev_id map
    # ================================
    repeater_map = {rnum: devid for devid, rnum in dev_entries if rnum > 0}

    gateway = 1  # Root repeater number
    gateway_dev = repeater_map.get(gateway, 0)

    # ================================
    # Fix topology (convert parent=0 and remove loops)
    # ================================
    fixed_topology = []
    for parent, child in topology_entries:

        if child == 0:
            continue

        if parent == 0:
            parent = gateway

        if parent == child:
            continue  # avoid infinite recursion

        fixed_topology.append((parent, child))

    # ================================
    # Build adjacency list
    # ================================
    children_map = {}
    for parent, child in fixed_topology:
        children_map.setdefault(parent, []).append(child)

    # Sort children for stable tree order
    for k in children_map:
        children_map[k].sort()

    # ================================
    # Recursive pretty tree printer
    # ================================
    def draw(node, prefix="", is_last=True):
        lines = []
        dev_id = repeater_map.get(node, 0)

        # -------------------------------------
        # GATEWAY (ROOT) — special formatting
        # -------------------------------------
        if node == gateway:
            lines.append(f"Gateway(0x{dev_id:06x})")

            # Print only ONE vertical line under gateway
            if node in children_map:
                lines.append("     |")

            kids = children_map.get(node, [])
            for i, child in enumerate(kids):
                last_child = (i == len(kids) - 1)
                # Prefix for gateway children starts with 5 spaces
                lines.extend(draw(child, "     ", last_child))

            return lines

        # -------------------------------------
        # NON-GATEWAY NODE
        # -------------------------------------
        connector = "`---> " if is_last else "|---> "
        lines.append(prefix + connector + f"R{node}(0x{dev_id:06x})")

        # If this node has children, draw them
        if node in children_map:
            new_prefix = prefix + ("     " if is_last else "|    ")
            kids = children_map[node]

            # Print a vertical bar under this repeater before its children
            lines.append(new_prefix + "|")

            for i, child in enumerate(kids):
                last_child = (i == len(kids) - 1)
                lines.extend(draw(child, new_prefix, last_child))

        return lines

    # Return complete tree string
    return "\n".join(draw(gateway))


# ===============================================================
# Read exact bytes
# ===============================================================
def read_exact(size):
    data = b""
    while len(data) < size:
        chunk = ser.read(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data


# ===============================================================
# Main loop
# ===============================================================
while True:

    print("\nWaiting for packet...")
    raw = read_exact(PACKET_SIZE)

    if raw is None:
        print("No data received")
        continue

    unpacked = struct.unpack(fmt, raw)

    net_id = unpacked[0]
    pkt_type = unpacked[1]

    print("\n==============================")
    print(f"Net ID       : {net_id}")
    print(f"Packet Type  : 0x{pkt_type:02X}")

    idx = 2

    # --------- TOPOLOGY ENTRIES ------------
    print("\n--- Repeater Topology (Parent → Child) ---")
    topology_entries = []

    for i in range(MAX_REPEATERS):
        parent = unpacked[idx]
        child = unpacked[idx + 1]
        idx += 2
        topology_entries.append((parent, child))
        print(f"Entry {i+1:02}: Parent={parent}, Child={child}")

    # --------- DEV ENTRIES ------------
    print("\n--- Repeater DevID Assignments ---")
    dev_entries = []

    for i in range(MAX_REPEATERS):
        d0 = unpacked[idx]
        d1 = unpacked[idx + 1]
        d2 = unpacked[idx + 2]
        repeater_num = unpacked[idx + 3]
        idx += 4

        dev_id = (d0 << 16) | (d1 << 8) | d2
        dev_entries.append((dev_id, repeater_num))

        print(f"Device {i+1:02}: DevID=0x{dev_id:06X}, RepeaterNum={repeater_num}")

    print("==============================")

    # ============================================================
    # Build and Save Family Tree
    # ============================================================
    tree_output = build_family_tree(dev_entries, topology_entries)

    print("\n--- FAMILY TREE ---")
    print(tree_output)

    with open("RepeaterTopologyDevIDPacket.txt", "w") as f:
        f.write(tree_output)

    print("\nSaved to RepeaterTopologyDevIDPacket.txt")
