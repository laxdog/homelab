#!/bin/bash
HOST=$1; USER=$2; KEY=/var/lib/nagios/.ssh/id_ed25519
drift=$(ssh -i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 $USER@$HOST 'chronyc tracking 2>/dev/null | grep "System time"' 2>/dev/null | awk '{gsub(/[+-]/,"",$4); print $4+0}')
[ -z "$drift" ] && echo 'UNKNOWN: SSH failed' && exit 3
over1=$(echo "$drift > 1" | bc)
over05=$(echo "$drift > 0.5" | bc)
[ "$over1" = '1' ] && echo "CRITICAL: drift ${drift}s" && exit 2
[ "$over05" = '1' ] && echo "WARNING: drift ${drift}s" && exit 1
echo "OK: drift ${drift}s" && exit 0
