# Claude Code Handoff

Last updated: 2026-03-28
Repo: `/home/mrobinson/source/homelab`
Branch: `main`
HEAD at handoff time: `e616018455cec1d96c23cd280462040ee165c056`
Current latest commit: `e616018` - `Fix Bazarr access and Heimdall icon overrides`

This brief is for Claude Code taking over ongoing homelab infra work. It is written to be usable cold. It assumes no prior chat context.

## Project Overview

### What this repo is
This repo is the homelab infra source of truth for the user's local estate. It owns:
- homelab topology and desired state in `config/homelab.yaml`
- Proxmox guest inventory and infra automation
- internal DNS design via AdGuard
- reverse proxy and internal/external hostname model via NPM
- external DNS/auth integration via Cloudflare + Authentik
- dashboard generation via Heimdall
- remote-node and Tailscale baseline
- apt-cacher infra policy for Debian/Ubuntu LXCs
- some homelab-owned runtime config for VM120 media ingress/routing and compose templating

It does **not** own:
- app-level media policy/content/indexer decisions inside the media stack
- Raffle Raptor application logic, schema, product behavior, worker behavior
- broad redesigns across app repos unless explicitly handed over

### Ownership boundary
#### Homelab-owned
- Proxmox hosts, VM/LXC definitions, host storage, backup policy
- host-managed datasets and guest mount presentation
- DNS, NPM, Cloudflare, Authentik, dashboards
- remote node baseline, Tailscale plumbing, RR staging DB transport path
- VM120 root disk, virtiofs media/download mounts, routing to media apps

#### Media-stack-owned
- app directory structure inside VM120 under `/srv/data` and `/opt/media-stack/appdata`
- docker compose/app config inside the media stack
- app-specific auth/whitelist/base URL/runtime behavior
- content/indexer/provider choices

#### Raffle Raptor-owned
- app deployment behavior and runtime logic
- business logic, DB/schema decisions, workers, product behavior

### Durable user preferences
- safety-first over speed
- accuracy over speed
- no opportunistic changes
- narrow commits only
- do not include unrelated dirty files
- do not push unless explicitly told
- prefer proving live state over assuming from repo only
- if a task is app-side and not homelab-owned, stop at a precise boundary/handoff

## Full Infrastructure Topology

### Main Proxmox estate
Primary Proxmox host is `10.20.30.46`.

#### VMs
- `120 media-stack` - `10.20.30.120` - Docker media stack VM - running
- `122 home-assistant` - `10.20.30.134` - HAOS - running
- `133 nagios` - `10.20.30.133` - monitoring - running
- `171 tailscale-gateway` - `10.20.30.171` - tailscale router/gateway - running

#### LXCs
- `128 couchdb` - `10.20.30.128` - CouchDB - running
- `153 adguard` - `10.20.30.53` - canonical internal DNS - running
- `154 nginx-proxy-manager` - `10.20.30.154` - reverse proxy / TLS - running
- `156 apt-cacher-ng` - `10.20.30.156` - apt cache - running
- `157 freshrss` - `10.20.30.157` - FreshRSS - running
- `158 netalertx` - `10.20.30.158` - NetAlertX - running
- `159 healthchecks` - `10.20.30.159` - Healthchecks - running
- `160 dashboard` - `10.20.30.160` - dashboard helper / legacy dashboard estate - running
- `161 static-sites` - `10.20.30.161` - static sites - running
- `162 browser` - `10.20.30.162` - Firefox/browser container - running
- `163 raffle-raptor-dev` - `10.20.30.163` - RR dev infra node - running
- `164 organizr` - `10.20.30.164` - Organizr - running
- `166 heimdall` - `10.20.30.166` - Heimdall - running
- `170 authentik` - `10.20.30.170` - Authentik - running

### Router / DNS / proxy / auth layout
- Router: `10.20.30.1`
  - ASUS RT-AC86U class device
  - running `dnsmasq`
- Canonical internal DNS: AdGuard on `10.20.30.53`
- Reverse proxy/TLS: NPM on `10.20.30.154`
- Identity/auth gateway: Authentik on `10.20.30.170`
- Dashboard: Heimdall on `10.20.30.166`
- Secondary dashboard: Organizr on `10.20.30.164`

### Two-site PtP context
Historical two-site / PtP split matters because it caused earlier confusion and outages.
- Near-side Ubiquiti PtP device: `10.20.30.50` (`Liberty`)
- Remote-side Ubiquiti PtP device: `10.20.30.51` (`Ellis`)
- Earlier incidents included the far-side being unreachable and duplicate-IP weirdness across the estate.
- The old Proxmox host at `10.20.30.155` was powered off for move and is not yet cleaned up.

### Tailscale / remote nodes
- `raptor-node-staging` - `10.20.30.153`
  - Tailscale healthy
  - `BackendState=Running`
  - Tailscale IP `100.88.35.124`
  - `ExitNodeOption=True`
- `raffle-raptor-dev` - `10.20.30.163`
  - Tailscale healthy
  - Tailscale IP `100.92.43.108`
  - `ExitNodeOption=False`
- `mums-house-mbp` - `10.20.30.75`
  - unreachable during latest validation (`No route to host`)
  - no fresh state beyond repo intent

RR staging DB transport on `raffle-raptor-dev` is active:
- `rr-db-ts-proxy` active/enabled
- `rr-db-ts-firewall` active/enabled
- listener on `100.92.43.108:5432` via `socat`

## DNS And Routing Model

### Domain split
#### Internal
- `*.laxdog.uk`
- intended for internal-only access
- internal clients resolve via AdGuard
- AdGuard rewrites resolve service names to NPM `10.20.30.154`
- NPM proxies to backend services
- no proxy auth on internal routes unless explicitly configured otherwise

#### External
- `*.lax.dog`
- public Cloudflare zone
- external requests land at NPM
- external routes use Authentik forward-auth where configured

### Root domains
Current intended/live behavior:
- `laxdog.uk` -> Heimdall internally
- `lax.dog` -> Heimdall externally via Authentik-protected path

### Internal resolution pattern
Typical path:
1. client asks AdGuard `10.20.30.53`
2. AdGuard rewrite answers `10.20.30.154`
3. request reaches NPM with SNI for requested hostname
4. NPM proxies to backend host/port

### Historical incidents that still matter
#### Duplicate `.53` AdGuard incident
- there were effectively two `.53` identities at different times / likely overlap
- legacy AdGuard on old Proxmox host conflicted with canonical CT153 AdGuard on `10.20.30.46`
- this caused major DNS confusion and stale/wrong answers
- canonical `.53` is now CT153 on `10.20.30.46`

#### Cloudflare wildcard fallback incident
Cloudflare previously had:
- apex `laxdog.uk -> 10.20.30.175`
- wildcard `*.laxdog.uk -> CNAME laxdog.uk`
This caused unknown internal names to fall through to `10.20.30.175`.
That fallback has been removed.

#### Router stale-cache issue
- Router `10.20.30.1` was serving bad wildcard/internal answers from stale cache at one point.
- Router cache behavior is no longer the primary root cause, but it remains historically relevant.

## Repo Structure And Source Of Truth

### Main source of truth
- `config/homelab.yaml`

This file drives:
- AdGuard rewrites
- NPM internal proxy hosts
- NPM external proxy hosts
- Authentik external app model
- Heimdall generated entries
- guest/service IPs and roles
- remote node metadata

### How generation works
#### NPM
- `config.npm.proxy_hosts` -> internal NPM hosts
- `config.npm.external_proxy_hosts` -> external NPM hosts
- applied by NPM API/config roles

#### AdGuard
- `config.adguard.rewrites` -> internal hostname rewrites
- rendered into AdGuard config + API-managed rewrite state

#### Authentik
- `config.authentik.proxy_apps` tracks the intended external protected app model
- external hosts in NPM use `authentik_protect: true` where applicable

#### Heimdall
- generated primarily from `config.npm.proxy_hosts`
- exclusions and extra non-NPM links are handled in Heimdall role logic
- extra items come from `config.heimdall.extra_items`

### Ansible structure
Key playbooks:
- `ansible/playbooks/guests.yml` - main guest provisioning/config path
- `ansible/playbooks/validate.yml` and `validate_fast.yml` - validation passes
- `ansible/playbooks/remote-nodes.yml` - remote node work
- `ansible/playbooks/host.yml` - host-side work

Key roles relevant to day-to-day homelab work:
- `adguard`
- `nginx-proxy-manager`
- `nginx-proxy-manager-config`
- `heimdall`
- `authentik`
- `apt_cacher`
- `remote-node-baseline`
- `tailscale-router`
- `rr-staging-db-access`

### How to apply changes to live
Normal pattern:
- repo path: `/home/mrobinson/source/homelab`
- ansible path: `/home/mrobinson/source/homelab/ansible`
- vault password file: `/home/mrobinson/.ansible_vault_pass`
- roles path often needs to be set explicitly:
  - `ANSIBLE_ROLES_PATH=./roles`

Typical apply form:
```bash
cd /home/mrobinson/source/homelab/ansible
ANSIBLE_VAULT_PASSWORD_FILE=/home/mrobinson/.ansible_vault_pass \
ANSIBLE_ROLES_PATH=./roles \
ansible-playbook -i inventory.yml playbooks/guests.yml --limit 'host1,host2'
```

### Known playbook quirk
`guests.yml --limit 'adguard,nginx-proxy-manager,heimdall'` can get stuck or wander into unrelated NPM certificate work after the proxy-host role has already done the useful part. It also fails entirely without vault secrets because `nginx-proxy-manager` / `nginx-proxy-manager-config` need admin/API passwords.

Current proven workaround:
- use the full `guests.yml` path when secrets are available and you actually need NPM compose + proxy-host work
- if you only need a subset after the NPM proxy host already exists, use a narrow temporary playbook targeting only the needed roles, e.g. `adguard` + `heimdall`

This was used successfully on 2026-03-28 for Bazarr:
- broad NPM path created the live Bazarr proxy host
- narrow temp playbook then applied AdGuard + Heimdall cleanly

## Heimdall / Dashboard State

### Generation model
Heimdall entries are generated from internal NPM hosts plus configured extra items.

Relevant current behavior:
- generated links now point directly to app URLs, not `/tag/<url>`
- generated entries are pinned to the dashboard/home
- excluded apps such as Heimdall itself and CouchDB are kept out of the pinned homepage
- icons are generated deterministically

### Icon system
Current system is now config-driven plus role defaults.

Sources:
- role default slug map in `ansible/roles/heimdall/tasks/main.yml`
- optional overrides in `config.homelab.yaml`:
  - `config.heimdall.icon_slug_map`
  - `config.heimdall.icon_overrides`

As of `e616018` the role supports:
- normal walkxcode PNG icons from slug mapping
- config overrides for icon slug
- config overrides for custom icon URL
- config overrides for emoji icons

Emoji icons are implemented by generating an SVG asset in Heimdall storage containing the emoji.

### Current notable icon state
- Bazarr now uses walkxcode `bazarr.png`
- `Raffle Raptor Dev` and `Raffle Raptor Prod` use generated `🦖` SVG icons

### Current Heimdall DB snapshot
See live capture block below. Important current items:
- Bazarr pinned and present
- RR dev pinned and present
- RR prod pinned and present
- Heimdall and CouchDB unpinned as intended

## VM120 Media Stack

### Current storage layout after virtiofs migration
This was completed before this handoff.

#### VM disks
- `scsi0` only: root disk on `local-lvm`, `40G`, `backup=1`
- old giant `scsi1` bulk disk was removed after safe migration and delete

#### Current guest mount layout
- `/` on `/dev/sda1`
- `/srv/data/media` -> `tank-media` via `virtiofs`
- `/srv/data/downloads` -> `tank-downloads` via `virtiofs`
- `/srv/data` parent now lives on rootfs and only hosts the two virtiofs mountpoints
- `/opt/media-stack/appdata` remains on root disk

#### Host-owned datasets
- `tank/media`
- `tank/downloads`

#### Backup state
- `scsi0` root disk backed up via Proxmox vzdump
- bulk media/downloads are **not** backed up as VM disks anymore
- host datasets `tank/media` and `tank/downloads` are currently **not** part of any automated snapshot/replication schedule

### Proven container bind mounts on VM120
- `bazarr`: host port `6767`, config under `/opt/media-stack/appdata/bazarr`
- `jellyfin`: `/srv/data/media -> /media`, appdata under `/opt/media-stack/appdata/jellyfin`
- `plex`: `/srv/data/media -> /media`, appdata under `/opt/media-stack/appdata/plex`
- `sonarr`: `/srv/data -> /data`
- `radarr`: `/srv/data -> /data`
- `sabnzbd`: `/srv/data -> /data`
- `qbittorrent`: `/srv/data -> /data`
- `prowlarr`: appdata only
- `cleanuparr`: appdata only
- `gluetun`: network boundary, appdata only

### Ownership boundary for VM120
#### Homelab owns
- VM definition
- root disk
- host datasets
- virtiofs presentation into guest
- routing and DNS exposure
- backup policy

#### Media-stack owns
- app directory structure inside `/srv/data`
- app config under `/opt/media-stack/appdata/*`
- compose and app runtime behavior

## The Bazarr Issue - Immediate Open Problem
This is the thing Claude Code should pick up first if the user still reports browser failure.

### What is proven working right now
All of the following are currently proven live:
- direct app access:
  - `http://10.20.30.120:6767/` returns `200`
- NPM proxy host exists:
  - `bazarr.laxdog.uk -> 10.20.30.120:6767`
- AdGuard rewrite exists:
  - `bazarr.laxdog.uk -> 10.20.30.154`
- Bazarr internal TLS cert is valid:
  - live NPM cert `id=17` includes `bazarr.laxdog.uk` SAN
- verified HTTPS request without `-k` succeeds:
  - `curl --resolve bazarr.laxdog.uk:443:10.20.30.154 https://bazarr.laxdog.uk/` returns `200`
- curl from inside the NPM container to the backend succeeds:
  - `http://10.20.30.120:6767/ -> 200`
- Heimdall entry exists and is pinned

### What is not proven
As of this handoff, the browser-specific user complaint was **not** reproduced via CLI after the live apply. The following are still not proven:
- whether the user's browser is seeing a stale cert error
- whether the browser is hitting a different network/DNS path than the CLI checks
- whether Bazarr has an app-side reverse-proxy/host validation behavior that only triggers under real browser flow
- whether there is any app-level rejection after successful TLS + proxy transit

### Why this still matters
The user explicitly reported that `https://bazarr.laxdog.uk/` was not working in the browser even though direct backend access worked.
By the end of the latest work, the infra path is healthy from CLI:
- DNS good
- TLS good
- proxy good
- backend good

So if there is still a user-visible failure, it is likely one of:
1. stale browser state / cached bad cert perception
2. a browser hitting non-authoritative DNS
3. Bazarr app-side reverse proxy / host / base URL behavior under real browser requests

### SABnzbd precedent
A similar previous issue with SABnzbd was fixed by adding the proxied hostname to SAB's host whitelist in its config. That pattern is relevant here.

For Bazarr, the app config is under:
- `/opt/media-stack/appdata/bazarr`

Relevant files/directories:
- `/opt/media-stack/appdata/bazarr/config/config.yaml`
- `/opt/media-stack/appdata/bazarr/db/bazarr.db`
- `/opt/media-stack/appdata/bazarr/log/bazarr.log`

Current grep signals from Bazarr config:
- `base_url: ''`
- `auth:` section exists
- `proxy:` section exists
- `hostname: f5333de55ef5`
- several other URL/host settings exist

There is not yet proof of a Bazarr-specific host whitelist key, but it should be looked for the same way SAB was handled.

### What Claude Code should try first, in order
1. Reproduce the user's actual browser failure mode precisely.
   - cert warning?
   - blank page?
   - 502/504?
   - app error page?
2. Check NPM proxy logs during a real browser request for `bazarr.laxdog.uk`.
3. Verify the exact cert the browser sees with the user's actual resolver/network path.
4. Curl from inside the NPM container to `10.20.30.120:6767` again during reproduction.
5. Inspect Bazarr config in `/opt/media-stack/appdata/bazarr/config/config.yaml` for:
   - `base_url`
   - reverse proxy settings
   - auth settings
   - host validation / trusted hosts / equivalent allowlist behavior
6. Inspect `bazarr.log` during a browser request.
7. If the pattern matches SABnzbd, apply the narrow app-side host allowance on the media-stack side.

### Important current state for Bazarr
Current infra state is healthy enough that this is no longer a homelab routing/TLS design problem by default. Treat it as a browser-path or app-side reverse-proxy compatibility problem unless new evidence says otherwise.

## Other Known Open Items
- `adguard.lax.dog` exists live in NPM but is not in repo config.
  - unresolved whether intentional or drift
- `docs/authentik.md` is stale vs current internal router/unifi behavior
- Proxmox metadata drift exists for some VM/LXC tags/descriptions, including VM120 tags and Heimdall LXC metadata, but was not acted on
- `mums-house-mbp (10.20.30.75)` was unreachable during last pass; no fresh validation
- old Proxmox host `10.20.30.155` is powered off for move but not fully cleaned up/decommissioned in repo/docs

## Backlog

### NPM upstream healthcheck / retry on startup
When Proxmox restarts all guests (e.g. for hardware maintenance), NPM (CT154) comes up before backends are ready, causing brief 502 Bad Gateway responses on all proxied services. Observed during the 2026-04-08 SSD install — two full-estate stopall/startall cycles produced a 502 cascade on raffle-raptor-dev and other services for ~10 minutes until backends finished initialising.

NPM Pro supports upstream health checks but NPM open source does not natively. Options to investigate:
1. Custom nginx upstream health check config in NPM's advanced config per proxy host (e.g. `proxy_next_upstream` directives with retry)
2. A startup delay or ordering at the Proxmox level — delay NPM start by 30s after other LXCs are up (Proxmox `onboot` ordering + `startup=order=` with delay)
3. Replace NPM with Caddy or Traefik which have native upstream health checks and automatic retry logic

Priority: **low** — only affects planned restart windows, not steady-state operation. Mitigated by advance notice to service tenants before maintenance.

## Historical Context That Still Matters

### Major incidents
#### Duplicate AdGuard `.53`
- legacy old AdGuard and canonical CT153 both claimed/used `.53` across time
- caused bad DNS answers and management confusion
- canonical `.53` is now CT153 on `10.20.30.46`

#### Cloudflare wildcard fallback
- old public apex + wildcard sent unknown `*.laxdog.uk` to `10.20.30.175`
- removed already

#### Router stale cache
- router `dnsmasq` had stale/bad internal wildcard answers at one point
- secondary/historical problem now

### Major Heimdall fixes
Historical broken states:
- generated entries had `type=1` so links became `/tag/<url>` instead of opening apps
- icon field was being treated incorrectly so icons broke
- homepage pin state was lost so generated apps disappeared from dashboard
- dynamic favicon fetching produced low-quality tiny near-identical icons

Current fixed state:
- entries are app type and open direct URLs
- homepage pin state is restored
- deterministic icon mapping in place
- config-driven slug overrides and emoji icon overrides now supported (`e616018`)

### SABnzbd hostname verification fix
SAB previously failed behind internal proxy due hostname verification. That was fixed by narrow app-side config, not by redesigning NPM/AdGuard. This is the main analogy for any remaining Bazarr browser issue.

### apt-cacher state
- verified with live traffic
- applicable Debian/Ubuntu LXCs use apt-cacher
- apt-cacher itself intentionally does not self-proxy

### Remote node baseline / Tailscale
- remote-node baseline is repo-managed and active
- `raptor-node-staging` and `raffle-raptor-dev` both validated healthy in latest pass

### RR staging DB transport over Tailscale
- hosted on `raffle-raptor-dev`
- `rr-db-ts-proxy` and `rr-db-ts-firewall` active/enabled
- listener on Tailscale `100.92.43.108:5432`
- this is homelab infra transport, not RR app ownership

## Live State Capture

### Git state
```text
=== git status --short ===
??  .Destination}}{{end}}'
?? docs/batocera/batocera-crt1/vga-only-debug/20260327T121437Z-glxgears-current.png
?? scripts/__pycache__/

=== git branch --show-current ===
main

=== git rev-parse HEAD ===
e616018455cec1d96c23cd280462040ee165c056

=== git log --oneline -n 20 ===
e616018 Fix Bazarr access and Heimdall icon overrides
489556a Add internal Bazarr routing and dashboard entry
56cb8ef media-stack: finalize compose templates and jellyfin docs
5d694c0 media-stack: add bazarr and expand indexer configuration
a8a0d0b Route laxdog roots to Heimdall and finalize apt-cacher LXC remediation
4d77a44 Add RR prod Heimdall entry and close apt-cacher LXC audit
1e6aa42 Clean Heimdall entries and fix HA/SAB internal access
3281d5d Use service-mapped Heimdall icons for generated apps
3411542 Restore Heimdall generated apps on dashboard home
f8562e2 Fix Heimdall generated links and icon paths
333f388 Sync Batocera docs to current VGA baseline
0a76123 Reset Batocera to minimal VGA baseline
c2f5437 Manage Batocera VGA amdgpu dc workaround
dd6e5a8 Record Batocera libVLC suppression result
4fbbd04 Record Batocera DRI3 and TearFree isolation
7a66171 Record Batocera ES runtime source evidence
50f2a62 Record Batocera ES runtime isolation result
27ef94e media-stack: document auth-mode handoff to homelab
005d3a8 Record Batocera VGA GL isolation result
d93dc32 Record Batocera VGA renderer failure evidence
```

### Proxmox guest state
```text
=== qm list ===
      VMID NAME                 STATUS     MEM(MB)    BOOTDISK(GB) PID       
       120 media-stack          running    8192              40.00 1756443   
       122 home-assistant       running    4096              32.00 4006821   
       133 nagios               running    2048              16.00 1952      
       171 tailscale-gateway    running    1024              16.00 2070      

=== pct list ===
VMID       Status     Lock         Name                
128        running                 couchdb             
153        running                 adguard             
154        running                 nginx-proxy-manager 
156        running                 apt-cacher-ng       
157        running                 freshrss            
158        running                 netalertx           
159        running                 healthchecks        
160        running                 dashboard           
161        running                 static-sites        
162        running                 browser             
163        running                 raffle-raptor-dev   
164        running                 organizr            
166        running                 heimdall            
170        running                 authentik           
```

### `qm config 120`
```text
acpi: 1
agent: enabled=0,fstrim_cloned_disks=0,type=virtio
balloon: 0
bios: seabios
boot: order=scsi0;net0
citype: nocloud
ciuser: ubuntu
cores: 4
cpu: x86-64-v2-AES
description: managed_by=scripts/proxmox_metadata.py;service=media-stack;kind=qemu;ip=10.20.30.120;access=internal,external;oidc=no;domains=jellyfin.lax.dog,jellyfin.laxdog.uk;creds=ui%3Aadmin|jellyfin_admin_password,ssh%3Aroot|root_password
hostpci0: 0000:00:02.0
ide2: local-lvm:vm-120-cloudinit,media=cdrom
ipconfig0: gw=10.20.30.1,ip=10.20.30.120/24
keyboard: en-us
memory: 8192
meta: creation-qemu=10.1.2,ctime=1773966572
name: media-stack
net0: virtio=BC:24:11:62:80:00,bridge=vmbr0,firewall=0
numa: 0
onboot: 1
ostype: l26
protection: 0
scsi0: local-lvm:vm-120-disk-0,aio=io_uring,backup=1,cache=none,discard=ignore,iothread=0,replicate=1,size=40G,ssd=0
scsihw: virtio-scsi-pci
smbios1: uuid=1efbae13-804d-4c1e-8bbc-47049f0ab27c
sockets: 1
sshkeys: ssh-rsa%20AAAAB3NzaC1yc2EAAAADAQABAAABgQCY5wqAy1dFFT5MbHXscJBLzz2le%2FaP9J5ofj9%2FlYcfl7xJ1PPdO%2FSNBLeMml%2Bi7GgQvi7MjFLOqzBEqTDj0SB6%2BS7B0gZCBpi%2FawkgVKTYuREjLwLm35Dyh8AoHjh2%2F2OHxmiwNuIhQ3G2wqer3tCaNrZg6ILdowOirUHJrhnYpREz%2B9Zlp7ot8dwHdeeVi5ylv0EDTCWzT0M%2BcwMYVqZ8%2BTdi166siBw8MQume4R4izDWjZsrWu6YIA8SXYfr%2Bif9GcZpzd%2BmilGlqg3YkDzZOXEd5gnu3n59gFLscGMKNW%2FxQASPsMDoQjhtd%2BK%2F%2Bp67h8i8jYQwqdskNmz58mWOXh9uPmTO5RBmFmKfMdUohoG1FukfR1LriLaNUUJg3XkX5eHRODhFJAbEcXInZBjLQ9xWiT8iHTGv2LTwmWf4R1p1fn8%2FVSQnWVTsN3l%2B4ykFS0tEIroS6YaCDUHT9BaY0KKhcfjeUn2TZjlQOvWjQTM36k%2FRBNQzaFVJ2kg7IT0%3D%20mrobinson%40plex-poo
startup: order=3
tablet: 1
tags: lax.dog;laxdog.uk;terraform
template: 0
virtiofs0: tank-media,cache=metadata
virtiofs1: tank-downloads,cache=metadata
vmgenid: 49d6e92d-d529-4182-9289-b196f9656c98
```

### VM120 `findmnt`
```text
TARGET                                                                                              SOURCE                 FSTYPE      OPTIONS
/                                                                                                   /dev/sda1              ext4        rw,relatime,discard,errors=remount-ro,commit=30
...
├─/srv/data/downloads                                                                               tank-downloads         virtiofs    rw,relatime
├─/srv/data/media                                                                                   tank-media             virtiofs    rw,relatime
├─/boot                                                                                             /dev/sda16             ext4        rw,relatime
│ └─/boot/efi                                                                                       /dev/sda15             vfat        rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=iso8859-1,shortname=mixed,errors=remount-ro
...
```

### VM120 `/etc/fstab`
```text
LABEL=cloudimg-rootfs	/	 ext4	discard,commit=30,errors=remount-ro	0 1
LABEL=BOOT	/boot	ext4	defaults	0 2
LABEL=UEFI	/boot/efi	vfat	umask=0077	0 1
tank-media /srv/data/media virtiofs defaults,nofail 0 0
tank-downloads /srv/data/downloads virtiofs defaults,nofail 0 0
```

### VM120 `docker ps`
```text
CONTAINER ID   IMAGE                                    COMMAND                  CREATED       STATUS                 PORTS                                                                                                                                                                 NAMES
f5333de55ef5   lscr.io/linuxserver/bazarr:latest        "/init"                  6 hours ago   Up 2 hours             0.0.0.0:6767->6767/tcp, [::]:6767->6767/tcp                                                                                                                           bazarr
df787840bf3a   lscr.io/linuxserver/prowlarr:latest      "/init"                  6 days ago    Up 2 hours             0.0.0.0:9696->9696/tcp, [::]:9696->9696/tcp                                                                                                                           prowlarr
91ea2145641c   lscr.io/linuxserver/qbittorrent:latest   "/init"                  6 days ago    Up 2 hours                                                                                                                                                                                   qbittorrent
9f5c2c39e709   lscr.io/linuxserver/sabnzbd:latest       "/init"                  6 days ago    Up 2 hours                                                                                                                                                                                   sabnzbd
ffb644620ebe   qmcgaw/gluetun:latest                    "/gluetun-entrypoint"    6 days ago    Up 2 hours (healthy)   0.0.0.0:6789->6789/tcp, [::]:6789->6789/tcp, 0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp, 8388/tcp, 0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp, 8888/tcp, 8388/udp   gluetun
e67dcbc3951e   ghcr.io/cleanuparr/cleanuparr:latest     "/entrypoint.sh ./Cl…"   6 days ago    Up 2 hours             0.0.0.0:11011->11011/tcp, [::]:11011->11011/tcp                                                                                                                       cleanuparr
1f7bf6f858ae   lscr.io/linuxserver/sonarr:latest        "/init"                  6 days ago    Up 2 hours             0.0.0.0:8989->8989/tcp, [::]:8989->8989/tcp                                                                                                                           sonarr
102adddd4dec   lscr.io/linuxserver/radarr:latest        "/init"                  6 days ago    Up 2 hours             0.0.0.0:7878->7878/tcp, [::]:7878->7878/tcp                                                                                                                           radarr
21392cd08200   lscr.io/linuxserver/plex:latest          "/init"                  6 days ago    Up 2 hours             1900/udp, 5353/udp, 32410/udp, 8324/tcp, 32412-32414/udp, 32469/tcp, 0.0.0.0:32400->32400/tcp, [::]:32400->32400/tcp                                                  plex
35f4f7c90e0c   jellyfin/jellyfin:latest                 "/jellyfin/jellyfin"     6 days ago    Up 2 hours (healthy)   0.0.0.0:8096->8096/tcp, [::]:8096->8096/tcp                                                                                                                           jellyfin
```

### `zpool list` and `zfs list`
```text
=== zpool list ===
NAME   SIZE  ALLOC   FREE  CKPOINT  EXPANDSZ   FRAG    CAP  DEDUP    HEALTH  ALTROOT
tank  27.3T   870G  26.4T        -         -     0%     3%  1.00x    ONLINE  -

=== zfs list ===
NAME             USED  AVAIL  REFER  MOUNTPOINT
tank             579G  17.5T   202K  /tank
tank/backups     530G  17.5T   530G  /tank/backups
tank/downloads  4.87G  17.5T  4.87G  /tank/downloads
tank/media      42.6G  17.5T  42.6G  /tank/media
tank/personal    128K  17.5T   128K  /tank/personal
tank/scratch     128K  17.5T   128K  /tank/scratch
tank/templates  1.79G  17.5T  1.79G  /tank/templates
```

### Live NPM proxy host DB rows
```text
=== active NPM proxy hosts ===
["adguard.lax.dog"] | 10.20.30.153 | 80 | access_list_id=1 | cert_id=0
["apt.laxdog.uk"] | 10.20.30.156 | 3142 | access_list_id=2 | cert_id=17
["auth.lax.dog"] | 10.20.30.170 | 9000 | access_list_id=4 | cert_id=16
["auth.laxdog.uk"] | 10.20.30.170 | 9000 | access_list_id=2 | cert_id=17
["bazarr.laxdog.uk"] | 10.20.30.120 | 6767 | access_list_id=2 | cert_id=17
["browser.laxdog.uk"] | 10.20.30.162 | 5800 | access_list_id=2 | cert_id=17
["cleanuparr.lax.dog"] | 10.20.30.120 | 11011 | access_list_id=4 | cert_id=16
["cleanuparr.laxdog.uk"] | 10.20.30.120 | 11011 | access_list_id=2 | cert_id=17
["couchdb.lax.dog"] | 10.20.30.128 | 5984 | access_list_id=4 | cert_id=16
["couchdb.laxdog.uk"] | 10.20.30.128 | 5984 | access_list_id=2 | cert_id=17
["dns.laxdog.uk"] | 10.20.30.53 | 80 | access_list_id=2 | cert_id=17
["ha.lax.dog"] | 10.20.30.134 | 8123 | access_list_id=4 | cert_id=16
["ha.laxdog.uk"] | 10.20.30.134 | 8123 | access_list_id=2 | cert_id=17
["health.laxdog.uk"] | 10.20.30.159 | 8000 | access_list_id=2 | cert_id=17
["heimdall.laxdog.uk"] | 10.20.30.166 | 80 | access_list_id=2 | cert_id=17
["jellyfin.lax.dog"] | 10.20.30.120 | 8096 | access_list_id=4 | cert_id=16
["jellyfin.laxdog.uk"] | 10.20.30.120 | 8096 | access_list_id=2 | cert_id=17
["lax.dog"] | 10.20.30.166 | 80 | access_list_id=4 | cert_id=16
["laxdog.uk"] | 10.20.30.166 | 80 | access_list_id=2 | cert_id=17
["nagios.lax.dog"] | 10.20.30.133 | 80 | access_list_id=4 | cert_id=16
["nagios.laxdog.uk"] | 10.20.30.133 | 80 | access_list_id=2 | cert_id=17
["netalertx.lax.dog"] | 10.20.30.158 | 20211 | access_list_id=4 | cert_id=16
["netalertx.laxdog.uk"] | 10.20.30.158 | 20211 | access_list_id=2 | cert_id=17
["npm.laxdog.uk"] | 127.0.0.1 | 81 | access_list_id=2 | cert_id=17
["organizr.laxdog.uk"] | 10.20.30.164 | 80 | access_list_id=2 | cert_id=17
["plex.lax.dog"] | 10.20.30.120 | 32400 | access_list_id=4 | cert_id=16
["plex.laxdog.uk"] | 10.20.30.120 | 32400 | access_list_id=2 | cert_id=17
["prowlarr.lax.dog"] | 10.20.30.120 | 9696 | access_list_id=4 | cert_id=16
["prowlarr.laxdog.uk"] | 10.20.30.120 | 9696 | access_list_id=2 | cert_id=17
["proxmox.lax.dog"] | 10.20.30.46 | 8006 | access_list_id=4 | cert_id=16
["proxmox.laxdog.uk"] | 10.20.30.46 | 8006 | access_list_id=2 | cert_id=17
["qbittorrent.lax.dog"] | 10.20.30.120 | 8080 | access_list_id=4 | cert_id=16
["qbittorrent.laxdog.uk"] | 10.20.30.120 | 8080 | access_list_id=2 | cert_id=17
["radarr.lax.dog"] | 10.20.30.120 | 7878 | access_list_id=4 | cert_id=16
["radarr.laxdog.uk"] | 10.20.30.120 | 7878 | access_list_id=2 | cert_id=17
["raffle-raptor-dev.lax.dog"] | 10.20.30.163 | 8081 | access_list_id=4 | cert_id=16
["raffle-raptor-dev.laxdog.uk"] | 10.20.30.163 | 8081 | access_list_id=2 | cert_id=17
["router.laxdog.uk"] | 10.20.30.1 | 80 | access_list_id=2 | cert_id=17
["rss.laxdog.uk"] | 10.20.30.157 | 80 | access_list_id=2 | cert_id=17
["sabnzbd.lax.dog"] | 10.20.30.120 | 6789 | access_list_id=4 | cert_id=16
["sabnzbd.laxdog.uk"] | 10.20.30.120 | 6789 | access_list_id=2 | cert_id=17
["sites.laxdog.uk"] | 10.20.30.161 | 80 | access_list_id=2 | cert_id=17
["sonarr.lax.dog"] | 10.20.30.120 | 8989 | access_list_id=4 | cert_id=16
["sonarr.laxdog.uk"] | 10.20.30.120 | 8989 | access_list_id=2 | cert_id=17
["unifi-primary.laxdog.uk"] | 10.20.30.50 | 80 | access_list_id=2 | cert_id=17
["unifi-secondary.laxdog.uk"] | 10.20.30.51 | 443 | access_list_id=2 | cert_id=17

=== Bazarr NPM host row ===
["bazarr.laxdog.uk"] | 10.20.30.120 | 6767 | access_list_id=2 | cert_id=17 | ssl_forced=1 | http2_support=1 | hsts_enabled=0
```

### Relevant AdGuard rewrites
```text
=== AdGuard rewrite lines ===
203:    - domain: dns.laxdog.uk
206:    - domain: npm.laxdog.uk
209:    - domain: proxmox.laxdog.uk
212:    - domain: organizr.laxdog.uk
215:    - domain: heimdall.laxdog.uk
218:    - domain: rss.laxdog.uk
221:    - domain: netalertx.laxdog.uk
224:    - domain: health.laxdog.uk
227:    - domain: couchdb.laxdog.uk
230:    - domain: browser.laxdog.uk
233:    - domain: apt.laxdog.uk
236:    - domain: sites.laxdog.uk
239:    - domain: auth.laxdog.uk
242:    - domain: ha.laxdog.uk
245:    - domain: nagios.laxdog.uk
248:    - domain: jellyfin.laxdog.uk
251:    - domain: router.laxdog.uk
254:    - domain: unifi-primary.laxdog.uk
257:    - domain: unifi-secondary.laxdog.uk
260:    - domain: raffle-raptor-dev.laxdog.uk
263:    - domain: plex.laxdog.uk
266:    - domain: prowlarr.laxdog.uk
269:    - domain: sonarr.laxdog.uk
272:    - domain: radarr.laxdog.uk
275:    - domain: cleanuparr.laxdog.uk
278:    - domain: sabnzbd.laxdog.uk
281:    - domain: qbittorrent.laxdog.uk
284:    - domain: laxdog.uk
287:    - domain: bazarr.laxdog.uk
```

### Heimdall DB current state
```text
=== Heimdall DB current state ===
app.dashboard|||0|0
AdGuard Internal|https://dns.laxdog.uk|icons/dns.laxdog.uk.png|1|1
NPM|https://npm.laxdog.uk|icons/npm.laxdog.uk.png|1|2
Proxmox|https://proxmox.laxdog.uk|icons/proxmox.laxdog.uk.png|1|3
Organizr|https://organizr.laxdog.uk|icons/organizr.laxdog.uk.png|1|4
Heimdall|https://heimdall.laxdog.uk|icons/heimdall.laxdog.uk.png|0|5
FreshRSS|https://rss.laxdog.uk|icons/rss.laxdog.uk.png|1|6
NetAlertX|https://netalertx.laxdog.uk|icons/netalertx.laxdog.uk.png|1|7
Healthchecks|https://health.laxdog.uk|icons/health.laxdog.uk.png|1|8
CouchDB|https://couchdb.laxdog.uk|icons/couchdb.laxdog.uk.png|0|9
Firefox|https://browser.laxdog.uk|icons/browser.laxdog.uk.png|1|10
Apt Cacher|https://apt.laxdog.uk|icons/apt.laxdog.uk.png|1|11
Static Sites Internal|https://sites.laxdog.uk|icons/sites.laxdog.uk.png|0|12
Authentik Internal|https://auth.laxdog.uk|icons/auth.laxdog.uk.png|1|13
Home Assistant|https://ha.laxdog.uk|icons/ha.laxdog.uk.png|1|14
Nagios|https://nagios.laxdog.uk|icons/nagios.laxdog.uk.png|1|15
Jellyfin|https://jellyfin.laxdog.uk|icons/jellyfin.laxdog.uk.png|1|16
Router|https://router.laxdog.uk|icons/router.laxdog.uk.png|1|17
Plex|https://plex.laxdog.uk|icons/plex.laxdog.uk.png|1|17
Liberty|https://unifi-primary.laxdog.uk|icons/unifi-primary.laxdog.uk.png|1|18
Prowlarr|https://prowlarr.laxdog.uk|icons/prowlarr.laxdog.uk.png|1|18
Bazarr|https://bazarr.laxdog.uk|icons/bazarr.laxdog.uk.png|1|18
Ellis|https://unifi-secondary.laxdog.uk|icons/unifi-secondary.laxdog.uk.png|1|19
Sonarr|https://sonarr.laxdog.uk|icons/sonarr.laxdog.uk.png|1|19
Raffle Raptor Dev|https://raffle-raptor-dev.laxdog.uk|icons/raffle-raptor-dev.laxdog.uk.svg|1|20
Radarr|https://radarr.laxdog.uk|icons/radarr.laxdog.uk.png|1|20
Cleanuparr|https://cleanuparr.laxdog.uk|icons/cleanuparr.laxdog.uk.png|1|21
SABnzbd|https://sabnzbd.laxdog.uk|icons/sabnzbd.laxdog.uk.png|1|22
qBittorrent|https://qbittorrent.laxdog.uk|icons/qbittorrent.laxdog.uk.png|1|23
Raffle Raptor Prod|https://raffle-raptor.lax.dog|icons/raffle-raptor.lax.dog.svg|1|25
Heimdall Root|https://laxdog.uk|icons/laxdog.uk.png|1|26
```

### Bazarr appdata directory
```text
=== ls /opt/media-stack/appdata/bazarr ===
total 32
drwxrwxr-x  8 ubuntu ubuntu 4096 Mar 28 14:00 .
drwxr-xr-x 13 root   root   4096 Mar 28 13:59 ..
drwxr-xr-x  2 ubuntu ubuntu 4096 Mar 28 14:00 backup
drwxr-xr-x  2 ubuntu ubuntu 4096 Mar 28 14:00 cache
drwxr-xr-x  2 ubuntu ubuntu 4096 Mar 28 17:52 config
drwxr-xr-x  2 ubuntu ubuntu 4096 Mar 28 18:36 db
drwxr-xr-x  2 ubuntu ubuntu 4096 Mar 28 14:00 log
drwxr-xr-x  2 ubuntu ubuntu 4096 Mar 28 14:00 restore
```

Additional Bazarr config signals:
```text
=== bazarr appdata tree ===
/opt/media-stack/appdata/bazarr/config/analytics_visitor_id.txt
/opt/media-stack/appdata/bazarr/config/announcements.json
/opt/media-stack/appdata/bazarr/config/config.yaml
/opt/media-stack/appdata/bazarr/config/releases.txt
/opt/media-stack/appdata/bazarr/db/bazarr.db
/opt/media-stack/appdata/bazarr/log/bazarr.log

=== bazarr config grep ===
/opt/media-stack/appdata/bazarr/config/config.yaml:21:auth:
/opt/media-stack/appdata/bazarr/config/config.yaml:57:  base_url: ''
/opt/media-stack/appdata/bazarr/config/config.yaml:76:  external_webhook_url: ''
/opt/media-stack/appdata/bazarr/config/config.yaml:80:  hostname: f5333de55ef5
/opt/media-stack/appdata/bazarr/config/config.yaml:167:  only_authors: false
/opt/media-stack/appdata/bazarr/config/config.yaml:180:  auth_method: apikey
/opt/media-stack/appdata/bazarr/config/config.yaml:197:  server_url: ''
/opt/media-stack/appdata/bazarr/config/config.yaml:211:  host: localhost
/opt/media-stack/appdata/bazarr/config/config.yaml:214:  url: ''
/opt/media-stack/appdata/bazarr/config/config.yaml:216:proxy:
/opt/media-stack/appdata/bazarr/config/config.yaml:218:  - localhost
/opt/media-stack/appdata/bazarr/config/config.yaml:223:  url: ''
/opt/media-stack/appdata/bazarr/config/config.yaml:227:  base_url: ''
/opt/media-stack/appdata/bazarr/config/config.yaml:257:  base_url: ''
/opt/media-stack/appdata/bazarr/config/config.yaml:311:  lingarr_url: http://lingarr:9876
```

### Bazarr DNS + curl checks
```text
=== dig bazarr.laxdog.uk @10.20.30.53 ===

; <<>> DiG 9.18.30-0ubuntu0.20.04.2+esm1-Ubuntu <<>> @10.20.30.53 bazarr.laxdog.uk
; (1 server found)
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 40446
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;bazarr.laxdog.uk.		IN	A

;; ANSWER SECTION:
bazarr.laxdog.uk.	10	IN	A	10.20.30.154

;; Query time: 4 msec
;; SERVER: 10.20.30.53#53(10.20.30.53) (UDP)
;; WHEN: Sat Mar 28 20:19:44 GMT 2026
;; MSG SIZE  rcvd: 50

=== curl bazarr with -k ===
HTTP/2 200 
server: openresty
date: Sat, 28 Mar 2026 20:19:44 GMT
content-type: text/html; charset=utf-8
content-length: 1897
access-control-allow-origin: *
vary: Accept-Encoding
x-served-by: bazarr.laxdog.uk

=== curl bazarr without -k ===
HTTP/2 200 
server: openresty
date: Sat, 28 Mar 2026 20:19:44 GMT
content-type: text/html; charset=utf-8
content-length: 1897
access-control-allow-origin: *
vary: Accept-Encoding
x-served-by: bazarr.laxdog.uk
```

### Bazarr TLS verification detail
```text
* SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384
* ALPN, server accepted to use h2
* Server certificate:
*  subject: CN=apt.laxdog.uk
*  start date: Mar 28 18:50:48 2026 GMT
*  expire date: Jun 26 18:50:47 2026 GMT
*  subjectAltName: host "bazarr.laxdog.uk" matched cert's "bazarr.laxdog.uk"
*  issuer: C=US; O=Let's Encrypt; CN=E8
```

### Router identity / DNS stack
```text
=== router identity ===
sh: hostname: not found
Linux RT-AC86U 4.1.27 #2 SMP PREEMPT Thu Oct 23 13:37:08 UTC 2025 aarch64
 20:20:24 up 78 days,  6:25,  load average: 2.55, 2.45, 2.44

=== dns process ===
23821 nobody    2524 S    dnsmasq --log-async
23822 admin     2392 S    dnsmasq --log-async
```

### Tailscale / remote node state
```text
=== 10.20.30.153 ===
raptor-node-staging
Running raptor-node-staging.tailb63b4.ts.net. ['100.88.35.124', 'fd7a:115c:a1e0::7b34:237c'] True None
=== 10.20.30.163 ===
raffle-raptor-dev
Running raffle-raptor-dev.tailb63b4.ts.net. ['100.92.43.108', 'fd7a:115c:a1e0::b034:2b6c'] False None
=== 10.20.30.75 ===
ssh: connect to host 10.20.30.75 port 22: No route to host
unreachable

=== rr staging transport ===
active
active
active
enabled
enabled
enabled
LISTEN 0      5                    100.92.43.108:5432       0.0.0.0:*    users:(("socat",pid=630001,fd=5))
```

## Immediate Operating Guidance For Claude Code
- Start with the Bazarr browser-path issue if the user still sees it.
- Assume infra path is now healthy until disproven.
- Use authoritative DNS checks against `@10.20.30.53`, not the router.
- Use SNI-correct HTTPS validation against `10.20.30.154` when checking internal routes.
- Keep commits narrow.
- Do not push.
- If a problem proves app-side (Bazarr config, media app policy, indexers, content behavior), stop at the homelab/media-stack boundary and hand it back cleanly.
