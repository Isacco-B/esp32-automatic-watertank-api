import gc
import time

import machine
from machine import Pin

from utils.utils import connect_to_wifi

BOOT_DELAY = 2
WIFI_TIMEOUT = 120
ENABLE_WEBREPL = False

aux_power = Pin(33, Pin.OUT)
aux_power.on()


def show_boot_info():
    """Display boot information."""
    print("\n" + "=" * 50)
    print("ESP32 Water Tank Controller - Booting...")
    print("=" * 50)

    gc.collect()
    print(f"Free memory: {gc.mem_free()} bytes")
    print(f"Used memory: {gc.mem_alloc()} bytes")
    print(f"CPU Frequency: {machine.freq()/1000000:.0f} MHz")
    print("=" * 50 + "\n")


def boot_sequence():
    """Main boot sequence with error handling."""
    print(f"Waiting {BOOT_DELAY} seconds for system stability...")
    time.sleep(BOOT_DELAY)

    print("\n[1/1] Connecting to WiFi...")
    wifi_connected = connect_to_wifi(timeout=WIFI_TIMEOUT)
    if wifi_connected:
        print("WiFi connected successfully")
    else:
        print("WiFi connection failed")
        print("Main program will retry WiFi connection")

    gc.collect()
    print(f"\nFree memory after boot: {gc.mem_free()} bytes")
    print("\nBoot sequence completed. Starting main program...\n")
    print("=" * 50 + "\n")


def setup_webrepl():
    """Setup WebREPL for remote access (optional)."""
    try:
        import webrepl

        webrepl.start()
        print("WebREPL started")
    except ImportError:
        print("WebREPL not available")
    except Exception as e:
        print(f"WebREPL error: {e}")


try:
    show_boot_info()

    if ENABLE_WEBREPL:
        setup_webrepl()

    boot_sequence()

except Exception as e:
    print(f"\nBoot error: {e}")
    print("Continuing to main program anyway...")
    time.sleep(2)
