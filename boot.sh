#!/bin/bash

LOGFILE="/home/jacob/Desktop/Car/boot.log"
TARGET_WIFI="GuestWifi"
MAX_RETRIES=10

echo "===== BOOT $(date) =====" >> $LOGFILE

# Function: check internet
check_internet() {
    ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1
    return $?
}

# Wait until connected to SOME wifi
echo "[BOOT] Waiting for WiFi connection..." >> $LOGFILE

while true
do
    CURRENT_WIFI=$(iwgetid -r)

    if [ -n "$CURRENT_WIFI" ]; then
        echo "[BOOT] Connected to WiFi: $CURRENT_WIFI" >> $LOGFILE
        break
    fi

    sleep 2
done


# If connected to GuestWifi we may need to accept terms
if [ "$CURRENT_WIFI" = "$TARGET_WIFI" ]; then

    echo "[BOOT] GuestWifi detected. Checking internet..." >> $LOGFILE

    for i in $(seq 1 $MAX_RETRIES)
    do
        if check_internet; then
            echo "[BOOT] Internet working." >> $LOGFILE
            break
        fi

        echo "[BOOT] No internet. Sending captive portal request (attempt $i)" >> $LOGFILE

        python3 /home/jacob/Desktop/Car/Eng-Club-Self-Driving-Car/connect_wifi.py >> $LOGFILE 2>&1

        sleep 5
    done
fi


# Wait until internet is confirmed
echo "[BOOT] Waiting for internet..." >> $LOGFILE

until check_internet
do
    sleep 2
done

echo "[BOOT] Internet confirmed." >> $LOGFILE


# Start main program
echo "[BOOT] Starting MQTT control..." >> $LOGFILE

python3 /home/jacob/Desktop/Car/Eng-Club-Self-Driving-Car/main.py >> $LOGFILE 2>&1