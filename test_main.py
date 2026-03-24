import json
import time
import psutil
import socket
from threading import Thread, Lock

import paho.mqtt.client as paho
from paho import mqtt
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# ================= CONFIG =================
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

CONTROL_TOPIC = "car/control"
TELEMETRY_TOPIC = "car/telemetry"

# Deadzone for joystick input
DEADZONE = 0.05

# Time in seconds to stop motors if no message
TIMEOUT = 1.0

# Last received command timestamp
last_cmd_time = time.time()
last_cmd_lock = Lock()

# ==========================================

# -------- MOTOR CONTROL (SIMULATED) --------
def set_throttle(value):
    """Simulate motor throttle"""
    print(f"[SIM] Set throttle: {value:.2f}")

def set_steering(value):
    """Simulate steering servo"""
    print(f"[SIM] Set steering: {value:.2f}")

# -------- MQTT CALLBACKS --------
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT with code {rc}")
    client.subscribe(CONTROL_TOPIC)

def on_message(client, userdata, msg):
    global last_cmd_time
    try:
        data = json.loads(msg.payload.decode())

        throttle = float(data.get("throttle", 0))
        steering = float(data.get("steering", 0))

        # Clamp values
        throttle = max(-1, min(1, throttle))
        steering = max(-1, min(1, steering))

        # Apply deadzone
        if abs(throttle) < DEADZONE:
            throttle = 0
        if abs(steering) < DEADZONE:
            steering = 0

        set_throttle(throttle)
        set_steering(steering)

        with last_cmd_lock:
            last_cmd_time = time.time()

        print(f"Throttle: {throttle:.2f}, Steering: {steering:.2f}")

    except Exception as e:
        print("Error processing message:", e)

# -------- TELEMETRY --------
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "unknown"

def get_cpu_temp():
    # Windows doesn't provide thermal_zone0
    return None

def telemetry_loop(client):
    while True:
        data = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "temperature": get_cpu_temp(),
            "ip": get_ip(),
            "timestamp": time.time()
        }

        client.publish(TELEMETRY_TOPIC, json.dumps(data))
        time.sleep(2)

# -------- FAILSAFE LOOP --------
def failsafe_loop():
    global last_cmd_time
    while True:
        with last_cmd_lock:
            elapsed = time.time() - last_cmd_time
        if elapsed > TIMEOUT:
            set_throttle(0)
        time.sleep(0.1)

# -------- MAIN --------
def main():
    if not MQTT_BROKER:
        raise ValueError("MQTT_BROKER not set in .env")

    client = paho.Client()

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    # Start telemetry thread
    Thread(target=telemetry_loop, args=(client,), daemon=True).start()

    # Start failsafe thread
    Thread(target=failsafe_loop, daemon=True).start()

    client.loop_forever()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Shutting down...")
        set_throttle(0)
        set_steering(0)