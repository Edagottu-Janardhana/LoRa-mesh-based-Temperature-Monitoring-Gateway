from bacpypes.app import BIPSimpleApplication
from bacpypes.local.device import LocalDeviceObject
from bacpypes.object import AnalogValueObject
from bacpypes.service.device import WhoIsIAmServices
from bacpypes.core import run, enable_sleeping, deferred
from bacpypes.primitivedata import Real

import threading
import subprocess
from uart_monitor import monitor_uart_file

UART_FILE = "uart_data.txt"

# -------------------- Custom Analog Object --------------------
class WritableAnalogValue(AnalogValueObject):
    def __init__(self, initial_value=0.0, **kwargs):
        super().__init__(**kwargs)
        self._values['presentValue'] = Real(initial_value)
        self._properties['presentValue'].writable = True

# -------------------- Dynamic IP Detection --------------------
def get_eth_ip():
    result = subprocess.getoutput("ip -4 addr show eth0 | grep inet")
    if "inet" in result:
        return result.strip().split()[1].split("/")[0]
    else:
        print("Ethernet IP not found. Using 0.0.0.0")
        return "0.0.0.0"

eth_ip = get_eth_ip()

# -------------------- BACnet Device Init --------------------
device_info = LocalDeviceObject(
    objectName="RaspberryPi BACnet Device",
    objectIdentifier=599,
    maxApduLengthAccepted=1024,
    segmentationSupported='segmentedBoth',
    vendorIdentifier=15,
)

application = BIPSimpleApplication(device_info, eth_ip)
application.add_capability(WhoIsIAmServices)
print(f"BACnet server running at {eth_ip}")

object_dict = {}
object_instance_counter = [1]
enable_sleeping()

# -------------------- Create or Update BACnet Object --------------------
def update_or_create_object(name, value):
    if name in object_dict:
        obj = object_dict[name]
        obj.presentValue = Real(value)
        print(f"Updated: {name} → {value}")
    else:
        instance = object_instance_counter[0]
        object_instance_counter[0] += 1

        new_obj = WritableAnalogValue(
            objectIdentifier=('analogValue', instance),
            objectName=name,
            units=62,
            initial_value=value
        )
        application.add_object(new_obj)
        object_dict[name] = new_obj
        print(f"Created: {name} → {value}")

# -------------------- BACnet Packet Handler --------------------
def bacnet_packet_handler(net_id, repeater_id, dev_id, t1, batt, rssi):
    base = f"{net_id}_{repeater_id}/{dev_id}"

    deferred(update_or_create_object, f"{base}_T1", t1)
    deferred(update_or_create_object, f"{base}_BATTERY", batt)
    deferred(update_or_create_object, f"{base}_RSSI", rssi)

    print(f"[BACnet] Updated objects for {base}")

# -------------------- Start UART Monitor Thread --------------------
uart_thread = threading.Thread(
    target=monitor_uart_file,
    args=(UART_FILE, bacnet_packet_handler),
    daemon=True,
    name="UART-Monitor-Thread"
)
uart_thread.start()

print("[BACnet] UART monitor thread started")

# -------------------- Start BACnet Core Loop --------------------
run()
