from lib.umqtt import MQTTClient
from lib.acs712 import ACS712
from utils.utils import connect_to_wifi, is_wifi_connected
from machine import Pin
import time
import json
from secrets import SERVER, USER, PASSWORD, CLIENT_ID


SLEEP_INTERVAL = 0.2
MQTT_RETRY_INTERVAL = 1
DEBOUNCE_TIME = 0.5
NOTIFICATION_TIMEOUT = 60

TOPICS = {
    "SIREN": b"api/water_tank/siren",
    "PUMP": b"api/water_tank/pump",
    "GET_WATER_TANK_STATUS" : b"api/water_tank/status"
}

ac_current_sernsor = Pin(4, Pin.IN)

pump_status = Pin(16, Pin.IN)
alarm_status = Pin(17, Pin.IN)

pump_aux_relay = Pin(18, Pin.OUT)
siren_aux_relay = Pin(19, Pin.OUT)

mqtt_client = None
current_message = None
status_requested = False
status_end_time = 0
last_execution_time = {}

acs = ACS712()
acs.calibrate()


def send_notification(topic, message):
    try:
        mqtt_client.publish(topic, message)
    except Exception as e:
        print(f"Error sending notification: {topic}")

def can_execute(command):
    current_time = time.time()
    if command not in last_execution_time or current_time - last_execution_time[command] >= DEBOUNCE_TIME:
        last_execution_time[command] = current_time
        return True
    return False

def handle_message(topic, msg):
    global current_message, status_end_time, status_requested
    print(topic, msg)

    if topic == TOPICS["SIREN"] and can_execute("small_gate"):
        if siren_aux_relay.value():
            siren_aux_relay.off()
            response = {"data": "Sirena disabilitata: Eseguito con successo"}
        else:
            siren_aux_relay.on()
            response = {"data": "Sirena abilitata: Eseguito con successo"}

        send_notification(b"api/notification/siren", json.dumps(response))

    elif topic == TOPICS["PUMP"] and can_execute("garage_light"):
        if pump_aux_relay.value():
            pump_aux_relay.off()
            response = {"data": "Pompa disattivata: Eseguito con successo"}
        else:
            pump_aux_relay.on()
            response = {"data": "Pompa attivata: Eseguito con successo"}

        send_notification(b"api/notification/pump", json.dumps(response))

    elif topic == TOPICS["GET_WATER_TANK_STATUS"]:
        status_requested = True
        status_end_time = time.time() + 60

def send_water_tank_status():
    status_variant = {"0":"disattivo", "1":"attivo"}
    water_tank_status = {
        "alarmStatus": status_variant.get(str(alarm_status.value()), "sconosciuto"),
        "pumpStatus": status_variant.get(str(pump_status.value()), "sconosciuto"),
        "pumpRelay": status_variant.get(str(pump_aux_relay.value()), "sconosciuto"),
        "sirenRelay": status_variant.get(str(siren_aux_relay.value()), "sconosciuto"),
        "current": str(acs.getCurrentAC())
    }
    response = json.dumps(water_tank_status)
    send_notification(b"api/notification/water_tank/status", response)

def connect_to_mqtt():
    global mqtt_client

    while not is_wifi_connected():
        connect_to_wifi()

    client = MQTTClient(client_id=CLIENT_ID, user=USER, password=PASSWORD, server=SERVER)
    client.set_callback(handle_message)
    client.connect()
    for topic in TOPICS.values():
        client.subscribe(topic)
    print(f"Connected to {SERVER}")
    mqtt_client = client

def keep_connection_active():
    try:
        mqtt_client.publish("api/ping", "ping")
    except Exception as e:
        print(f"Error sending ping to broker: {e}")

def main():
    global status_requested
    last_send_status = time.time()
    last_keep_alive = time.time()

    while True:
        try:
            connect_to_mqtt()
            while True:
                current_time = time.time()

                mqtt_client.check_msg()

                if status_requested:
                    if current_time - last_send_status >= 1:
                        send_water_tank_status()
                        last_send_status = current_time

                    if current_time >= status_end_time:
                        status_requested = False

                if current_time - last_keep_alive >= 10:
                    keep_connection_active()
                    last_keep_alive = current_time
                time.sleep(SLEEP_INTERVAL)

        except Exception as e:
            print(f"MQTT communication error: {e}")

        finally:
            try:
                mqtt_client.disconnect()
            except Exception as e:
                print(f"Error disconnecting client: {e}")

            time.sleep(MQTT_RETRY_INTERVAL)

if __name__ == '__main__':
    main()
