#!/bin/bash

LOGFILE="/home/jacob/Desktop/Car/boot.log"
REPO_DIR="/home/jacob/Desktop/Car/Eng-Club-Self-Driving-Car"

echo "===== BOOT START $(date) =====" >> $LOGFILE

# 1. Handle WiFi connection
echo "[BOOT] Running WiFi setup..." >> $LOGFILE
bash /home/pi/wifi_connect.sh

if [ $? -ne 0 ]; then
    echo "[BOOT] WiFi failed. Shutting down." >> $LOGFILE
    sudo shutdown now
    exit 1
fi

echo "[BOOT] WiFi connected successfully." >> $LOGFILE

# 2. Update GitHub repo
echo "[BOOT] Updating repo..." >> $LOGFILE
cd $REPO_DIR || exit 1

git fetch origin >> $LOGFILE 2>&1
git reset --hard origin/main >> $LOGFILE 2>&1

if [ $? -ne 0 ]; then
    echo "[BOOT] Git update failed. Not arming motors." >> $LOGFILE
    exit 1
fi

echo "[BOOT] Repo updated successfully." >> $LOGFILE

# 3. Arm motors
echo "[BOOT] Arming motors..." >> $LOGFILE
python3 arm_motors.py >> $LOGFILE 2>&1

# 4. Start main program
echo "[BOOT] Starting main program..." >> $LOGFILE
python3 main.py >> $LOGFILE 2>&1