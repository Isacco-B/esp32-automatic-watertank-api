import time
from secrets import WLAN_PASSWORD, WLAN_SSID

import network
from machine import Pin

from utils.timezone import sync_ntp

WIFI_RETRY_INTERVAL = 1
led_wifi = Pin(32, Pin.OUT)

led_wifi.off()


def connect_to_wifi(timeout: int = 30) -> bool:
    """Connect to WiFi and synchronize time."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        led_wifi.off()
        print(f"Already connected to: {WLAN_SSID}")
        print(f"Connection details: {wlan.ifconfig()}")
        return True

    led_wifi.on()
    print(f"Connecting to WiFi: {WLAN_SSID}")
    wlan.connect(WLAN_SSID, WLAN_PASSWORD)

    start_time = time.time()
    while not wlan.isconnected():
        if time.time() - start_time > timeout:
            led_wifi.on()
            print(f"WiFi connection timeout after {timeout} seconds")
            return False

        led_wifi.value(not led_wifi.value())
        time.sleep(WIFI_RETRY_INTERVAL)
        print(f"Connecting... ({int(time.time() - start_time)}s)")

    led_wifi.off()
    print(f"Connected to: {WLAN_SSID}")
    print(f"Connection details: {wlan.ifconfig()}")

    ntp_ok = sync_ntp()
    if ntp_ok:
        print("Time synchronized successfully")
    else:
        print("Time synchronization failed")

    return True


def is_wifi_connected() -> bool:
    """Check if WiFi is connected."""
    wlan = network.WLAN(network.STA_IF)
    connected = wlan.isconnected()

    if connected:
        led_wifi.off()
    else:
        led_wifi.on()

    return connected
