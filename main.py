import json
import random
import time
from secrets import PASSWORD, SERVER, USER

import machine

from lib.umqtt import MQTTClient
from lib.acs712 import ACS712
from utils.counter import counter
from utils.email_manager import email_manager
from utils.messages import ALARM_MESSAGES, DEFAULT_USER, MESSAGES, STATUS_DESCRIPTIONS
from utils.timezone import now_unix_ms
from utils.utils import connect_to_wifi, is_wifi_connected

WIFI_TIMEOUT = 120
SLEEP_INTERVAL = 0.1
MQTT_RETRY_INTERVAL = 1
DEBOUNCE_TIME = 1000
NOTIFICATION_TIMEOUT = 60

STATUS_SEND_INTERVAL = 1000
KEEP_ALIVE_INTERVAL = 10
ALARM_CHECK_INTERVAL = 500
ALARM_EMAIL_INTERVAL = 300

VALID_COMMANDS = {"siren", "pump"}

PUMP_DRY_RUN_CURRENT = 2.8
PUMP_STARTUP_DELAY = 3
PUMP_DRY_RUN_CHECK_INTERVAL = 1000

TOPICS = {
    "SIREN": b"api/water_tank/siren",
    "PUMP": b"api/water_tank/pump",
    "GET_STATUS": b"api/water_tank/status",
    "GET_STATISTICS": b"api/water_tank/statistics",
    "RESET_STATISTICS": b"api/water_tank/statistics/reset",
    "EMAIL_ADD": b"api/water_tank/email/add",
    "EMAIL_REMOVE": b"api/water_tank/email/remove",
    "EMAIL_LIST": b"api/water_tank/email/list",
    "EMAIL_TEST": b"api/water_tank/email/test",
}

NOTIFY = {
    "SIREN": b"api/notification/water_tank/siren",
    "PUMP": b"api/notification/water_tank/pump",
    "ALARM": b"api/notification/water_tank/alarm",
    "STATUS": b"api/notification/water_tank/status",
    "EMAIL": b"api/notification/water_tank/email",
    "EMAIL_LIST": b"api/notification/water_tank/email/list",
    "EMAIL_TEST": b"api/notification/water_tank/email/test",
    "STATISTICS": b"api/notification/water_tank/statistics",
    "STATISTICS_RESET": b"api/notification/water_tank/statistics/reset",
}

pump_status = machine.Pin(16, machine.Pin.IN)
alarm_status = machine.Pin(17, machine.Pin.IN)

pump_aux_relay = machine.Pin(18, machine.Pin.OUT)
siren_aux_relay = machine.Pin(19, machine.Pin.OUT)

acs = ACS712()
acs.calibrate()

mqtt_client = None
status_requested = False
status_end_time = 0
last_execution_time = {}
last_alarm_state = alarm_status.value()
last_alarm_email_time = 0
last_pump_state = pump_status.value()
pump_dry_run_check = False
pump_start_time = 0


def cleanup_pins() -> None:
    try:
        pump_aux_relay.off()
        siren_aux_relay.off()
    except Exception as e:
        print(f"Error cleaning up pins: {e}")


def parse_message_payload(msg: bytes) -> tuple:
    """
    Parse MQTT message payload to extract command and username.
    """
    try:
        msg_str = msg.decode("utf-8")

        if msg_str.startswith("{"):
            try:
                data = json.loads(msg_str)
                command = data.get("cmd", "on")
                username = data.get("user", DEFAULT_USER)
                return command, username
            except json.JSONDecodeError:
                pass

        if ":" in msg_str:
            parts = msg_str.split(":", 1)
            command = parts[0]
            username = parts[1] if len(parts) > 1 and parts[1] else DEFAULT_USER
            return command, username

        return msg_str, DEFAULT_USER

    except Exception as e:
        print(f"Error parsing message: {e}")
        return "on", DEFAULT_USER


def send_notification(topic, message: str, success: bool = True) -> None:
    """
    Send MQTT notification with status and timestamp.
    """
    try:
        if isinstance(topic, str):
            topic = topic.encode()

        payload = {
            "data": message,
            "status": "success" if success else "error",
            "timestamp": now_unix_ms(),
        }

        mqtt_client.publish(topic, json.dumps(payload))
    except Exception as e:
        print(f"Error sending notification: {topic}, error: {e}")


def can_execute(command: str) -> bool:
    """
    Check if a command can be executed using debouncing.
    Prevents command flooding by enforcing minimum time between executions.
    """
    if command not in VALID_COMMANDS:
        return False

    ms_current_time = time.ticks_ms()

    if command not in last_execution_time:
        last_execution_time[command] = ms_current_time
        return True

    if time.ticks_diff(ms_current_time, last_execution_time[command]) >= DEBOUNCE_TIME:
        last_execution_time[command] = ms_current_time
        return True

    return False


def handle_message(topic: bytes, msg: bytes) -> None:
    """
    Handle incoming MQTT messages and trigger appropriate actions.
    """
    print(f"Received - Topic: {topic}, Message: {msg}")
    global status_requested, status_end_time

    if topic == TOPICS["GET_STATISTICS"]:
        send_statistics()
        return

    if topic == TOPICS["RESET_STATISTICS"]:
        handle_reset_statistics(msg)
        return

    if topic == TOPICS["EMAIL_ADD"]:
        handle_email_add(msg)
        return

    if topic == TOPICS["EMAIL_REMOVE"]:
        handle_email_remove(msg)
        return

    if topic == TOPICS["EMAIL_LIST"]:
        handle_email_list()
        return

    if topic == TOPICS["EMAIL_TEST"]:
        handle_email_test(msg)
        return

    _, username = parse_message_payload(msg)

    if topic == TOPICS["SIREN"] and can_execute("siren"):
        is_on = siren_aux_relay.value()
        if is_on:
            siren_aux_relay.off()
            message = MESSAGES["siren"]["off"].format(user=username)
        else:
            siren_aux_relay.on()
            message = MESSAGES["siren"]["on"].format(user=username)
        send_notification(NOTIFY["SIREN"], message)
        counter.increment("siren")

    elif topic == TOPICS["PUMP"] and can_execute("pump"):
        global pump_dry_run_check, pump_start_time
        is_on = pump_aux_relay.value()
        if is_on:
            pump_aux_relay.off()
            pump_dry_run_check = False
            message = MESSAGES["pump"]["off"].format(user=username)
        else:
            pump_aux_relay.on()
            if alarm_status.value() == 0:
                pump_dry_run_check = True
                pump_start_time = time.time()
            message = MESSAGES["pump"]["on"].format(user=username)
        send_notification(NOTIFY["PUMP"], message)

    elif topic == TOPICS["GET_STATUS"]:
        status_requested = True
        status_end_time = time.time() + NOTIFICATION_TIMEOUT


def handle_email_add(msg: bytes) -> None:
    """Add an email recipient from MQTT payload {"email": "..."}."""
    try:
        data = json.loads(msg.decode("utf-8"))
        email = data.get("email", "")

        if not email or "@" not in email:
            send_notification(
                NOTIFY["EMAIL"],
                "Indirizzo email non valido",
                False,
            )
            return

        added = email_manager.add_recipient(email)
        if added:
            message = f"Indirizzo {email} aggiunto ai destinatari"
        else:
            message = f"Indirizzo {email} già presente nella lista"
        send_notification(NOTIFY["EMAIL"], message, added)

    except Exception as e:
        print(f"Error adding email: {e}")
        send_notification(
            NOTIFY["EMAIL"],
            "Errore nell'aggiunta dell'indirizzo email",
            False,
        )


def handle_email_remove(msg: bytes) -> None:
    """Remove an email recipient from MQTT payload {"email": "..."}."""
    try:
        data = json.loads(msg.decode("utf-8"))
        email = data.get("email", "")

        removed = email_manager.remove_recipient(email)
        if removed:
            message = f"Indirizzo {email} rimosso dai destinatari"
        else:
            message = f"Indirizzo {email} non trovato nella lista"
        send_notification(NOTIFY["EMAIL"], message, removed)

    except Exception as e:
        print(f"Error removing email: {e}")
        send_notification(
            NOTIFY["EMAIL"],
            "Errore nella rimozione dell'indirizzo email",
            False,
        )


def handle_email_list() -> None:
    """Publish the current list of email recipients."""
    try:
        recipients = email_manager.get_recipients()
        payload = {
            "destinatari": recipients,
            "totale": len(recipients),
            "timestamp": now_unix_ms(),
        }
        mqtt_client.publish(NOTIFY["EMAIL_LIST"], json.dumps(payload))
    except Exception as e:
        print(f"Error listing email recipients: {e}")


def handle_email_test(msg: bytes) -> None:
    """Send a test email to the address in payload {"email": "..."}."""
    try:
        data = json.loads(msg.decode("utf-8"))
        email = data.get("email", "")

        if not email or "@" not in email:
            send_notification(
                NOTIFY["EMAIL_TEST"],
                MESSAGES["email_test"]["invalid"].format(email=email),
                False,
            )
            return

        ok = email_manager.send_alarm_email(
            "Test notifica cisterna",
            f"Questa è un'email di test inviata dal sistema di controllo cisterna all'indirizzo {email}.",
            recipients=[email],
        )
        if ok:
            message = MESSAGES["email_test"]["success"].format(email=email)
        else:
            message = MESSAGES["email_test"]["error"].format(email=email)
        send_notification(NOTIFY["EMAIL_TEST"], message, ok)

    except Exception as e:
        print(f"Error sending test email: {e}")
        send_notification(
            NOTIFY["EMAIL_TEST"],
            MESSAGES["email_test"]["error"].format(email="?"),
            False,
        )


def send_statistics() -> None:
    """Send command and alarm statistics via MQTT."""
    try:
        stats = counter.get_statistics()
        message = {
            "ultime_24_ore": stats["last_24_hours"],
            "totale_storico": stats["totale"],
            "timestamp": now_unix_ms(),
        }
        mqtt_client.publish(NOTIFY["STATISTICS"], json.dumps(message))
        print("Statistics sent successfully")
    except Exception as e:
        print(f"Error sending statistics: {e}")


def handle_reset_statistics(msg: bytes) -> None:
    """Handle statistics reset request. Payload: {"cmd": "24h"|"total"|"all", "user": "..."}"""
    try:
        reset_type, username = parse_message_payload(msg)

        if reset_type not in ["24h", "total", "all"]:
            print(f"Invalid reset type: {reset_type}")
            return

        counter.reset_counters(reset_type)

        message = MESSAGES["reset_statistics"]["success"].format(user=username)
        send_notification(NOTIFY["STATISTICS_RESET"], message)
        print(f"Statistics reset: {reset_type}")

    except Exception as e:
        print(f"Error resetting statistics: {e}")


def send_water_tank_status() -> None:
    """Read all sensors and publish current water tank status."""
    try:
        status = {
            "alarmStatus": STATUS_DESCRIPTIONS.get(
                str(alarm_status.value()), STATUS_DESCRIPTIONS["unknown"]
            ),
            "pumpStatus": STATUS_DESCRIPTIONS.get(
                str(pump_status.value()), STATUS_DESCRIPTIONS["unknown"]
            ),
            "pumpRelay": STATUS_DESCRIPTIONS.get(
                str(pump_aux_relay.value()), STATUS_DESCRIPTIONS["unknown"]
            ),
            "sirenRelay": STATUS_DESCRIPTIONS.get(
                str(siren_aux_relay.value()), STATUS_DESCRIPTIONS["unknown"]
            ),
            "current": str(acs.getCurrentAC()),
            "timestamp": now_unix_ms(),
        }
        mqtt_client.publish(NOTIFY["STATUS"], json.dumps(status))
    except Exception as e:
        print(f"Error sending water tank status: {e}")


def check_alarm() -> None:
    """
    Poll alarm pin and detect state transitions.
    On 0→1: send MQTT notification + email to all recipients.
    While active: resend email every ALARM_EMAIL_INTERVAL seconds.
    On 1→0: send MQTT notification (alarm cleared).
    """
    global last_alarm_state, last_alarm_email_time
    try:
        current_alarm = alarm_status.value()
        current_time = time.time()

        if current_alarm == 1 and last_alarm_state == 0:
            print("ALARM TRIGGERED — water level too high!")
            counter.increment("alarm")
            send_notification(
                NOTIFY["ALARM"],
                ALARM_MESSAGES["triggered"],
                False,
            )
            email_manager.send_alarm_email(
                "ALLARME CISTERNA",
                ALARM_MESSAGES["triggered"],
            )
            last_alarm_email_time = current_time

        elif current_alarm == 1 and last_alarm_state == 1:
            if current_time - last_alarm_email_time >= ALARM_EMAIL_INTERVAL:
                print("Alarm still active — resending email notification")
                email_manager.send_alarm_email(
                    "ALLARME CISTERNA",
                    ALARM_MESSAGES["triggered"],
                )
                last_alarm_email_time = current_time

        elif current_alarm == 0 and last_alarm_state == 1:
            print("Alarm cleared.")
            send_notification(
                NOTIFY["ALARM"],
                ALARM_MESSAGES["cleared"],
            )
            last_alarm_email_time = 0

        last_alarm_state = current_alarm

    except Exception as e:
        print(f"Error checking alarm: {e}")


def check_pump_state() -> None:
    """Detect pump rising edge on physical pin and increment counter."""
    global last_pump_state
    try:
        current_pump = pump_status.value()
        if current_pump == 1 and last_pump_state == 0:
            counter.increment("pump")
            print("Pump activated — counter incremented")
        last_pump_state = current_pump
    except Exception as e:
        print(f"Error checking pump state: {e}")


def check_pump_dry_run() -> None:
    """Force-stop the pump if current drops below threshold (dry run protection)."""
    global pump_dry_run_check
    if not pump_dry_run_check:
        return
    if pump_aux_relay.value() == 0:
        pump_dry_run_check = False
        return
    if alarm_status.value() == 1:
        pump_dry_run_check = False
        return
    if time.time() - pump_start_time < PUMP_STARTUP_DELAY:
        return

    current = acs.getCurrentAC()
    if current < PUMP_DRY_RUN_CURRENT:
        pump_aux_relay.off()
        pump_dry_run_check = False
        message = MESSAGES["pump"]["dry_run"]
        print(f"Pump stopped: dry run detected (current={current:.2f}A)")
        send_notification(NOTIFY["PUMP"], message, False)


def connect_to_mqtt() -> bool:
    """
    Connect to MQTT broker.
    Handles WiFi check and previous session cleanup.
    """
    global mqtt_client

    if mqtt_client:
        try:
            mqtt_client.disconnect()
        except:
            pass
        mqtt_client = None

    while not is_wifi_connected():
        print("WiFi not connected, attempting connection...")
        connect_to_wifi(timeout=WIFI_TIMEOUT)
        time.sleep(1)

    try:
        client = MQTTClient(
            client_id=str(random.randint(100000, 999999)),
            user=USER,
            password=PASSWORD,
            server=SERVER,
        )
        client.set_callback(handle_message)
        client.connect()
        time.sleep_ms(200)

        for topic_name, topic in TOPICS.items():
            client.subscribe(topic)
            print(f"Subscribed to {topic_name}")

        print(f"Connected to MQTT broker at {SERVER}")
        mqtt_client = client
        return True
    except Exception as e:
        print(f"Failed to connect to MQTT: {e}")
        return False


def keep_connection_active() -> None:
    """
    Keep MQTT connection alive by sending ping.
    Raises exception if ping fails to trigger reconnection.
    """
    try:
        mqtt_client.publish(b"api/ping", b"ping")
    except Exception as e:
        print(f"Error sending ping to broker: {e}")
        raise


def main() -> None:
    global status_requested, mqtt_client

    cleanup_pins()

    last_send_status = time.ticks_ms()
    last_keep_alive = time.time()
    last_alarm_check = time.ticks_ms()
    last_pump_check = time.ticks_ms()

    while True:
        try:
            if not connect_to_mqtt():
                print("Failed to connect to MQTT, retrying...")
                time.sleep(MQTT_RETRY_INTERVAL)
                continue

            while True:
                current_time = time.time()
                ms_current_time = time.ticks_ms()

                mqtt_client.check_msg()

                if time.ticks_diff(ms_current_time, last_alarm_check) >= ALARM_CHECK_INTERVAL:
                    check_alarm()
                    check_pump_state()
                    last_alarm_check = ms_current_time

                if time.ticks_diff(ms_current_time, last_pump_check) >= PUMP_DRY_RUN_CHECK_INTERVAL:
                    check_pump_dry_run()
                    last_pump_check = ms_current_time

                if status_requested:
                    if (
                        time.ticks_diff(ms_current_time, last_send_status)
                        >= STATUS_SEND_INTERVAL
                    ):
                        send_water_tank_status()
                        last_send_status = ms_current_time

                    if current_time >= status_end_time:
                        status_requested = False
                        print("Status request timeout")

                if current_time - last_keep_alive >= KEEP_ALIVE_INTERVAL:
                    keep_connection_active()
                    last_keep_alive = current_time

                time.sleep(SLEEP_INTERVAL)

        except KeyboardInterrupt:
            print("Program interrupted by user")
            break

        except Exception as e:
            print(f"MQTT communication error: {e}")

        finally:
            try:
                if mqtt_client:
                    mqtt_client.disconnect()
                    mqtt_client = None
            except Exception as e:
                print(f"Error disconnecting client: {e}")

            time.sleep(MQTT_RETRY_INTERVAL)

    cleanup_pins()
    print("Program terminated")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
        cleanup_pins()
        machine.reset()
