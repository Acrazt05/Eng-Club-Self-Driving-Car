import json
import time
import psutil
import socket
from threading import Thread, Lock

import paho.mqtt.client as paho
from paho import mqtt
from adafruit_servokit import ServoKit
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup

# Load .env file
load_dotenv()

# ================= CONFIG =================

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

CONTROL_TOPIC = "car/control"
TELEMETRY_TOPIC = "car/telemetry"

# ServoKit setup
kit = ServoKit(channels=16)

# Motor channels
MOTOR_CHANNELS = [0, 1, 2, 3]

# Steering servo channels
STEERING_LEFT = 4
STEERING_RIGHT = 5

# Neutral values
MOTOR_STOP = 0.0
STEERING_MIN = 0
STEERING_MAX = 45
STEERING_CENTER = 22.5

# Deadzone
DEADZONE = 0.05

# Failsafe timeout
TIMEOUT = 1.0

# State variables
last_cmd_time = time.time()
last_cmd_lock = Lock()

motors_armed = True

# ==========================================


# -------- MOTOR CONTROL --------

def set_throttle(value):
    global motors_armed

    if not motors_armed:
        return

    for ch in MOTOR_CHANNELS:
        kit.continuous_servo[ch].throttle = value


def set_steering(value):
    """
    value: -1 (left) to 1 (right)
    servo range: 0 to 45 degrees
    center: 22.5 =~ 27
    """

    if value == 0:
        angle = 27
    else:
        # map -1..1 → 0..45
        angle = (value + 1) * 22.5

    # clamp just to be safe
    angle = max(0, min(45, angle))

    kit.servo[STEERING_LEFT].angle = angle
    kit.servo[STEERING_RIGHT].angle = angle

def stop_motors():
    for ch in MOTOR_CHANNELS:
        kit.continuous_servo[ch].throttle = 0

    print("Motors stopped.")


def arm_motors():
    global motors_armed

    print("Arming ESCs...")

    for ch in MOTOR_CHANNELS:
        kit.continuous_servo[ch].throttle = 1

    print("Waiting for ESCs to arm...")
    time.sleep(2)

    for ch in MOTOR_CHANNELS:
        kit.continuous_servo[ch].throttle = 0

    motors_armed = True

    print("Motors armed.")


# -------- MQTT CALLBACKS --------

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT with code {rc}")
    client.subscribe(CONTROL_TOPIC)


def on_message(client, userdata, msg):
    global last_cmd_time

    try:
        data = json.loads(msg.payload.decode())

        # ---- COMMAND HANDLING ----
        command = data.get("command")

        if command == "arm":
            arm_motors()
            return

        if command == "stop":
            stop_motors()
            return

        # ---- DRIVE COMMAND ----
        throttle = float(data.get("throttle", 0))
        steering = float(data.get("steering", 0))

        # Clamp
        throttle = max(-1, min(1, throttle))
        steering = max(-1, min(1, steering))

        # Deadzone
        if abs(throttle) < DEADZONE:
            throttle = 0

        if abs(steering) < DEADZONE:
            steering = 0

        set_throttle(throttle)
        set_steering(steering)

        with last_cmd_lock:
            last_cmd_time = time.time()

        print(f"Throttle: {throttle}, Steering: {steering}")

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
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read()) / 1000.0
            return temp
    except:
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
            stop_motors()

        time.sleep(0.1)


# -------- MAIN --------

def main():
    ssid=os.popen("sudo iwgetid -r").read()

    if(ssid=="GuestWifi\n"):
        print("Connected to school wifi")

        url = "http://198.18.32.1/reg"#/php?ah_goal=index.html&ah_log=true"
        payload = {"url":"E2B8F3578D88E9E372C8A715DED910CE976547C419","checkbox":"checkbox"}
        headers = {"Content-type":"application/x-www-form-urlencoded"}

        response = requests.post(url, data=payload, headers=headers)

        if response.status_code == 200:
            soud = BeautifulSoup(response.text, "html.parser")
            
            print ("Connected to WiFi")
        #else:
        #    raise ValueError(f"Resquest failed with status code {response.status_code}")

    if not MQTT_BROKER:
        raise ValueError("MQTT_BROKER not set in .env")

    client = paho.Client()

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    # Telemetry thread
    t1 = Thread(target=telemetry_loop, args=(client,), daemon=True)
    t1.start()

    # Failsafe thread
    t2 = Thread(target=failsafe_loop, daemon=True)
    t2.start()

    client.loop_forever()


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("Shutting down...")
        stop_motors()
        set_steering(0)
