
# =======================
# portal.py (Updated: Success Page Fix + AP Fixes)
# =======================
# Fully complete version verified, no missing lines.
# Compatible with Raspberry Pi OS Bookworm.
# Success page is shown BEFORE shutting down AP mode.
# STA switching runs in background -> no reboot needed.

from flask import Flask, request, Response
import subprocess
import threading
import os  
import shlex
import RPi.GPIO as GPIO
import functools
import serial
import time
import struct

ser = serial.Serial("/dev/ttyAMA3", 115200, timeout=1)

LED_PIN = 20    
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.HIGH)#TURNING OFF CONNECTION LED

USERNAME = "admin"
PASSWORD = "1234"

NUM_ENTRIES = 20
HEADER_SIZE = 3
ENTRY_SIZE = 2
#PACKET_SIZE = HEADER_SIZE + NUM_ENTRIES * ENTRY_SIZE   

app = Flask(__name__)

#-------------------UART--------------------
def read_exact(size):
    data = b""
    while len(data) < size:
        chunk = ser.read(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data
# ===========================================================
#  New Full Packet Parser (NetID + Type + 20 topology + 20 dev entries)
# ===========================================================

MAX_REPEATERS = 20
DEV_FMT = "<HB" + ("BB" * MAX_REPEATERS) + ("BBB" + "B") * MAX_REPEATERS
DEV_PACKET_SIZE = struct.calcsize(DEV_FMT)

def build_family_tree(dev_entries, topology_entries):
    # ================================
    # Build repeater_num → dev_id map
    # ================================
    repeater_map = {rnum: devid for devid, rnum in dev_entries if rnum > 0}

    gateway = 1  # root
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

        if parent == child:  # avoid infinite recursion
            continue

        fixed_topology.append((parent, child))

    # ================================
    # Build adjacency list
    # ================================
    children_map = {}
    for parent, child in fixed_topology:
        children_map.setdefault(parent, []).append(child)

    # Sort for consistent ordering
    for k in children_map:
        children_map[k].sort()

    # ================================
    # Recursive pretty tree printer
    # ================================
    def draw(node, prefix="", is_last=True):
        lines = []
        dev_id = repeater_map.get(node, 0)

        # -----------------------------------------
        # GATEWAY (ROOT)
        # -----------------------------------------
        if node == gateway:
            lines.append(f"Gateway(0x{dev_id:06x})")

            if node in children_map:
                lines.append("     |")

            kids = children_map.get(node, [])
            for i, child in enumerate(kids):
                last_child = (i == len(kids) - 1)

                # draw the subtree
                lines.extend(draw(child, "     ", last_child))

                # Add blank vertical separation between R2 and R3
                if not last_child:
                    lines.append("     |")

            return lines

        # -----------------------------------------
        # NON-GATEWAY NODES
        # -----------------------------------------
        connector = "`---> " if is_last else "|---> "
        lines.append(prefix + connector + f"R{node}(0x{dev_id:06x})")

        if node in children_map:
            new_prefix = prefix + ("     " if is_last else "|    ")
            kids = children_map[node]

            # Vertical connector below this node
            lines.append(new_prefix + "|")

            for i, child in enumerate(kids):
                last_child = (i == len(kids) - 1)

                lines.extend(draw(child, new_prefix, last_child))

                # Add blank spacing between children
                if not last_child:
                    lines.append(new_prefix + "|")

        return lines

    # ================================
    # Return complete formatted tree
    # ================================
    return "\n".join(draw(gateway))


def parse_full_packet(raw):
    unpacked = struct.unpack(DEV_FMT, raw)

    net_id = unpacked[0]
    pkt_type = unpacked[1]

    idx = 2

    # Topology entries
    topology = []
    for _ in range(MAX_REPEATERS):
        parent = unpacked[idx]
        child = unpacked[idx + 1]
        topology.append((parent, child))
        idx += 2

    # Dev ID entries
    dev_entries = []
    for _ in range(MAX_REPEATERS):
        d0 = unpacked[idx]
        d1 = unpacked[idx + 1]
        d2 = unpacked[idx + 2]
        repeater_num = unpacked[idx + 3]
        idx += 4

        dev_id = (d0 << 16) | (d1 << 8) | d2
        dev_entries.append((dev_id, repeater_num))

    return net_id, pkt_type, topology, dev_entries


def uart_listener_thread():
    print("[UART LISTENER] Waiting for FULL 123-byte packets...")

    while True:
        raw = read_exact(DEV_PACKET_SIZE)
        if not raw:
            continue

        # Packet type sits after NetID → unpack raw to check type
        pkt_type = raw[2]
        if pkt_type != 0x16:   # Full repeater+devid topology
            continue

        try:
            net_id, pkt_type, topology, dev_entries = parse_full_packet(raw)

            # Build multi-level family tree
            tree_output = build_family_tree(dev_entries, topology)

            # Save to file
            with open("RepeaterTopologyDevIDPacket.txt", "w") as f:
                f.write(tree_output)

            print("[UART LISTENER] Updated RepeaterTopologyDevIDPacket.txt")

        except Exception as e:
            print("UART LISTENER ERROR:", e)
            continue


# --------------------------- AUTH HANDLING ---------------------------
def check_auth(u, p):
    return u == USERNAME and p == PASSWORD

def authenticate():
    return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Login Required"'})

def requires_auth(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return func(*args, **kwargs)
    return wrapper

# --------------------------- CMD RUNNER ---------------------------
def run(cmd):
    print(f" {cmd}")
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.communicate()[0].decode(errors="ignore")
    print(out)
    return p.returncode, out
'''
def send_uart_command(cmd):
    try:
        os.system(f"echo '{cmd}' > /dev/ttyAMA3")
        return "Command Sent"
    except Exception as e:
        return f"Error: {e}"
'''
def send_uart_command(cmd_byte):
    try:
        ser.write(bytes([cmd_byte]))  # send 0x01, 0x02, etc.
        return f"Sent command: {hex(cmd_byte)}"
    except Exception as e:
        return f"Error: {e}"



# --------------------------- STA SWITCH ---------------------------
def sta_background(ssid, password):
    print("Background STA switching started...")
    
    # Start blinking LED to show "connecting to WiFi"
    def blink_led():
        while True:
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(LED_PIN, GPIO.HIGH)
            time.sleep(0.1)

    blink_thread = threading.Thread(target=blink_led, daemon=True)
    blink_thread.start()    
    # 1. Stop AP services
    run("sudo systemctl stop hostapd || true")
    run("sudo systemctl stop dnsmasq || true")

    # 2. Remove NM unmanage wlan0
    run("sudo rm -f /etc/NetworkManager/conf.d/unmanage-wlan0.conf")
    run("sudo systemctl restart NetworkManager")

    # 3. Remove systemd AP static IP file
    run("sudo rm -f /etc/systemd/network/08-wlan0.network")
    run("sudo systemctl restart systemd-networkd")

    # 4. Connect to STA WiFi via nmcli
    ssid_q = shlex.quote(ssid)
    pass_q = shlex.quote(password)

    # try direct connect
    rc, _ = run(f"sudo nmcli device wifi connect {ssid_q} password {pass_q}")
    if rc == 0:
        print("Direct WiFi connect successful.")
        # Turn LED ON (connected)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(1)
        return

    # fallback: create connection profile
    conn = f"conn_{ssid}"
    run(f"sudo nmcli connection delete '{conn}' 2>/dev/null || true")
    run(f"sudo nmcli connection add type wifi ifname wlan0 con-name '{conn}' ssid {ssid_q}")
    run(f"sudo nmcli connection modify '{conn}' wifi-sec.key-mgmt wpa-psk wifi-sec.psk {pass_q}")
    run(f"sudo nmcli connection up '{conn}'")

    print("Fallback WiFi connection attempt completed.")
    
    print("STA mode complete -> stopping portal server.")
    os._exit(0)

# --------------------------- ROUTES ---------------------------
@app.route('/', methods=['GET', 'POST'])
@requires_auth
def index():
    if request.method == 'POST':
        ssid = request.form.get('ssid')
        password = request.form.get('password')

        if not ssid or not password:
            return "Please provide both SSID and password."

        # write to file for debugging
        with open("wifi_credentials.txt", "w") as f:
            f.write(f"{ssid}\n{password}\n")

        # ---------------- SUCCESS PAGE FIRST ----------------
        success_page = """
        <!DOCTYPE html>
        <html>
        <head>
        <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f2f2f2;
            margin: 0;
            height: 100vh;

            display: flex;
            justify-content: center;   /* Center horizontally */
            align-items: center;       /* Center vertically */
            text-align: center;
        }

        .container {
            background: white;
            padding: 25px;
            border-radius: 12px;
            width: 350px;
            box-shadow: 0 0 10px rgba(0,0,0,0.2);
        }
        </style>
        </head>

        <body>
        <div class="container">
            <h2 style="color: green;">WiFi Credentials Saved Successfully</h2>
            <p>You can disconnect from this hotspot.</p>
            <p>It will connect to your WiFi network shortly.</p>
        </div>
        </body>
        </html>
        """


        # start STA switching in background
        threading.Thread(target=sta_background, args=(ssid, password), daemon=True).start()

        return success_page

    # GET request show WiFi form
    return '''
        <!DOCTYPE html>
        <html>
        <head>
        <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f2f2f2;
            height: 100vh;
            margin: 0;
            display: flex;
            align-items: center;   /* Vertical center */
            justify-content: center; /* Horizontal center */
        }
        .container {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0px 0px 10px rgba(0,0,0,0.2);
            width: 300px;
            text-align: center;
        }
        input {
            width: 90%;
            padding: 10px;
            margin-top: 8px;
            border: 1px solid #ccc;
            border-radius: 5px;
        }
        button, input[type="submit"] {
            width: 100%;
            padding: 10px;
            margin-top: 15px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
        }
        button:hover, input[type="submit"]:hover {
            background-color: #45a049;
        }
        </style>
        </head>

        <body>
        <div class="container">
            <h2>Enter Wi-Fi Credentials</h2>
            <form method="POST">
                <input name="ssid" placeholder="Enter SSID" required><br>
                <input name="password" type="password" placeholder="Enter Password" required><br>
                <input type="submit" value="Submit">
            </form>
        </div>
        </body>
        </html>
        '''
    
@app.route('/config', methods=['GET', 'POST'])
@requires_auth
def route_page():
    message = ""
    tree_output = ""

    if request.method == "POST":

        # ---------- SEND CONFIG (first button) ----------
        if "send_cmd" in request.form:
            response = send_uart_command(0x01)
            message = "Sent CONFIG (0x01)"
            time.sleep(0.5)

        # ---------- RETRY BUTTON ----------
        elif "retry" in request.form:
            response = send_uart_command(0x01)
            message = "Retried CONFIG (0x01)"
            time.sleep(0.5)

        # ---------- OK BUTTON ----------
        elif "ok_btn" in request.form:
            response = send_uart_command(0x02)
            message = "Sent OK (0x02)"

        # ---------- Load topology ----------
        try:
            with open("RepeaterTopologyDevIDPacket.txt", "r") as f:
                tree_output = f.read().strip()
            if not tree_output:
                tree_output = "? No topology data available."
        except FileNotFoundError:
            tree_output = "? repeater_topology_packet.txt not found."

    return f"""
    <html>
    <body style='font-family: Arial; padding: 20px;'>

        <h2>UART Control Panel</h2>

        <!-- Send CONFIG button -->
        <form method="POST">
            <button name="send_cmd" type="submit"
                    style='padding: 10px 20px; font-size:16px; background-color: #007bff; color: white;'>
                Send CONFIG Command
            </button>
        </form>

        <p style='margin-top:20px; color:green; font-size:18px;'>
            {message}
        </p>

        <!-- Display topology tree -->
        <pre style="
            background:#f4f4f4;
            padding:15px;
            border-radius:10px;
            font-size:15px;
            border:1px solid #ddd;
            white-space: pre-wrap;
        ">
{tree_output}
        </pre>

        <!-- Retry + OK Buttons -->
        <form method="POST" style="margin-top:20px;">
            <button name="retry" type="submit"
                    style='padding: 10px 20px; font-size:16px; background-color: #6c757d; color: white; margin-right:10px;'>
                Retry (Send CONFIG)
            </button>

            <button name="ok_btn" type="submit"
                    style='padding: 10px 20px; font-size:16px; background-color: #28a745; color: white;'>
                OK
            </button>
        </form>

    </body>
    </html>
    """


def get_wlan_ip():
    try:
        ip = subprocess.getoutput("ip -4 addr show wlan0 | grep inet | awk '{print $2}' | cut -d/ -f1")
        return ip if ip else "192.168.4.1"
    except:
        return "192.168.4.1"


if __name__ == '__main__':
    # Start UART listener thread
    threading.Thread(target=uart_listener_thread, daemon=True).start()

    ip = get_wlan_ip()
    print(f"Portal running at:  http://{ip}")
    print("Access this page from your phone or laptop.")
    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.protocol_version = "HTTP/1.1"  # optional cleanup

    # Suppress Flask warning banner
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    app.run(host='0.0.0.0', port=80, debug=False, use_reloader=False)

