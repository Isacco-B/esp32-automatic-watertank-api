from utils.utils import connect_to_wifi
from machine import Pin

aux_power = Pin(33, Pin.OUT)

aux_power.on()
connect_to_wifi()
