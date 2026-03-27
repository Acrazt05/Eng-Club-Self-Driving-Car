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
STEERING_CENTER = 90

# Max steering angle
MAX_STEERING_ANGLE = 30

# Deadzone
DEADZONE = 0.05

# Failsafe timeout
TIMEOUT = 1.0

# State variables
last_cmd_time = time.time()
last_cmd_lock = Lock()

motors_armed = False

# ==========================================


# -------- MOTOR CONTROL --------

def set_throttle(value):
    global motors_armed

    if not motors_armed:
        return

    for ch in MOTOR_CHANNELS:
        kit.continuous_servo[ch].throttle = value


def set_steering(value):
    angle_offset = value * MAX_STEERING_ANGLE

    left_angle = STEERING_CENTER + angle_offset
    right_angle = STEERING_CENTER + angle_offset

    kit.servo[STEERING_LEFT].angle = left_angle
    kit.servo[STEERING_RIGHT].angle = right_angle


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