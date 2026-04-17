# Runbook: Add a New RR Worker Node

## Overview

RR worker nodes run the RR worker container only (no web, alerter, nginx, or local DB). They connect to the application node DB via Tailscale. All worker LXCs get TUN device passthrough so RR can choose their egress model (Gluetun VPN or bare NAT).

## Naming convention

`rr-worker-<env>-<location>`
- **env**: `staging` or `prod`
- **location**: descriptive (`proxmox`, `home`, `mums`, etc.)

## Egress model

- Staging workers: Gluetun/VPN (unique exit IP per worker — never share an exit IP)
- Prod workers: bare residential NAT (unique residential IP per worker)
- Every worker must have a unique egress IP
- TUN device is always provisioned — RR decides whether to use Gluetun

## Proxmox spec

| Property | Value | Notes |
|---|---|---|
| OS | Ubuntu 24.04 | Standard |
| Cores | 2 | |
| RAM | 2048 MB | Worker only — no DB/web |
| Disk | 16 GB | |
| Storage | ssd-mirror | |
| Nesting | true | Required for Docker |
| TUN | true | Required for Tailscale + optional Gluetun |
| IP | 10.20.30.`<CTID>` | Follow CTID = last octet convention |

## Steps

### 1. Choose next available CT ID

```bash
ssh root@10.20.30.46 "pct list && qm list"
```

Next ID = next available after current highest.

### 2. Add to config/homelab.yaml

Under `services.lxcs`:

```yaml
rr-worker-<env>-<location>:
  id: <ID>
  ip: 10.20.30.<ID>
  cores: 2
  memory_mb: 2048
  disk_gb: 16
  tun_required: true
  roles:
  - docker
```

Under `remote_nodes.nodes`:

```yaml
rr-worker-<env>-<location>:
  ip: 10.20.30.<ID>
  tailscale_ip: null  # fill in after Tailscale join
  ssh_user: root
  location_label: <location>
  hostname: rr-worker-<env>-<location>
  environment: <env>
  roles: []
  wifi_enabled: false
  wifi_only: false
  tailscale:
    advertise_routes: []
    advertise_exit_node: false
    accept_dns: false
  battery:
    enabled: false
  powertop:
    enabled: false
  nagios:
    ping: true
    disk: true
    tailscale: true
    cpu_temp: false
    ntp: true
```

### 3. Add to ansible/inventory.yml

Add host entry to: `docker_hosts`, `guests`, `lxcs`, `promtail_hosts` groups.

### 4. Run Terraform

```bash
cd terraform
terraform plan
terraform apply -auto-approve
```

**Note:** Terraform creates the LXC but cannot set `lxc.cgroup2.devices.allow` or `lxc.mount.entry` (TUN passthrough). This must be done manually after creation.

### 5. Add TUN device passthrough

```bash
ssh root@10.20.30.46 "
  pct stop <ID>
  echo 'lxc.cgroup2.devices.allow: c 10:200 rwm' >> /etc/pve/lxc/<ID>.conf
  echo 'lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file' >> /etc/pve/lxc/<ID>.conf
  pct start <ID>
"
```

Verify: `ssh root@10.20.30.<ID> "ls -la /dev/net/tun"`

### 6. Run guest baseline + Docker

```bash
ansible-playbook ansible/playbooks/guests.yml --limit rr-worker-<env>-<location>
```

This runs guest-baseline, docker-host, log-policy, and promtail roles automatically.

### 7. Install Tailscale

```bash
ssh root@10.20.30.<ID> "curl -fsSL https://tailscale.com/install.sh | sh"
ssh root@10.20.30.<ID> "systemctl enable --now tailscaled"
```

### 8. Join Tailscale

```bash
ssh root@10.20.30.<ID> "tailscale up --hostname=rr-worker-<env>-<location> --accept-routes=false"
```

**IMPORTANT:** `--accept-routes=false` is mandatory for LAN-resident guests. See AGENTS.md known gotcha.

Authenticate via the login URL. Get Tailscale IP:

```bash
ssh root@10.20.30.<ID> "tailscale ip -4"
```

Update `homelab.yaml` with the Tailscale IP (`tailscale_ip` field).

### 9. Deploy Nagios checks

Re-render `remote-nodes.cfg.j2` and deploy to VM133:

```bash
python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
with open('config/homelab.yaml') as f:
    config = yaml.safe_load(f)
env = Environment(loader=FileSystemLoader('ansible/roles/remote-node-baseline/templates'))
template = env.get_template('remote-nodes.cfg.j2')
with open('/tmp/remote-nodes.cfg', 'w') as f:
    f.write(template.render(config=config))
"
scp /tmp/remote-nodes.cfg ubuntu@10.20.30.133:/tmp/
ssh ubuntu@10.20.30.133 "
  sudo cp /tmp/remote-nodes.cfg /usr/local/nagios/etc/objects/remote-nodes.cfg
  sudo chown nagios:nagios /usr/local/nagios/etc/objects/remote-nodes.cfg
  sudo /usr/local/nagios/bin/nagios -v /usr/local/nagios/etc/nagios.cfg
  sudo systemctl reload nagios
"
```

Deploy Nagios SSH key for check_by_ssh:

```bash
NAGIOS_KEY=$(ssh ubuntu@10.20.30.133 "sudo cat /var/lib/nagios/.ssh/id_ed25519.pub")
ssh root@10.20.30.<ID> "
  mkdir -p /root/.ssh && chmod 700 /root/.ssh
  echo '$NAGIOS_KEY' >> /root/.ssh/authorized_keys
  sort -u -o /root/.ssh/authorized_keys /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
"
```

Checks: PING, SSH, Disk, Tailscale, NTP (all via Tailscale IP).

### 10. Add DHCP reservation

```bash
MAC=$(ssh root@10.20.30.46 "pct config <ID> | grep -oP 'hwaddr=\K[^,]+'")
ssh admin@10.20.30.1 "
  current=\$(nvram get dhcp_staticlist)
  nvram set dhcp_staticlist=\"\${current}<${MAC}>10.20.30.<ID>>>\"
  nvram commit
  service restart_dnsmasq
"
```

### 11. Update docs

- `docs/agents/raffle-raptor.md` — add to node map
- `docs/changelog.md` — add entry
- `docs/backlog.md` — mark complete if applicable

### 12. Notify RR orchestrator

Provide:
- Node name and Tailscale IP
- TUN device available (`/dev/net/tun`)
- Docker installed
- Nagios + Promtail active
- Egress model is RR's decision

### RR agent responsibilities (after homelab confirms node is ready)

- Deploy worker Docker compose
- Configure DB connection via Tailscale to `rr-application-<env>-<location>`
- Configure egress (Gluetun or bare NAT)
- Ensure `/var/log/raffle-raptor/` exists so Promtail can ship app logs
- Confirm worker is running and scraping

## Known issues

- **Terraform cannot manage TUN passthrough** — `lxc.cgroup2.devices.allow` and `lxc.mount.entry` must be added manually to `/etc/pve/lxc/<ID>.conf` after TF creates the LXC. This is a Proxmox provider limitation.
- **Nagios delegation SSH user mismatch** — the remote-node-baseline role delegates Nagios config deployment to VM133 using `config.services.vms.nagios.ip`, but SSH auth fails because VM133 expects user `ubuntu` not `mrobinson`. Workaround: deploy Nagios config manually (template render + scp) as shown above.
- **Tailscale join is manual** — no auth-key automation yet. Each node requires browser authentication.
