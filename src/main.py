# =======================
# main.py 
# =======================
# This version includes:
#  Full AP mode fixes for Raspberry Pi OS Bookworm
#  wlan0 unmanaged via NetworkManager
#  systemd-networkd static IP for AP
#  Correct dnsmasq + hostapd configs
#  Correct restart ordering
#  No reboot required
#
# Author: Janardhan

import subprocess
import threading
import time
import signal
import os
import sys
import RPi.GPIO as GPIO
from gpiozero import Device, Button
exit_event = threading.Event()

# ----------------------------- CONFIG ------------------------------
# Pin definitions and AP-mode configuration settings
POWERLED_PIN = 16
BUTTON_PIN = 27
CONNECTION_LED_PIN = 20
blink_flag = False
AP_SSID = "Pi_Config_AP"
AP_PASSWORD = "raspberry123"
AP_IP = "192.168.4.1/24"
AP_NETFILE = "/etc/systemd/network/08-wlan0.network"
AP_UNMAN_NM = "/etc/NetworkManager/conf.d/unmanage-wlan0.conf"

# --------------------------- GPIO Setup -----------------------------
# Initialize LEDs and alert/tamper pin
GPIO.setmode(GPIO.BCM)
GPIO.setup(POWERLED_PIN, GPIO.OUT)
GPIO.output(POWERLED_PIN, GPIO.HIGH)  # turning OFF LED briefly
time.sleep(0.25)
GPIO.output(POWERLED_PIN, GPIO.LOW)   # turning ON LED

GPIO.setup(CONNECTION_LED_PIN, GPIO.OUT)
GPIO.output(CONNECTION_LED_PIN, GPIO.HIGH)

#Tamper input pin (active LOW)
ALERT_PIN = 24

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(ALERT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

button = Button(BUTTON_PIN)

# -------------------------------------------------------------------
# FUNCTION: handle_exit
# PURPOSE:
#  - Handles CTRL+C or service stop
#  - Cleanly terminates uart.py, GET_IP.py, and MQTT/BACnet processes
#  - Cleans GPIO before exit
# -------------------------------------------------------------------
'''
def handle_exit(sig, frame):
    print("\nCTRL+C detected. Cleaning up...")

    try:
        if 't_uart' in globals() and t_uart:
            os.kill(t_uart.pid, signal.SIGKILL)
            print("Killed uart.py")
    except:
        pass

    try:
        if 't_ip' in globals() and t_ip:
            os.kill(t_ip.pid, signal.SIGKILL)
            print("Killed GET_IP.py")
    except:
        pass

    try:
        if 'current_process' in globals() and current_process:
            os.kill(current_process.pid, signal.SIGKILL)
            print("Killed child process")
    except:
        pass

    GPIO.cleanup()
    print("GPIO cleaned. Exiting.")
    sys.exit(0)
'''
def handle_exit(sig, frame):
    print("\nCTRL+C detected. Cleaning up...")

    # 1️⃣ Tell all threads to stop
    exit_event.set()

    # 2️⃣ Give threads time to exit
    time.sleep(0.5)

    # 3️⃣ Kill child processes
    for name, proc in [("uart.py", t_uart), ("GET_IP.py", t_ip), ("child", current_process)]:
        try:
            if proc:
                proc.terminate()
                proc.wait(timeout=1)
                print(f"Killed {name}")
        except:
            pass

    # 4️⃣ GPIO cleanup MUST be last
    try:
        GPIO.cleanup()
        print("GPIO cleaned.")
    except:
        pass

    print("Exiting cleanly.")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

# -------------------------------------------------------------------
# FUNCTION: tamper_thread
# PURPOSE:
#  - Continuously monitors tamper GPIO pin
#  - Measures pulse width to identify tamper type
#  - Writes tamper event to tamper_detection.txt
#  - Avoids writing repeatedly if same value
# -------------------------------------------------------------------
def tamper_thread():
    print("Tamper thread started...")
    last_msg = ""

    while not exit_event.is_set():
        try:
            if GPIO.input(ALERT_PIN) == 0:
                start = time.time()

                while GPIO.input(ALERT_PIN) == 0 and not exit_event.is_set():
                    time.sleep(0.001)

                pulse_width = time.time() - start

                if pulse_width < 0.15:
                    msg = "TOP_TAMPER"
                elif pulse_width < 0.30:
                    msg = "BOTTOM_TAMPER"
                else:
                    msg = "TAMPER_BOTH"

                if msg != last_msg:
                    print("Detected:", msg)
                    with open("tamper_detection.txt", "w") as f:
                        f.write(msg)
                    last_msg = msg
        except RuntimeError:
            break  # GPIO already cleaned

        time.sleep(0.005)

    print("Tamper thread exited cleanly")

'''
def tamper_thread():
    print("Tamper thread started...")

    last_msg = ""

    while True:
        if GPIO.input(ALERT_PIN) == 0:  # active LOW detection
            start = time.time()

            while GPIO.input(ALERT_PIN) == 0:
                time.sleep(0.001)

            pulse_width = time.time() - start

            if pulse_width < 0.15:
                msg = "TOP_TAMPER"
            elif pulse_width < 0.30:
                msg = "BOTTOM_TAMPER"
            else:
                msg = "TAMPER_BOTH"

            print("Detected:", msg)

            if msg != last_msg:
                with open("tamper_detection.txt", "w") as f:
                    f.write(msg)
                last_msg = msg

        time.sleep(0.005)
'''

# -------------------------------------------------------------------
# FUNCTION: force_sta_mode_on_boot
# PURPOSE:
#  - Removes AP-mode configuration files
#  - Ensures Pi always boots in STA mode (not AP)
#  - Restarts NetworkManager + systemd-networkd
# -------------------------------------------------------------------
def force_sta_mode_on_boot():
    print("Forcing STA mode on boot...")

    if os.path.exists("/etc/NetworkManager/conf.d/unmanage-wlan0.conf"):
        os.remove("/etc/NetworkManager/conf.d/unmanage-wlan0.conf")
        print("Removed unmanage-wlan0.conf")

    if os.path.exists("/etc/systemd/network/08-wlan0.network"):
        os.remove("/etc/systemd/network/08-wlan0.network")
        print("Removed 08-wlan0.network")

    os.system("sudo systemctl restart NetworkManager")
    os.system("sudo systemctl restart systemd-networkd")

    print("STA mode ready. Continuing normal startup...")

# -------------------------------------------------------------------
# FUNCTION: led_blink
# PURPOSE:
#  - Blinks Wi-Fi LED repeatedly while AP mode is active
# -------------------------------------------------------------------
def led_blink():
    while blink_flag:
        GPIO.output(CONNECTION_LED_PIN, GPIO.LOW)
        time.sleep(0.4)
        GPIO.output(CONNECTION_LED_PIN, GPIO.HIGH)
        time.sleep(0.4)

# --------------------------- Helpers ------------------------------
# FUNCTION: run
# PURPOSE: Prints and executes system commands
def run(cmd):
    print(f" {cmd}")
    return os.system(cmd)

# FUNCTION: write_file
# PURPOSE: Writes configuration text files for AP mode
def write_file(path, content):
    print(f" Writing {path}")
    with open(path, "w") as f:
        f.write(content)

# -------------------------------------------------------------------
# FUNCTIONS: setup_unmanage_nm, setup_systemd_networkd, setup_dnsmasq, setup_hostapd
# PURPOSE:
#  - Configure required services for AP mode
#  - Create config files and restart services
# -------------------------------------------------------------------
def setup_unmanage_nm():
    write_file(AP_UNMAN_NM,
"""
[keyfile]
unmanaged-devices=interface-name:wlan0
""")
    run("sudo systemctl restart NetworkManager")

def setup_systemd_networkd():
    write_file(AP_NETFILE,
        f"""
[Match]
Name=wlan0

[Network]
Address={AP_IP}
ConfigureWithoutCarrier=yes
""")
    run("sudo systemctl enable --now systemd-networkd")
    run("sudo systemctl restart systemd-networkd")

def setup_dnsmasq():
    run("sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig 2>/dev/null || true")
    write_file("/etc/dnsmasq.conf",
"""
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
""")
    run("sudo systemctl restart dnsmasq")

def setup_hostapd():
    write_file("/etc/hostapd/hostapd.conf",
        f"""
interface=wlan0
driver=nl80211
ssid={AP_SSID}
hw_mode=g
channel=7
wmm_enabled=0
auth_algs=1
ignore_broadcast_ssid=0

# WPA2 Security
wpa=2
wpa_passphrase={AP_PASSWORD}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
""")
    run("sudo sed -i 's|#DAEMON_CONF=.*|DAEMON_CONF=\"/etc/hostapd/hostapd.conf\"|' /etc/default/hostapd")
    run("sudo systemctl unmask hostapd")
    run("sudo systemctl restart hostapd")

# -------------------------------------------------------------------
# FUNCTION: start_ap_services
# PURPOSE:
#  - Starts all AP-related services in order
# -------------------------------------------------------------------
def start_ap_services():
    run("sudo rfkill unblock wifi")
    run("sudo systemctl stop NetworkManager")
    run("sudo systemctl restart systemd-networkd")
    run("sudo systemctl restart dnsmasq")
    run("sudo systemctl enable --now hostapd")
    run("sudo systemctl start NetworkManager")

# -------------------------------------------------------------------
# FUNCTION: start_ap_mode
# PURPOSE:
#  - Activates AP mode
#  - Starts captive portal
#  - Restarts gateway into STA mode afterwards
# -------------------------------------------------------------------
def start_ap_mode():
    global blink_flag
    print("Starting AP Mode...")

    blink_flag = True
    threading.Thread(target=led_blink, daemon=True).start()

    setup_unmanage_nm()
    setup_systemd_networkd()
    setup_dnsmasq()
    setup_hostapd()
    start_ap_services()

    print(f"AP LIVE  SSID={AP_SSID}  IP=192.168.4.1")
    print("Opening portal... http://192.168.4.1")

    subprocess.run(["python3", "portal.py"])

    blink_flag = False
    GPIO.output(CONNECTION_LED_PIN, GPIO.LOW)

    print("Restarting main.py after portal exit...")

    try:
        os.kill(t_uart.pid, signal.SIGKILL)
        print("Killed old uart.py")
    except:
        print("uart.py already stopped.")
    
    exit_event.set()
    time.sleep(0.5)
    GPIO.cleanup()

    os.execv(sys.executable, ["python3", "main.py"])

# -------------------------------------------------------------------
# FUNCTION: start_script
# PURPOSE:
#  - Spawns child Python scripts (uart.py, GET_IP.py, mqtt.py/bacnet.py)
# -------------------------------------------------------------------
def start_script(name):
    return subprocess.Popen(["python3", "-u", name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

# -------------------------------------------------------------------
# FUNCTION: stream_output
# PURPOSE:
#  - Reads output from child processes and prints with tags
# -------------------------------------------------------------------
def stream_output(proc, tag):
    for line in iter(proc.stdout.readline, b""):
        print(f"[{tag}] {line.decode().strip()}")

current_process = None
current_thread = None
mode = None

# -------------------------------------------------------------------
# FUNCTION: button_loop
# PURPOSE:
#  - Monitors AP button
#  - Detects long press (≥2 sec) to switch into AP mode
#  - Stops running scripts before entering AP mode
# -------------------------------------------------------------------
def button_loop():
    print("Waiting for AP button...")
    press_start = None

    while not exit_event.is_set():
        if button.is_pressed:
            if press_start is None:
                press_start = time.time()
            else:
                if time.time() - press_start >= 2:
                    print("Long press detected -> Entering AP Mode")

                    try:
                        if current_process:
                            os.kill(current_process.pid, signal.SIGKILL)
                            print("Killed mqtt/bacnet script")
                    except:
                        pass

                    try:
                        if t_uart:
                            os.kill(t_uart.pid, signal.SIGKILL)
                            print("Killed uart.py before AP mode")
                    except:
                        pass

                    try:
                        if t_ip:
                            os.kill(t_ip.pid, signal.SIGKILL)
                            print("Killed GET_IP.py before AP mode")
                    except:
                        pass

                    start_ap_mode()

                    press_start = None
                    time.sleep(1)

        else:
            press_start = None

        time.sleep(0.1)

threading.Thread(target=button_loop).start()

# -------------------------------------------------------------------
# Start UART and IP scripts in background
# -------------------------------------------------------------------
t_uart = start_script("uart.py")
threading.Thread(target=stream_output, args=(t_uart, "UART"), daemon=True).start()

t_ip = start_script("GET_IP.py")
threading.Thread(target=stream_output, args=(t_ip, "GETIP_UART"), daemon=True).start()

# -------------------------------------------------------------------
# FUNCTION: is_eth
# PURPOSE:
#  - Detects whether Ethernet is active (switches to BACnet mode)
# -------------------------------------------------------------------
def is_eth():
    return "inet" in subprocess.getoutput("ip -4 addr show eth0 | grep inet")

# -------------------------------------------------------------------
# FUNCTION: is_wifi_connected
# PURPOSE:
#  - Returns True if connected to a Wi-Fi network
# -------------------------------------------------------------------
def is_wifi_connected():
    ssid = subprocess.getoutput("iwgetid -r").strip()
    return ssid != ""

# -------------------------------------------------------------------
# FUNCTION: update_wifi_led
# PURPOSE:
#  - Updates LED state depending on Wi-Fi connection status
# -------------------------------------------------------------------
def update_wifi_led():
    if is_wifi_connected():
        GPIO.output(CONNECTION_LED_PIN, GPIO.LOW)
    else:
        GPIO.output(CONNECTION_LED_PIN, GPIO.HIGH)

# -------------------------------------------------------------------
# FUNCTION: main
# PURPOSE:
#  - Initializes STA mode
#  - Starts tamper detection thread
#  - Selects between MQTT or BACnet mode based on Ethernet detection
#  - Monitors Wi-Fi LED status
# -------------------------------------------------------------------
def main():
    global current_process, current_thread, mode
    force_sta_mode_on_boot()

    threading.Thread(target=tamper_thread).start()

    while True:
        update_wifi_led()
        time.sleep(2)

        new_mode = "bacnet" if is_eth() else "mqtt"

        if new_mode != mode:
            print("====================================")
            print(f"[MODE_SWITCH] REQUESTED: {mode} → {new_mode}")
            print(f"[MODE_SWITCH] Killing PID: {current_process.pid if current_process else 'None'}")
            print("====================================")
            
            if current_process:
                current_process.terminate()
                current_thread.join()

            print(f"Starting {new_mode}.py...")
            current_process = start_script(f"{new_mode}.py")
            current_thread = threading.Thread(target=stream_output, args=(current_process, new_mode.upper()), daemon=True)
            current_thread.start()
            mode = new_mode

        time.sleep(3)

if __name__ == "__main__":
    main()

