#!/bin/bash
HOST=$1; USER=$2; KEY=/var/lib/nagios/.ssh/id_ed25519
state=$(ssh -i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 $USER@$HOST 'tailscale status --json 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin).get(\"BackendState\",\"Unknown\"))"' 2>/dev/null)
[ -z "$state" ] && echo 'UNKNOWN: SSH failed' && exit 3
[ "$state" = 'Running' ] && echo "OK: Tailscale $state" && exit 0
echo "CRITICAL: Tailscale $state" && exit 2
