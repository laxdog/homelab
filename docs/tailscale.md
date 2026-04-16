# Tailscale (Phase 1)

Source of truth: `config/homelab.yaml` (`tailscale`, `services.vms.tailscale-gateway`, `services.lxcs.<name>.tailscale`).

## Scope
Phase 1 provides:
- remote access to LAN subnet `10.20.30.0/24`
- optional/on-demand home exit-node use

Out of scope in phase 1:
- Mullvad integration
- site-to-site / VPS connectivity
- redundancy/failover
- ACL/policy redesign

## Topology
- Dedicated VM: `tailscale-gateway`
- VMID: `171`
- LAN IP: `10.20.30.171`
- Role: `tailscale_router`
- Service LXC: `rr-application-staging-proxmox`
- CT ID: `163`
- LAN IP: `10.20.30.163`
- Role: `tailscale_router`
- Node override:
  - no advertised routes
  - no exit-node advertisement
  - `accept-dns=false`

This keeps Tailscale off the Proxmox host and limits routing changes to one guest VM.

## Repo-managed behavior
The `tailscale-router` role configures:
- Tailscale package/repository
- `tailscaled` service enabled/running
- forwarding sysctls:
  - `net.ipv4.ip_forward=1`
  - `net.ipv6.conf.all.forwarding=1`
- helper command:
  - `/usr/local/sbin/tailscale-phase1-up`

Default phase-1 flags used by helper command:
- `--advertise-routes=10.20.30.0/24`
- `--advertise-exit-node`
- `--accept-dns=false`

## Manual steps (phase 1)
1. Join/login the node:
   - `ssh ubuntu@10.20.30.171`
   - `sudo /usr/local/sbin/tailscale-phase1-up`
   - `ssh root@10.20.30.163`
   - `sudo /usr/local/sbin/tailscale-phase1-up`
2. In Tailscale admin console, approve:
   - subnet route `10.20.30.0/24`
   - exit node advertisement
   - (none required for `rr-application-staging-proxmox` unless policy approval is enabled in tailnet)
3. Configure split DNS in Tailscale admin:
   - domain: `laxdog.uk`
   - nameserver: `10.20.30.53`
4. Per client (optional):
   - accept subnet routes
   - choose exit node on demand

## Validation
Pre-join (expected valid state):
- VM reachable over SSH
- `tailscaled` active
- forwarding sysctls set to `1`

Post-join (manual/runtime checks):
- `tailscale status` reports Running
- route and exit-node are approved/active in admin console
- remote client can reach representative LAN IPs (`10.20.30.46`, `10.20.30.53`, `10.20.30.154`)
- internal name resolution for `*.laxdog.uk` works through split DNS

## Validation mode
Current repo default is `config.validation.tailscale_require_joined: true`, so validation fails if
the gateway is not joined (`BackendState != Running`).

For initial bootstrap only, temporarily set it to `false` until manual login + admin approvals are complete.
