# Batocera HP 705 G3 VGA Baseline

This is the active source of truth for `batocera-crt1`.

Current operating mode:
- we are continuing from the current installed Batocera system
- a fresh reinstall is desirable in theory, but it is not required to proceed
- if USB boot or install media is unavailable, the current install is acceptable as long as the active baseline is applied and documented

Current target state:
- stock Batocera on the HP EliteDesk 705 G3
- VGA monitor only
- no HDMI-specific forcing
- no CRT/UMSA/SCART config
- one host-specific workaround only: `amdgpu.dc=0`

Active managed repo scope:
- playbook: `ansible/playbooks/batocera.yml`
- baseline facts role: `ansible/roles/batocera_baseline`
- VGA baseline role: `ansible/roles/batocera_vga_safe`
- VGA-safe role defaults: `ansible/roles/batocera_vga_safe/defaults/main.yml`
- host vars: `ansible/host_vars/batocera-crt1.yml`

Current proven host-specific fact:
- on this hardware/VGA path, stock Batocera can fail after splash with AMDGPU Display Core timeouts
- `amdgpu.dc=0` removes the critical timeout signature and yields a rendered VGA framebuffer

Minimal rebuild target:
1. Use stock Batocera.
2. Ensure `amdgpu.dc=0` is present through the active baseline role.
3. Validate on a VGA monitor.
4. Do not apply CRT/UMSA-specific config yet.

What `batocera_vga_safe` is allowed to manage:
- remove stale `global.videooutput` and `es.resolution`
- remove stale boot-time `es.resolution`
- remove stale display override files:
  - `/etc/X11/xorg.conf.d/10-monitor.conf`
  - `/etc/switchres.ini`
  - `/userdata/system/videomodes.conf`
  - `/userdata/system/videomodes.conf.bak`
  - `/userdata/system/custom-es-config`
  - `/userdata/system/custom.sh`
- ensure the default Batocera boot entry includes the host-scoped kernel arg `amdgpu.dc=0`

What is intentionally not part of the active baseline:
- CRT script installation
- Switchres configuration
- `videomodes.conf`
- `10-monitor.conf`
- output forcing
- hybrid/finalize/recovery logic
- UMSA/SCART/CRT setup
- EmulationStation theme/runtime hacks

Do not do this yet:
- do not re-enable CRT script logic in the active baseline
- do not reintroduce `/etc/switchres.ini`, `/userdata/system/videomodes.conf`, or `/etc/X11/xorg.conf.d/10-monitor.conf`
- do not treat old CRT investigation steps as current setup instructions
- do not remove `amdgpu.dc=0` for this host unless deliberately testing rollback

Clean rebuild procedure for this exact box:
1. Fresh Batocera install is preferred if convenient, but not mandatory.
2. If doing a fresh install:
   - initial install and first boot may be done on HDMI
   - once reachable over SSH, run:
     - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_baseline`
     - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_vga_safe`
   - reboot
   - switch to VGA-only validation
3. If continuing from the current install:
   - run:
     - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_baseline`
     - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_vga_safe`
   - reboot if needed
4. For either path, verify:
   - `/proc/cmdline` contains `amdgpu.dc=0`
   - the Batocera UI is visible on VGA
   - no extra display forcing files were reintroduced
5. Do not start CRT/UMSA work before that VGA baseline is confirmed.

Current install procedure:
- because USB boot/install media is not cooperating right now, the current installed system is the active working base
- use the same baseline flow on the current install:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_baseline`
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_vga_safe`
- then verify the same VGA-only conditions above

Rollback:
- remove `amdgpu.dc=0` from `ansible/host_vars/batocera-crt1.yml`
- re-run `--tags batocera_vga_safe`
- reboot

Historical investigation:
- previous Batocera investigation artifacts are preserved under `docs/batocera/batocera-crt1/`
- they are archival evidence, not active configuration guidance
- see `docs/batocera/batocera-crt1/HISTORICAL.md`
