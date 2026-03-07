# ESP32 Automatic Water Tank API

MQTT API running on an ESP32 for remote control and monitoring of a water tank system. Controls a pump and siren relay, monitors an alarm sensor, and sends email notifications.

## Features

- Remote control of pump and siren via MQTT
- Real-time status monitoring (pump, alarm, relays, AC current)
- Alarm detection with MQTT + email notifications
- Daily command statistics reset at 23:59
- Email recipient management via MQTT
- NTP time synchronization with Europe/Rome timezone (DST aware)
- Automatic WiFi and MQTT reconnection

## Hardware

| Pin | Role |
|-----|------|
| 16 | Pump status (IN) |
| 17 | Alarm status (IN) |
| 18 | Pump relay (OUT) |
| 19 | Siren relay (OUT) |
| 32 | WiFi LED (OUT) |
| 33 | Aux power (OUT) |

## Setup

1. Copy `secrets.example.py` to `secrets.py` and fill in your credentials:

```python
WLAN_SSID = ""
WLAN_PASSWORD = ""

SERVER = ""        # MQTT broker address
USER = ""
PASSWORD = ""

EMAIL_HOST = ""    # e.g. smtps.aruba.it
EMAIL_PORT = 465
EMAIL_ADDRESS = ""
EMAIL_PASSWORD = ""
```

2. Flash all files to the ESP32 (e.g. with `mpremote` or Thonny).

## MQTT Topics

### Command topics (subscribe → ESP32 receives)

| Topic | Payload | Description |
|-------|---------|-------------|
| `api/water_tank/siren` | `{"cmd": "on\|off", "user": "name"}` | Toggle siren relay |
| `api/water_tank/pump` | `{"cmd": "on\|off", "user": "name"}` | Toggle pump relay |
| `api/water_tank/status` | _(any)_ | Start streaming status every second for 60s |
| `api/water_tank/statistics` | _(any)_ | Request current statistics |
| `api/water_tank/statistics/reset` | `{"cmd": "24h\|total\|all", "user": "name"}` | Reset counters |
| `api/water_tank/email/add` | `{"email": "addr@example.com"}` | Add email recipient |
| `api/water_tank/email/remove` | `{"email": "addr@example.com"}` | Remove email recipient |
| `api/water_tank/email/list` | _(any)_ | List all email recipients |
| `api/water_tank/email/test` | `{"email": "addr@example.com"}` | Send a test email to a specific address |

### Notification topics (ESP32 publishes)

| Topic | Description |
|-------|-------------|
| `api/notification/water_tank/status` | Tank status (pump, alarm, relays, current) |
| `api/notification/water_tank/alarm` | Alarm triggered / cleared |
| `api/notification/water_tank/siren` | Siren toggle result |
| `api/notification/water_tank/pump` | Pump toggle result |
| `api/notification/water_tank/statistics` | Statistics payload |
| `api/notification/water_tank/statistics/reset` | Reset confirmation |
| `api/notification/water_tank/email` | Email add/remove result |
| `api/notification/water_tank/email/list` | List of recipients |
| `api/notification/water_tank/email/test` | Test email result |

All notification payloads include a `timestamp` (Unix ms) and a `status` field (`"success"` or `"error"`).

## Alarm notifications

When the alarm pin goes high the system:
1. Publishes an MQTT notification immediately
2. Sends an email to all configured recipients
3. Repeats the email every **5 minutes** until the alarm clears

When the alarm clears, a single MQTT notification is published.

## Statistics

Counters track siren, pump, and alarm activations:
- **Daily** — reset automatically every day at **23:59**
- **Total** — cumulative, reset only manually via MQTT

Counters persist across reboots on the ESP32 filesystem.
