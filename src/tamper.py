# ------------------------------------------------------------
# tamper_test.py
#
# Purpose:
# - Test tamper detection on GPIO12 (connected to STM32 output)
# - Use polling (safe for PWM pins, avoids interrupt issues)
# - Publish tamper alert to MQTT broker
# - Easy to integrate later into main.py and mqtt.py
# ------------------------------------------------------------
'''
import RPi.GPIO as GPIO
import time
import threading
import paho.mqtt.client as mqtt

# ---------------- GPIO Setup ----------------
TAMPER_PIN = 27 #12  # Using GPIO12 (BCM)
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(TAMPER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
#GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
# ---------------- MQTT Setup ----------------
BROKER = "broker.hivemq.com"
TOPIC = "rpi/tamper"

client = mqtt.Client()
client.connect(BROKER, 1883, 60)
client.loop_start()

# ---------------- Tamper Monitor Thread ----------------
def tamper_monitor():
    print("Tamper monitor thread started...")
    last_state = 1  # previous pin state

    while True:
        state = GPIO.input(TAMPER_PIN)

        # Detect rising edge: LOW -> HIGH
        if state == 0 and last_state == 1:
            print("⚠️ TAMPER DETECTED!")
            client.publish(TOPIC, "Tamper Detected!")

        last_state = state
        time.sleep(0.01)  # 10 ms polling

# ---------------- Start Thread ----------------
thread = threading.Thread(target=tamper_monitor, daemon=True)
thread.start()

print("Tamper test running... Press CTRL+C to exit.")

# ---------------- Keep Program Running ----------------
try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nExiting...")
    GPIO.cleanup()
    client.loop_stop()

'''
'''
import RPi.GPIO as GPIO
import time

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

PIN = 24  # GPIO12

#GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
print("Reading GPIO12... Press CTRL+C to stop.\n")

try:
    while True:
        value = GPIO.input(PIN)
        print("GPIO12 =", value)   # 0 = LOW, 1 = HIGH
        time.sleep(0.5)            # read every 500 ms

except KeyboardInterrupt:
    print("\nExiting...")
    GPIO.cleanup()



'''
import time
import RPi.GPIO as GPIO

PIN = 24

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Waiting for tamper pulse...")

while True:
    # Wait for LOW
    if GPIO.input(PIN) == 0:
        start = time.time()

        # Wait until it goes LOW again
        while GPIO.input(PIN) == 0:
            time.sleep(0.001)  # reduce CPU load

        pulse_width = time.time() - start

        # Classify pulse width
        if pulse_width < 0.5:
            print("Tamper 1")
        elif pulse_width < 0.9:
            print("Tamper 2")
        else:
            print("Both tamper")

    time.sleep(0.005)  # small polling delay