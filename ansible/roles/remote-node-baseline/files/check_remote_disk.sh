#!/bin/bash
HOST=$1; USER=$2; KEY=/var/lib/nagios/.ssh/id_ed25519
pct=$(ssh -i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 $USER@$HOST 'df / | tail -1' 2>/dev/null | awk '{print $5+0}')
[ -z "$pct" ] && echo 'UNKNOWN: SSH failed' && exit 3
[ $pct -gt 90 ] && echo "CRITICAL: disk ${pct}%" && exit 2
[ $pct -gt 80 ] && echo "WARNING: disk ${pct}%" && exit 1
echo "OK: disk ${pct}%" && exit 0
