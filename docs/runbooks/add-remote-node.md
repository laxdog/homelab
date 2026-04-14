# Runbook: Add a New Remote Node

## Prerequisites
- Ubuntu 24.04 installed on the target machine
- Tailscale account access to approve new device
- Machine reachable via Tailscale after join

## Steps

1. **Join Tailscale**: on the target machine, run `tailscale up` and approve the device in the Tailscale admin panel. Note the Tailscale IP.

2. **Add to config/homelab.yaml** under `remote_nodes.nodes`:
   ```yaml
   <hostname>:
     ip: 10.20.30.<lan-ip>
     tailscale_ip: 100.x.x.x
     ssh_user: <username>
     hostname: <hostname>
     environment: staging|prod
     roles: [remote_node_baseline, tailscale_router]
     battery:
       enabled: true|false
       start_threshold: 40  # ThinkPad only
       stop_threshold: 80
     powertop:
       enabled: true
       exclude_interfaces: [wlp3s0, tailscale0]
     nagios:
       ping: true
       disk: true
       tailscale: true
       cpu_temp: true
       ntp: true
   ```

3. **Add to ansible/inventory.yml** under `remote_node_baseline_hosts` using Tailscale IP as `ansible_host`.

4. **Run wifi-sync** to push all WiFi networks to the new node:
   ```bash
   ansible-playbook ansible/playbooks/wifi-sync.yml --limit <hostname>
   ```

5. **Run remote-nodes playbook**:
   ```bash
   ansible-playbook ansible/playbooks/remote-nodes.yml --limit <hostname>
   ```

6. **Verify on the node**:
   - WiFi networks configured (`nmcli connection show | grep wifi`)
   - Tailscale active (`tailscale status`)
   - Battery thresholds set if ThinkPad (`tlp-stat -b | grep threshold`)
   - Powertop service running (`systemctl status powertop-autotune`)
   - Chrony synced (`chronyc tracking`)
   - Nagios checks appear on VM133

7. **Commit** homelab.yaml and inventory changes.
