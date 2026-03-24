#!/bin/bash

TARGET_WIFI="GuestWifi"
MAX_RETRIES=5
LOGFILE="/home/pi/wifi.log"

echo "===== WIFI START $(date) =====" >> $LOGFILE

# Function to check internet
check_internet() {
    ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1
    return $?
}

# 1. Try to connect to GuestWifi
echo "[WIFI] Connecting to $TARGET_WIFI..." >> $LOGFILE
nmcli dev wifi connect "$TARGET_WIFI" >> $LOGFILE 2>&1

sleep 5

# 2. Try captive portal login if needed
for i in $(seq 1 $MAX_RETRIES)
do
    echo "[WIFI] Checking internet (attempt $i)..." >> $LOGFILE

    if check_internet; then
        echo "[WIFI] Internet is working." >> $LOGFILE
        exit 0
    fi

    echo "[WIFI] No internet. Running captive portal script..." >> $LOGFILE
    python3 /home/jacob/Desktop/Car/Eng-Club-Self-Driving-Car/connect_wifi.py >> $LOGFILE 2>&1

    sleep 5
done

# 3. Try fallback known networks
echo "[WIFI] Trying fallback networks..." >> $LOGFILE

nmcli connection up id "$(nmcli -t -f NAME connection show | head -n 1)" >> $LOGFILE 2>&1
sleep 5

if check_internet; then
    echo "[WIFI] Connected via fallback network." >> $LOGFILE
    exit 0
fi

echo "[WIFI] Failed to get internet." >> $LOGFILE
exit 1