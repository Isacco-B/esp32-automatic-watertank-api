from machine import Pin
import network
import time
from secrets import WLAN_SSID, WLAN_PASSWORD


WIFI_RETRY_INTERVAL = 1

led_wifi = Pin(32, Pin.OUT)


def connect_to_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        led_wifi.on()
        print('wifi connection...')
        wlan.connect(WLAN_SSID, WLAN_PASSWORD)
        while not wlan.isconnected():
            led_wifi.on()
            time.sleep(WIFI_RETRY_INTERVAL)
            print('Retrying WiFi connection...')
    led_wifi.off()
    print('Connected to:', WLAN_SSID)
    print('Connection details:', wlan.ifconfig())

def is_wifi_connected():
    wlan = network.WLAN(network.STA_IF)
    return wlan.isconnected()
