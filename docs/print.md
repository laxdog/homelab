# Print Server (Brother HL-1110)

CT174 (`10.20.30.174`). Unprivileged Ubuntu 24.04 LXC running CUPS with the Brother HL-1110 attached via USB passthrough from the Proxmox host. Shares the printer to the LAN over IPP with mDNS/Bonjour broadcast so iOS (AirPrint) and Android (Mopria) clients auto-discover it. Internal-only (`print.laxdog.uk`); off-LAN / Tailscale exposure is deferred — see "Future options".

**OS choice — Ubuntu 24.04, not Debian 12.** Matches the template already staged on `tank-templates` (no extra `pveam download` prereq) and matches the jellyfin-hw precedent for passthrough-style containers (`terraform/jellyfin_hw.tf`), so this LXC follows an established working pattern. CUPS, avahi, i386 multiarch, and Brother's `.deb` wrappers behave identically on Ubuntu 24.04 and Debian 12 — zero functional difference for this workload.

## Status

**Brief stage** — not yet deployed. This document is the spec; once provisioned it becomes the operational runbook (same shape as `docs/obsidian.md`).

## Architecture

```
Brother HL-1110 (USB)
        │
        │ USB cable
        ▼
Proxmox host (10.20.30.46)
        │ /dev/bus/usb/<bus>/<dev>
        │ bind-mounted into CT174 via raw lxc.mount.entry
        ▼
CT174 cups (10.20.30.174)
  ├── cups.service          — IPP server on :631
  ├── cups-browsed.service  — outbound CUPS browsing
  ├── avahi-daemon.service  — mDNS / Bonjour announce
  └── /opt/brother/         — proprietary HL-1110 driver (32-bit)
        ▲
        │ IPP / mDNS on LAN
        │
   LAN clients (Mac, iOS, Android, laptops)
```

## Repo-managed pieces

| What | Where |
|---|---|
| LXC (id 174, 1 vCPU / 512 MB / 4 GB rootfs, ssd-mirror) | `config/homelab.yaml` `services.lxcs.print` |
| USB passthrough (`lxc.cgroup2.devices.allow` + `lxc.mount.entry`) | `/etc/pve/lxc/174.conf` — written by Ansible `cups-host` task on the Proxmox host (out-of-band; can't go through `pct set --dev<n>` because of the root@pam constraint that already affects jellyfin-hw — see `terraform/jellyfin_hw.tf` for the pattern) |
| Terraform `proxmox_virtual_environment_container.print` resource (imported, `lifecycle.ignore_changes` covers `mount_point` / `device_passthrough`) | `terraform/print.tf` |
| Ansible `cups` role: CUPS install, multiarch i386 deps, Brother driver staging, `cupsd.conf` Listen / Allow @LOCAL, avahi/cups-browsed enable, declarative `lpadmin` printer add | `ansible/roles/cups/` |
| Brother HL-1110 driver `.deb` files (proprietary, archived in repo for reproducibility) | `ansible/roles/cups/files/hl1110lpr-*.deb`, `hl1110cupswrapper-*.deb` |
| AdGuard rewrite for `print.laxdog.uk` | `config/homelab.yaml` `adguard.rewrites` |
| NPM proxy host (`forward_scheme: https`, `forward_port: 631`, internal access list) | `config/homelab.yaml` `npm.proxy_hosts` |
| Cert 17 SAN expansion for `print.laxdog.uk` | `config/homelab.yaml` `npm.certificates[0].domains` |
| Nagios port checks (CUPS :631, mDNS announce verified by IPP probe) | `config/homelab.yaml` `nagios.service_ports` |
| DHCP reservation on the router | `config/network.md` (manual update, per existing convention) |
| Playbook play (`cups_hosts`) | `ansible/playbooks/guests.yml` |
| Proxmox metadata SSH credential mapping | `config/homelab.yaml` `proxmox_metadata.service_credentials.print` |

## What is NOT repo-managed (one-time bootstrap)

These are the manual steps that don't fit the declarative pipeline. Same shape as the Obsidian bootstrap.

### 0. Prerequisites

- HL-1110 plugged into a USB port on the Proxmox host (10.20.30.46) and powered on. Probed 2026-04-28: `lsusb` reports `Bus 001 Device 003: ID 04f9:0054 Brother Industries, Ltd HL-1110 series`. Vendor:product `04f9:0054` is stable across reboots; the bus number can drift on unplug/replug, which is why we whole-tree bind `/dev/bus/usb` rather than a specific bus path (step 1).
- LXC 174 created via the create-script in step 1 below and Terraform-imported.
- DNS rewrite + NPM cert applied; `https://print.laxdog.uk:631` returns the CUPS web UI.

### 1. Create the bare LXC on the host (one-time)

`terraform apply` cannot create CT174 directly: USB device passthrough via `pct set --dev<n>` is one of the operations Proxmox restricts to interactive `root@pam` only. Same constraint that drove the jellyfin-hw split (`terraform/jellyfin_hw.tf`).

Run as `root@10.20.30.46`:

```bash
pct create 174 tank-templates:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst \
  --hostname print \
  --cores 1 --memory 512 --swap 256 \
  --rootfs ssd-mirror:4 \
  --net0 name=eth0,bridge=vmbr0,ip=10.20.30.174/24,gw=10.20.30.1 \
  --nameserver 10.20.30.53 \
  --unprivileged 1 \
  --features nesting=1 \
  --onboot 1 \
  --ssh-public-keys /root/.ssh/authorized_keys \
  --start 0
```

Then append USB passthrough to `/etc/pve/lxc/174.conf`:

```
lxc.cgroup2.devices.allow: c 189:* rwm
lxc.mount.entry: /dev/bus/usb dev/bus/usb none bind,optional,create=dir
```

Bind the whole `/dev/bus/usb` directory rather than a single bus path — that survives unplug/replug renumbering, which is the gotcha the original brief flagged. Then `pct start 174`.

Inside the container, `lsusb` should now list the Brother device. If it doesn't, the next escape hatch is `lxc.apparmor.profile: unconfined` in the same conf file (loosens isolation; only if the cgroup+mount lines alone don't work).

Finally, from `terraform/`:

```bash
terraform import proxmox_virtual_environment_container.print 174
terraform plan   # must come back clean — anything dirty needs ignore_changes added
```

### 2. Brother driver staging (one-time, manual download)

Brother only distributes HL-1110 drivers from their support site, behind a click-through. `brlaser` does **not** support the 1110 (no rendering on the printer; HL-1110 is GDI / host-rendered). Download once, archive in the repo, then the role installs idempotently.

1. From `https://support.brother.com/g/b/downloadtop.aspx?prod=hl1110_eu` grab:
   - `hl1110lpr-<version>.i386.deb`
   - `hl1110cupswrapper-<version>.i386.deb`
2. Verify both checksums against Brother's published list.
3. Drop both into `ansible/roles/cups/files/` and commit (small files; reproducibility wins over fetch-at-apply).

**Licensing note.** Brother's HL-1110 driver `.deb`s are proprietary, redistributed under their EULA. Committing them here is fine while this repo is private; revisit (mirror them out, or fetch-at-apply with checksum pin) before the repo is ever made public.

The role enables `dpkg --add-architecture i386`, installs `lib32stdc++6 lib32z1`, and runs `dpkg -i --force-all` on each .deb (Brother's `.deb`s have broken control fields; `--force-all` is their documented workaround). Files land under `/opt/brother/`.

### 3. Add the printer queue (one-time, scripted from the role)

The role calls:

```
lpadmin -p HL1110 -E \
  -v usb://Brother/HL-1110%20series \
  -m brother-HL1110-cups-en.ppd \
  -L "Carrickfergus office" \
  -o printer-is-shared=true
cupsenable HL1110
cupsaccept HL1110
lpoptions -d HL1110
```

(The exact `-v` URI and PPD filename come from the wrapper install — the role discovers them via `lpinfo -v` / `lpinfo -m | grep -i 1110` on first run. Web UI bootstrap is **not** required.)

### 4. Discovery

`avahi-daemon` + `cups-browsed` come up enabled. Verify from any LAN client:

```
avahi-browse -a | grep -i ipp
```

Expect `_ipp._tcp` (and `_ipps._tcp`) advertising the queue. iOS prints from the share sheet; Android needs the Mopria Print Service app (not always preinstalled).

## Acceptance tests

Tick when the bootstrap completes — these are the gates before declaring the task done.

- [ ] `lsusb` inside CT174 shows the Brother HL-1110.
- [ ] `https://print.laxdog.uk:631` reaches the CUPS web UI (NPM-terminated LE cert).
- [ ] `lpstat -p HL1110` reports `enabled and accepting requests`.
- [ ] CUPS web UI test page prints.
- [ ] Printer appears in macOS Print dialog without manual setup (AirPrint discovery).
- [ ] Printer appears in iOS share sheet (AirPrint).
- [ ] Printer appears for Android via Mopria Print Service.
- [ ] Test page prints from at least one phone (cold and after >30 min idle — see "deep sleep" gotcha).
- [ ] Nagios `print` host green; CUPS port check on :631 PASSING.

## Known gotchas

- **USB bus renumbering after unplug/replug** can break a single-bus bind. Mitigation already taken: bind `/dev/bus/usb` whole-tree (step 1) rather than one specific `<bus>` path.
- **GDI / host-based rendering.** HL-1110 has no on-printer rendering; all rasterisation happens on CT174. The print server must be up for any job. Implication: don't ZFS snapshot-rollback / `pct stop` CT174 mid-print.
- **i386 multilib requirement.** Brother's drivers are 32-bit. Works on the x86_64 Proxmox host today; will not work if CT174 is ever migrated to an arm64 host. Flag this in the role's preflight (`assert: ansible_architecture in [x86_64, amd64]`).
- **No status feedback.** The Brother wrapper does not report toner / paper-jam state cleanly back to CUPS. Web UI shows "printing" and hopes. Aftermarket toner may need a panel reset; unrelated to server config.
- **Deep-sleep first-job swallow.** HL-1110 in deep sleep occasionally drops the first job after long idle. Annoying, retry-able. If it gets noisy, disable deep sleep on the printer panel (slightly higher idle power) or schedule a wake-up cron.
- **CUPS self-signed cert behind NPM.** CUPS terminates HTTPS on :631 with its own self-signed cert. Use `forward_scheme: https` in NPM with backend SSL verification disabled — same pattern as the Proxmox NPM entry. Do not try to disable HTTPS on CUPS; it forces redirects on `/admin` regardless and it's not worth the fight.
- **CUPS web UI is not Authentik-protected.** Internal access only (LAN + Tailscale subnet route). Anyone on the LAN with the URL can submit print jobs and see the queue. Acceptable for this service; revisit if external exposure ever lands.

## Operating rules (reminder for the rollout)

- Commit `config/homelab.yaml` + `terraform/print.tf` + `ansible/roles/cups/` changes to the repo **before** applying. Per AGENTS.md.
- Don't run a broad `terraform apply` after import — narrow with `-target=proxmox_virtual_environment_container.print`. The `lifecycle.ignore_changes` should keep plans clean, but verify on the first run.
- Don't `pct set --dev0 …` post-create — that's the operation that fails with the root@pam constraint. Edit `/etc/pve/lxc/174.conf` directly.
- No push without explicit instruction.
- Run `terraform plan` before `apply`. Run `terraform plan` again at end-of-session.

## Operational notes (post-bootstrap)

- **Restart CUPS:** `ssh root@10.20.30.174 systemctl restart cups`
- **Tail print logs:** `ssh root@10.20.30.174 journalctl -u cups -f`
- **Check active queue:** `ssh root@10.20.30.174 lpstat -o`
- **Re-detect USB after a printer swap:** unplug/replug on the host (the whole-bus bind survives), then `pct restart 174` if `lsusb` inside the container is empty.
- **Cancel everything:** `ssh root@10.20.30.174 cancel -a`
- **PPD location:** `/etc/cups/ppd/HL1110.ppd` (managed by `lpadmin`, not Ansible templated — Brother's wrapper writes this).

## Future options (post-basics)

- **Tailscale / off-LAN exposure.** Stable MagicDNS hostname + manual IPP add on phones. iOS AirPrint over Tailscale needs an mDNS reflector (Avahi reflector mode on VM171 or similar) — non-trivial. Pure manual IPP works without it.
- **Print-job notifications to Discord/Telegram.** Fits the existing RR alert plumbing. CUPS notification handler → webhook → existing channel.
- **PaperCut NG free tier.** Per-user usage stats + Grafana scrape via JSON exporter.
- **Scanner integration.** HL-1110 is print-only; future MFPs would need SANE in-container.
- **External (`lax.dog`) exposure.** Out of scope today — printing is LAN/Tailscale-only.

## Backlog items spawned by this brief

- [ ] **Codify CT174 USB passthrough lines as a `cups-host` Ansible role** so `/etc/pve/lxc/174.conf` is reproducible from the repo (today: written by hand during step 1 bootstrap). Mirrors the jellyfin-hw out-of-band pattern. Effort: low.
- [ ] **mDNS reflector for AirPrint over Tailscale.** Defer until a phone needs to print from outside the LAN.
- [ ] **Print-job notification webhook** wired into existing RR alert pipe. Low priority.

## See also

- `docs/runbooks/add-new-guest.md` — generic guest provisioning checklist.
- `terraform/jellyfin_hw.tf` — sibling pattern for `pct create` + `terraform import` + `lifecycle.ignore_changes` when device passthrough hits the root@pam constraint.
- `docs/obsidian.md` — comparable repo-managed-pieces + GUI/manual-bootstrap split.
- AGENTS.md → "Domain architecture" — laxdog.uk vs lax.dog rules (this service is laxdog.uk only).
- Memory `feedback_terraform_root_pam.md` — why USB device passthrough cannot go through the standard TF flow.
