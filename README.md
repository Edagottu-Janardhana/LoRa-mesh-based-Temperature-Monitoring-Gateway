# Raspberry Pi - Wireless Temperature Monitoring Gateway Documentation

## Overview

This project is a Raspberry Pi based IoT Gateway system designed to:

* Receive sensor/device data through UART
* Automatically switch between MQTT and BACnet communication
* Support Wi-Fi Access Point mode with captive portal
* Monitor tamper detection signals
* Manage network connectivity dynamically
* Provide LED indication for system status
* Handle clean process shutdown and restart

The Raspberry Pi acts as the central gateway between embedded devices and cloud/building automation systems.

---

# Main Features

## 1. UART Communication

The gateway launches:

* uart.py
* GET_IP.py

These scripts continuously communicate with external embedded devices such as:

* STM microcontrollers
* ESP32 devices
* LoRa nodes

UART data is processed and forwarded to cloud or industrial systems.

---

## 2. Automatic Protocol Switching

The gateway automatically selects communication mode depending on Ethernet availability.

### Logic

If Ethernet is connected:

```text
BACnet/IP Mode
```

If Ethernet is disconnected:

```text
MQTT Mode
```

The following scripts are dynamically launched:

* mqtt.py
* bacnet.py

Only one mode runs at a time.

---

# Network Mode Selection Flow

```text
             +----------------+
             | Ethernet Found |
             +----------------+
                      |
                    YES
                      |
                      v
               Start bacnet.py
                      |
                    NO
                      |
                      v
                Start mqtt.py
```

---

## 3. Wi-Fi AP Mode

The system supports Access Point mode for Wi-Fi configuration.

### Trigger

Press and hold the hardware button for 2 seconds.

### AP Mode Actions

* Stops running communication scripts
* Creates Wi-Fi hotspot
* Starts captive portal
* User enters Wi-Fi credentials
* Restarts back into STA mode automatically

### AP Configuration

```text
SSID     : Pi_Config_AP
Password : raspberry123
IP       : 192.168.4.1
```

---

# AP Mode Internal Components

## hostapd

Used for:

* Creating Wi-Fi hotspot
* WPA2 security

## dnsmasq

Used for:

* DHCP server
* IP allocation

## systemd-networkd

Used for:

* Static IP assignment

## NetworkManager

Used for:

* Wi-Fi management
* STA mode handling

---

## 4. Tamper Detection System

The project continuously monitors a tamper GPIO pin.

### GPIO Used

```text
ALERT_PIN = GPIO24
```

### Detection Types

| Pulse Width | Detection     |
| ----------- | ------------- |
| < 0.15 sec  | TOP_TAMPER    |
| < 0.30 sec  | BOTTOM_TAMPER |
| > 0.30 sec  | TAMPER_BOTH   |

Detected tamper events are stored in:

```text
tamper_detection.txt
```

---

## 5. LED Status Indicators

### Power LED

```text
GPIO16
```

Indicates system power status.

---

### Connection LED

```text
GPIO20
```

Indicates:

* Wi-Fi connected status
* AP mode blinking indication

### LED Behavior

| State    | Meaning             |
| -------- | ------------------- |
| ON       | No Wi-Fi connection |
| OFF      | Wi-Fi connected     |
| BLINKING | AP Mode active      |

---

# GPIO Pin Configuration

| GPIO Pin | Purpose        |
| -------- | -------------- |
| GPIO16   | Power LED      |
| GPIO20   | Connection LED |
| GPIO24   | Tamper Input   |
| GPIO27   | AP Mode Button |

---

# Main Functional Blocks

## handle_exit()

Purpose:

* Handles CTRL+C
* Stops all child processes
* Cleans GPIO safely
* Prevents zombie processes

Processes terminated:

* uart.py
* GET_IP.py
* mqtt.py
* bacnet.py

---

## tamper_thread()

Purpose:

* Monitors tamper GPIO continuously
* Measures pulse width
* Detects tamper type
* Stores tamper events

Runs as background thread.

---

## force_sta_mode_on_boot()

Purpose:

* Removes AP mode configuration
* Forces Wi-Fi station mode during boot
* Restarts networking services

---

## led_blink()

Purpose:

* Blinks connection LED during AP mode

---

## setup_hostapd()

Purpose:

* Configures Wi-Fi hotspot
* Enables WPA2 security
* Sets AP SSID and password

---

## setup_dnsmasq()

Purpose:

* Configures DHCP server
* Assigns IP addresses to connected devices

---

## start_ap_mode()

Purpose:

* Starts AP mode services
* Launches captive portal
* Restarts gateway after configuration

---

## button_loop()

Purpose:

* Detects long button press
* Enters AP mode
* Stops running services before switching

---

## is_eth()

Purpose:

* Detects Ethernet connectivity
* Determines BACnet mode activation

---

## is_wifi_connected()

Purpose:

* Checks Wi-Fi connection status

---

## update_wifi_led()

Purpose:

* Updates LED based on Wi-Fi state

---

## main()

Main control loop of the gateway.

Responsibilities:

* Initialize STA mode
* Start tamper monitoring
* Monitor Ethernet state
* Switch between MQTT and BACnet modes
* Update LED indicators
* Manage child processes dynamically

---

# Process Architecture

```text
                   +----------------+
                   |    main.py     |
                   +----------------+
                     |     |      |
                     |     |      |
                     |     |      +----------------+
                     |     |                       |
                     |     v                       v
                     |  mqtt.py               bacnet.py
                     |
                     +----------------+
                     |                |
                     v                v
                 uart.py         GET_IP.py
```

---

# Thread Architecture

```text
main thread
   |
   +-- button_loop thread
   |
   +-- tamper_thread
   |
   +-- stream_output threads
```

---

# Technologies Used

## Hardware

* Raspberry Pi 4 / CM4
* STM Microcontroller
* ESP32
* LoRa Modules
* LEDs
* Push Button

---

## Software

* Python
* RPi.GPIO
* gpiozero
* MQTT
* BACnet/IP
* Linux Networking
* hostapd
* dnsmasq
* systemd-networkd
* NetworkManager

---

# Advantages of This Architecture

* Automatic network management
* Dynamic protocol switching
* Easy Wi-Fi configuration
* Industrial IoT ready
* Supports remote deployment
* Reliable process handling
* Clean service restart
* Thread-based monitoring
* Scalable gateway design

---

# Typical Use Cases

* Industrial IoT Gateway
* Smart Meter Gateway
* Remote Monitoring System
* LoRa Mesh Gateway
* Building Automation
* Environmental Monitoring
* Smart Energy Systems

---

# Example Working Flow

```text
Sensor Device
      |
      v
     UART 
      |
      v
Raspberry Pi Gateway
      |
      +-------------------+
      |                   |
      v                   v
 MQTT over Wi-Fi     BACnet/IP Ethernet
      |                   |
      v                   v
 Cloud Dashboard    Building System
```

---

# Author

Edagottu Janardhana
Firmware Developer


