# Batocera HP 705 G3 VGA Baseline

This is the active source of truth for `batocera-crt1`.

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
- host vars: `ansible/host_vars/batocera-crt1.yml`

Current proven host-specific fact:
- on this hardware/VGA path, stock Batocera can fail after splash with AMDGPU Display Core timeouts
- `amdgpu.dc=0` removes the critical timeout signature and yields a rendered VGA framebuffer

Minimal rebuild target:
1. Install stock Batocera cleanly on the box.
2. Boot on a VGA monitor only.
3. Apply `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_vga_safe`
4. Reboot.
5. Verify the UI is visibly working on VGA.

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

Clean rebuild procedure for this exact box:
1. Write a fresh Batocera image to the target disk or replacement media.
2. Boot the HP EliteDesk 705 G3 with a VGA monitor only.
3. Confirm the box is reachable over SSH.
4. Run:
   - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_baseline`
   - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_vga_safe`
5. Reboot.
6. Verify:
   - `/proc/cmdline` contains `amdgpu.dc=0`
   - the Batocera UI is visible on VGA
   - no extra display forcing files were reintroduced

Rollback:
- remove `amdgpu.dc=0` from `ansible/host_vars/batocera-crt1.yml`
- re-run `--tags batocera_vga_safe`
- reboot

Historical investigation:
- previous Batocera investigation artifacts are preserved under `docs/batocera/batocera-crt1/`
- they are archival evidence, not active configuration guidance
- see `docs/batocera/batocera-crt1/HISTORICAL.md`
