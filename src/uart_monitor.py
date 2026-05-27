# =========================================================
# uart_monitor.py
# PURPOSE:
#   - Monitor UART data file
#   - Detect file modification
#   - Parse valid UART packets
#   - Call a user-provided callback for each packet
# =========================================================

import os
import time

def monitor_uart_file(file_path, packet_handler, poll_interval=1):
    """
    Common UART file monitoring function (reusable)
    
    Args:
        file_path      : UART data file path
        packet_handler : Callback function(net_id, dev_id, t1, batt, rssi)
        poll_interval  : File polling interval (seconds)
    """

    last_mtime = 0

    while True:
        try:
            if os.path.exists(file_path):
                current_mtime = os.path.getmtime(file_path)

                # File updated
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    print("[UART] New data detected")

                    with open(file_path, "r") as f:
                        for ln in f.readlines():
                            line = ln.strip()

                            # Validate frame
                            if not (line.startswith("|##|") and line.endswith("|**|")):
                                continue

                            parts = line.strip("|").split("|")

                            # Expected: |##|net_id|repeater_id|dev|temp|batt|rssi|**|
                            if len(parts) != 8:
                                print("[UART] Invalid packet:", parts)
                                continue

                            _, net_id,  repeater_id,  dev_id, t1, batt, rssi, _ = parts

                            try:
                                packet_handler(
                                    net_id,
                                    repeater_id,
                                    dev_id,
                                    float(t1),
                                    float(batt),
                                    float(rssi)
                                )
                            #except ValueError:
                                #print("[UART] Data conversion error:", line)
                            except Exception as e:
                                print("[UART] Packet handler error:", e)

            time.sleep(poll_interval)

        except KeyboardInterrupt:
            print("[UART] Monitor stopped")
            break
