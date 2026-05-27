#!/usr/bin/python3
"""
File: led_blink.py
Purpose: Blink LEDs connected to GPIO 16, 20, and 21 on Raspberry Pi 4.

Description:
    This script toggles three GPIO pins (16, 20, 21) alternately to blink LEDs.
    It uses the RPi.GPIO library for GPIO control.
"""

import RPi.GPIO as GPIO
import time

# Use BCM pin numbering
GPIO.setmode(GPIO.BCM)

# Define LED pins
led_pins = [16, 20, 21]

# Set pins as output
GPIO.setup(led_pins, GPIO.OUT)

print("Blinking LEDs on GPIO 16, 20, 21. Press Ctrl+C to stop.")

try:
    while True:
        # Turn all LEDs ON
        for pin in led_pins:
            GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.5)

        # Turn all LEDs OFF
        for pin in led_pins:
            GPIO.output(pin, GPIO.LOW)
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nProgram stopped by user")

finally:
    GPIO.cleanup()
    print("GPIO cleaned up successfully.")

