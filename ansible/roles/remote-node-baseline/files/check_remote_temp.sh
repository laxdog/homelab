#!/bin/bash
HOST=$1; USER=$2; KEY=/var/lib/nagios/.ssh/id_ed25519
raw=$(ssh -i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 $USER@$HOST 'cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -n | tail -1' 2>/dev/null)
[ -z "$raw" ] && echo 'UNKNOWN: SSH failed' && exit 3
temp=$(echo "scale=1; $raw / 1000" | bc)
tempi=$(echo "$raw / 1000" | bc)
[ $tempi -gt 80 ] && echo "CRITICAL: ${temp} C" && exit 2
[ $tempi -gt 70 ] && echo "WARNING: ${temp} C" && exit 1
echo "OK: ${temp} C" && exit 0
