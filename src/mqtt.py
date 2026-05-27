# ==============================================================
# mqtt.py (TLS-enabled)
# ==============================================================
# PURPOSE:
#   - Connect Raspberry Pi to Wi-Fi using nmcli
#   - Maintain MQTT client connection with TLS support
#   - Publish UART sensor data from uart_data.txt
#   - Publish tamper events from tamper_detection.txt
#   - Handle automatic reconnects using callbacks
#
# NOTE:
#   main.py starts this file as a subprocess.
#   DO NOT RUN THIS FILE DIRECTLY unless debugging.
# ==============================================================

import os
import time
import ssl
import subprocess
import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import threading
import socket
from uart_monitor import monitor_uart_file

client = None  # Global MQTT client reference (shared across functions)
print("[MQTT] PID:", os.getpid())
GPIO.setwarnings(False)

# --------------------------------------------------------------
# GPIO Setup: Transmission LED pin
# --------------------------------------------------------------
TRANSMISION_LED_PIN = 21
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRANSMISION_LED_PIN, GPIO.OUT)
GPIO.output(TRANSMISION_LED_PIN, GPIO.HIGH)  # LED default OFF state


# --------------------------------------------------------------
# MQTT + TLS Configuration
# --------------------------------------------------------------
BROKER = "test.mosquitto.org"           # MQTT broker hostname
MQTT_PORT_PLAINTEXT = 1883              # Non-TLS port
MQTT_PORT_TLS = 8883                    # TLS port
#USE_TLS = True                          # Enable TLS mode
CA_CERT = "ca.pem"                      # Certificate authority file
USE_TLS = False

# Files monitored for publishing
file_path = "uart_data.txt"             # UART data source
tamper_file = "tamper_detection.txt"    # Tamper events written by main.py
last_tamper_state = ""                  # Avoid duplicate tamper publishes


# --------------------------------------------------------------
# FUNCTION: blink_led_once
# PURPOSE:
#   - Blink transmission LED to indicate publish success
# --------------------------------------------------------------
def blink_led_once():
    GPIO.output(TRANSMISION_LED_PIN, GPIO.LOW)
    time.sleep(0.15)
    GPIO.output(TRANSMISION_LED_PIN, GPIO.HIGH)


# --------------------------------------------------------------
# FUNCTION: load_wifi_credentials
# PURPOSE:
#   - Reads SSID and password from wifi_credentials.txt
#   - Used before Wi-Fi connection to ensure credentials exist
# --------------------------------------------------------------
def load_wifi_credentials():
    try:
        with open("wifi_credentials.txt", "r") as f:
            lines = f.read().splitlines()
            ssid = lines[0].strip() if len(lines) > 0 else ""
            password = lines[1].strip() if len(lines) > 1 else ""

            if ssid == "" or password == "":
                print("[MQTT] ERROR: wifi_credentials.txt missing SSID or Password.")
                return None, None

            print(f"[MQTT] Loaded SSID: {ssid}")
            return ssid, password

    except Exception as e:
        print(f"[MQTT] ERROR reading wifi_credentials.txt: {e}")
        return None, None



# --------------------------------------------------------------
# FUNCTION: connect_wifi
# PURPOSE:
#   - Uses nmcli to connect Raspberry Pi to a Wi-Fi network
#   - Verifies connection with multiple retries
#   - Disconnects from other networks if required
# --------------------------------------------------------------
def connect_wifi(ssid, password):
    print("[MQTT] Checking current Wi-Fi status...")
    
    
    if subprocess.getoutput("iwgetid -r").strip() == ssid:
        print(f"[MQTT] Already connected to {ssid}")
        return True

    # Check current Wi-Fi SSID
    try:
        current_ssid = subprocess.getoutput("iwgetid -r").strip()
    except Exception as e:
        print(f"[MQTT] iwgetid call failed: {e}")
        current_ssid = ""

    # Already connected to correct Wi-Fi
    if current_ssid == ssid:
        print(f"[MQTT] Already connected to {ssid}. Skipping Wi-Fi connect.")
        return True

    # Disconnect if connected to some other SSID
    if current_ssid != "":
        print(f"[MQTT] Connected to another network ({current_ssid}). Disconnecting...")
        subprocess.getoutput(f"nmcli con down id \"{current_ssid}\"")

    # Attempt new connection
    print(f"[MQTT] Connecting to {ssid}...")
    subprocess.getoutput("nmcli dev wifi rescan")
    time.sleep(2)
    result = subprocess.getoutput(f"nmcli dev wifi connect \"{ssid}\" password \"{password}\"")
    print("[MQTT] nmcli result:", result)

    # Verify with retries
    for _ in range(10):
        time.sleep(2)
        if subprocess.getoutput("iwgetid -r").strip() == ssid:
            print(f"[MQTT] Connected to {ssid}")
            return True

    print("[MQTT] Wi-Fi not connected.")
    return False



# --------------------------------------------------------------
# FUNCTION: read_all_sensor_lines
# PURPOSE:
#   - Reads the last 20 UART frames from uart_data.txt
#   - Validates frame structure (must start with |##| and end with |**|)
# --------------------------------------------------------------
def read_all_sensor_lines(file_path):
    """Load all 20 sensor lines from uart_data.txt"""
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Only valid formatted UART packets
    valid = [ln.strip() for ln in lines if ln.startswith("|##|") and ln.endswith("|**|")]
    return valid[-20:]   # Return last 20 entries



# --------------------------------------------------------------
# FUNCTION: create_mqtt_client
# PURPOSE:
#   - Create MQTT client object
#   - Configure TLS, callbacks, reconnect behavior
# --------------------------------------------------------------
def create_mqtt_client(client_id="rpi_client"):

    client = mqtt.Client(client_id=client_id)

    # ----------------- CALLBACKS -----------------

    # Triggered when connection to MQTT broker is established
    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] ✓ Connected to broker (rc={rc})")
        else:
            print(f"[MQTT] ✗ Connect returned result code: {rc}")

    # Triggered when MQTT client disconnects
    def on_disconnect(c, userdata, rc):
        print(
            f"[MQTT][{time.strftime('%H:%M:%S')}] "
            f"Disconnected rc={rc} PID={os.getpid()}"
        )
        if rc != 0:   # Unexpected disconnect
            print(f"[MQTT] Warning: Unexpected disconnect (rc={rc}). Will attempt reconnect.")
            '''
            try:
                c.reconnect()  # Auto-reconnect attempt
            except Exception as e:
                print(f"[MQTT] Reconnect attempt failed: {e}")
            '''
        else:
            print("[MQTT] Disconnected cleanly.")

    # Triggered after MQTT publish completes
    def on_publish(c, userdata, mid):
        pass
        #print(f"[MQTT] → Message published, mid={mid}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish

    # ----------------- TLS CONFIGURATION -----------------
    if USE_TLS:
        try:
            client.tls_set(
                ca_certs=CA_CERT,
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
                ciphers=None
            )
            client.tls_insecure_set(False)   # Enforce certificate verification
            print(f"[MQTT] TLS configured (CA={CA_CERT})")

        except Exception as e:
            print(f"[MQTT] ERROR setting TLS: {e}")
            raise

    return client
# --------------------------------------------------------------
# FUNCTION: main
# PURPOSE:
#   - Load Wi-Fi credentials
#   - Connect Raspberry Pi to Wi-Fi using nmcli
#   - Create MQTT client (TLS optional)
#   - Monitor:
#         1) uart_data.txt  → publish 20 sensor packets
#         2) tamper_detection.txt → publish tamper alerts
#   - Auto-publish when file content changes
# -------------------------------------------------------------

def mqtt_packet_handler(net_id, repeater_id, dev_id, t1, battery, rssi):
    """
    Safe UART → MQTT publish handler
    """

    # -------- Validate all required fields --------
    if not net_id or not repeater_id or not dev_id or dev_id == "000000":
        print("[MQTT] Invalid UART packet fields, skipping")
        return

    topic = f"NET_ID:{net_id}/{repeater_id}/{dev_id}"
    payload = f"Temperature:{t1},Battery:{battery},RSSI:{rssi}"

    try:
        info = client.publish(topic, payload, qos=1, retain=True)
        print(f"[MQTT] Published → {topic}:{payload} (mid={info.mid})")
        blink_led_once()
        time.sleep(0.05)
    except Exception as e:
        print("[MQTT] Publish exception:", e)

'''
def mqtt_packet_handler(net_id, repeater_id, dev_id, t1, battery, rssi):
    """
    Called once per valid UART packet
    """
    info = client.publish(topic, payload, qos=1, retain=True)
    print(f"[MQTT] publish rc={info.rc} mid={info.mid}")

    topic = f"NET_ID:{net_id}/{repeater_id}/{dev_id}"
    payload = f"Temperature:{t1},Battery:{battery},RSSI:{rssi}"

    try:
        client.publish(topic, payload, qos=1, retain=True)
        print(f"[MQTT] Published → {topic}: {payload}")
        blink_led_once()
    except Exception as e:
        print("[MQTT] Publish error:", e)
'''


def main():

    # -------- Load SSID + Password --------
    ssid, password = load_wifi_credentials()
    if not ssid or not password:
        print("[MQTT] Cannot start MQTT — Wi-Fi credentials missing!")
        return
    
    # -------- Ensure Wi-Fi is connected --------
    while not connect_wifi(ssid, password):
        print("[MQTT] Retrying Wi-Fi in 5 seconds...")
        time.sleep(5)
    
    global client

    # -------- Create MQTT client --------
    #client = create_mqtt_client(
     #   client_id="rpi_tls_client" if USE_TLS else "rpi_plain_client"
    #)
    

    client = create_mqtt_client(
        client_id=f"rpi_{socket.gethostname()}_{os.getpid()}"
    )


    port = MQTT_PORT_TLS if USE_TLS else MQTT_PORT_PLAINTEXT

    try:
        print(f"[MQTT] Connecting to broker {BROKER}:{port}")
        client.connect(BROKER, port, keepalive=300)
    except Exception as e:
        print(f"[MQTT] ERROR connecting to broker: {e}")

    client.loop_start()
    print("[MQTT] loop_start called, PID:", os.getpid())
    print("[MQTT] MQTT loop started")

    # =========================================================
    # START UART FILE MONITOR (COMMON MODULE)
    # =========================================================
    uart_thread = threading.Thread(
        target=monitor_uart_file,
        args=(file_path, mqtt_packet_handler),
        daemon=True
    )
    uart_thread.start()
    
    
    # =========================================================
    # TAMPER FILE MONITORING (MQTT-SPECIFIC)
    # =========================================================
    global last_tamper_state

    while True:
        try:
            if os.path.exists(tamper_file):
                with open(tamper_file, "r") as tf:
                    tamper_state = tf.read().strip()

                if tamper_state and tamper_state != last_tamper_state:
                    try:
                        client.publish(
                            "gateway/tamper",
                            tamper_state,
                            qos=1,
                            retain=True
                        )
                        print(f"[MQTT] Published Tamper → {tamper_state}")
                        last_tamper_state = tamper_state
                    except Exception as e:
                        print("[MQTT] Tamper publish error:", e)

            time.sleep(1)

        except KeyboardInterrupt:
            print("[MQTT] Exiting main loop")
            break
    

# --------------------------------------------------------------
# ENTRY POINT CHECK
# PURPOSE:
#   - Ensures main() runs only when mqtt.py is executed directly
# --------------------------------------------------------------
if __name__ == "__main__":
    main()
