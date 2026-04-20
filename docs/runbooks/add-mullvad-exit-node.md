# Runbook: Add Mullvad exit to a Tailscale gateway

## Overview

Adds Mullvad WireGuard egress (via `wg-quick@wg0`) to a Tailscale subnet-router/exit-node VM. All host traffic + Tailscale exit-node forwarded traffic egresses via Mullvad. LAN subnet routing continues via `eth0`. Kill-switch iptables rules prevent forwarded-traffic leaks if `wg0` is down.

Source role: `ansible/roles/mullvad-exit`.

## When to use

- Tailscale exit-node VMs where Mullvad egress is desired for all exit-forwarded traffic.
- NOT for application hosts that already use Gluetun (VM120, CT163, prod VPS). Those use Gluetun because the VPN is per-container, not per-host.

## Prerequisites

- Host already configured as a Tailscale subnet router / exit node (`tailscale-router` role).
- A free Mullvad device slot (check `docs/vpn.md` §Device Inventory).
- SSH + Proxmox console access to the target host (for recovery).

## Steps

### 1. Generate WireGuard keypair on the target host

```bash
ssh <host> '
  umask 077
  cd /tmp
  wg genkey | tee mullvad_privkey | wg pubkey > mullvad_pubkey
  echo "PUBLIC KEY: $(cat mullvad_pubkey)"
'
```

Record the public key. **Do not remove `/tmp/mullvad_privkey` yet** — you will pull it into the vault in step 4.

### 2. Register public key with Mullvad and pick server

1. Log in to Mullvad account portal.
2. Register the public key; name the device identifiably (e.g. `vm171 gateway`).
3. Note the Mullvad-assigned `Address` (IPv4/IPv6) for this device.
4. Pick a **pinned server** distinct from existing devices (check `docs/vpn.md` §Device Inventory). Before committing to a server, verify it is currently active and preferably Mullvad-owned (`owned: true`, provider `31173`) via the authoritative API — do not trust hostname numbering alone:

   ```bash
   curl -sS https://api.mullvad.net/www/relays/wireguard/ \
     | python3 -c "
   import json, sys
   rs = json.load(sys.stdin)
   for r in sorted(rs, key=lambda r: r['hostname']):
       if r['hostname'].startswith('gb-lon-wg-'):   # change prefix for other sites
           print(f\"{r['hostname']:20s} ipv4={r['ipv4_addr_in']:16s} active={r['active']} owned={r['owned']} provider={r['provider']}\")"
   ```

   Numbering is not contiguous (e.g. London jumps 008 → 201) and rented-provider servers may go inactive. Only pin a server flagged `active=true`. Prefer `owned=true` for stronger trust signal.
5. Download a WireGuard config for the chosen server.
6. From the downloaded config, record: `Endpoint` IP + port, `PublicKey` of the peer.
7. Update `docs/vpn.md` §Device Inventory with the new device.

### 3. Update `config/homelab.yaml`

Under the target host, add `mullvad_exit` to `roles` and populate `mullvad_exit` config block:

```yaml
<hostname>:
  ...
  roles:
  - tailscale_router
  - mullvad_exit
  mullvad_exit:
    interface_addresses:
      - "10.x.y.z/32"
      - "fc00:bbbb:.../128"
    endpoint_host: "gb-lon-wg-NNN.mullvad.net"
    endpoint_ip: "<IPv4 from Mullvad config>"
    endpoint_port: 51820
    peer_public_key: "<server PublicKey from Mullvad config>"
```

### 4. Add private key to vault

```bash
ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass ansible-vault edit ansible/secrets.yml
```

Add entry:

```yaml
mullvad_<host>_wg_private_key: "<contents of /tmp/mullvad_privkey from step 1>"
```

Wipe the on-host file:

```bash
ssh <host> 'shred -u /tmp/mullvad_privkey /tmp/mullvad_pubkey'
```

### 5. Wire the playbook

Ensure `ansible/playbooks/guests.yml` has a Mullvad-exit section binding to `mullvad_exit_hosts` (or equivalent group), and the role receives `mullvad_exit_private_key` from the vault.

### 6. Dry-run and apply

```bash
ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass \
  ansible-playbook ansible/playbooks/guests.yml --limit <host> --check --diff

ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass \
  ansible-playbook ansible/playbooks/guests.yml --limit <host>
```

### 7. Verify — abort and report if any step fails

Do not patch around failures; back out and investigate.

**a. wg0 up + handshake**
```bash
ssh <host> 'sudo wg show wg0 | grep -E "latest handshake|transfer"'
```
Expected: a recent handshake and non-zero transfer within ~1 min.

**b. Host egress is the pinned Mullvad IP**
```bash
ssh <host> 'curl -4 -s --max-time 10 https://ifconfig.me'
```
Expected: matches the Mullvad server's egress IP (check against Mullvad).

**c. Tailscale control plane still reachable**
```bash
ssh <host> 'sudo tailscale status --json | jq -r .BackendState,.Self.Online'
```
Expected: `Running`, `true`. If broken, abort — do not attempt workarounds.

**d. Kill-switch test**
```bash
ssh <host> 'sudo systemctl stop wg-quick@wg0'
# From a separate Tailscale client using this host as exit node:
#   curl -4 -s --max-time 10 https://ifconfig.me  # should fail / timeout, NOT return home NAT IP
ssh <host> 'sudo systemctl start wg-quick@wg0'
```
Expected: with wg0 down, forwarded traffic from tailnet clients does not reach the internet via eth0.

**e. LAN subnet routing unchanged**
From a Tailscale client that routes via this gateway, confirm LAN hosts are reachable (e.g. ping `10.20.30.154`). Not affected by Mullvad — must remain working.

### 8. Document

- Update `docs/vpn.md`:
  - Device Inventory table (new device, updated slot count).
  - Egress IP Map row for the gateway.
- Update `docs/changelog.md` with the deployment date and Mullvad device name.
- Close/update related backlog items.

## Rollback

If verification fails:

```bash
# Access via Proxmox console if SSH is lost:
#   qm terminal <VMID>         (HAOS/Ubuntu VM)
#   or the Proxmox web console

# Stop wg-quick and kill-switch:
sudo systemctl stop wg-quick@wg0 mullvad-exit-killswitch
sudo systemctl disable wg-quick@wg0 mullvad-exit-killswitch

# Remove role from host in config/homelab.yaml, re-run the baseline playbook.
```

Keep the Mullvad device registration in place during debugging — delete only after the root cause is understood.
