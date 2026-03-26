# Batocera CRT 1

Host:
- inventory: `batocera-crt1`
- address: `10.20.30.206`
- platform: HP 705 G3 running Batocera v42

Wiring:
- GPU analog path target: `DP -> VGA DAC -> UMSA -> SCART -> CRT TV`
- temporary recovery display: HDMI monitor

Safety rule:
- Keep the CRT powered off, or on another input, during BIOS and early Batocera boot.
- Early boot can emit non-15kHz-safe timings before the CRT-specific config takes over.

Repo-managed scope:
- playbook: `ansible/playbooks/batocera.yml`
- baseline role: `ansible/roles/batocera_baseline`
- VGA-safe reset role: `ansible/roles/batocera_vga_safe`
- CRT script installer role: `ansible/roles/batocera_crt_script`
- CRT config role: `ansible/roles/batocera_crt_config`
- host vars: `ansible/host_vars/batocera-crt1.yml`

Current defaults:
- monitor profile: `arcade_15`
- fallback profile: `generic_15`
- UI base resolution target: `768x576`
- finalize output mode: `hybrid`
- hybrid HDMI-safe resolution target: `max-1920x1080`
- connector candidates:
  - `card0-DP-1`
  - `card0-DP-2`

Apply commands:
- baseline only:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_baseline`
- reset the box to the proven minimal VGA-safe state:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_vga_safe`
  - removes forced `global.videooutput` and `es.resolution`
  - removes `/etc/X11/xorg.conf.d/10-monitor.conf`, `/etc/switchres.ini`, `/userdata/system/videomodes.conf`, `/userdata/system/custom-es-config`, and `/userdata/system/custom.sh`
  - reboot after applying it
- install CRT script + stage config without switching away from HDMI:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_crt`
  - default staged state is now HDMI-safe hybrid, not global CRT timing activation
- run the full Batocera playbook through the repo runner:
  - `python3 scripts/run.py batocera`
- finalize CRT connector selection after the VGA -> UMSA -> SCART chain is connected:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_crt -e batocera_crt_apply_mode=finalize`
- force intentional CRT-only behavior after you have positively validated the CRT path:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_crt -e batocera_crt_apply_mode=finalize -e batocera_crt_output_mode=crt_only`
- run the test task:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_crt_test -e batocera_crt_apply_mode=finalize`
  - purpose: expose `DP-1` to X while keeping HDMI as the safe preferred output
  - after applying it, reboot or reliably restart X/EmulationStation, then use `DISPLAY=:0.0 xrandr -q`

Rollback:
- restore HDMI-first monitor config:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_crt_recovery`
- after `batocera_crt_recovery`, reboot the box before judging success.
- a reliable X/EmulationStation restart may also work, but reboot is the expected operator path.

Operational flow:
1. For VGA-only troubleshooting or before future CRT work, start with `--tags batocera_vga_safe` and reboot. That returns the box to the clean display state that proved stable in overnight testing.
2. Run baseline while HDMI is attached and archive the collected facts under `docs/batocera/batocera-crt1/baseline/`.
3. Run the CRT playbook in default `stage` mode. This installs the pinned Batocera-CRT-Script tree and keeps the box in an HDMI-safe hybrid state without installing global CRT timing files.
4. After the physical CRT chain is connected, rerun with `-e batocera_crt_apply_mode=finalize`. The default finalize path is `hybrid`: it keeps HDMI available as a recovery output while also enabling the CRT candidate connector.
5. In `hybrid` and `batocera_crt_test`, the role now avoids installing global CRT timing files. This is intentional: “HDMI enabled” is not sufficient if HDMI is still being driven with CRT-safe timings.
6. Do not treat DRM or XRandR `connected` state as proof that the CRT path is good. On this host, `DP-1` can appear connected even while the user still needs HDMI recovery.
7. Use `DISPLAY=:0.0 xrandr -q` for PC-display-side testing. Do not rely on `batocera-resolution listOutputs` as the only live test path.
8. `crt_only` is explicit and higher risk. That is the mode that applies the global CRT timing files. If CRT sync fails in that mode, the box can still end up headless until you recover over SSH and reboot back into HDMI-first config.
9. If video recovery is needed, rerun with `--tags batocera_crt_recovery`, then reboot before judging the result.

VGA-only findings from 2026-03-26:
- Earlier Batocera/Ansible display forcing left the box in a bad state:
  - stale `global.videooutput=DP-1`
  - stale `es.resolution=640x480`
  - stale `/boot/batocera-boot.conf` `es.resolution=640x480`
- With those removed, Batocera booted back into a single clean `:0` X session on `DP-1` with:
  - `openbox` running
  - `emulationstation` running
  - no `Invalid output: DP-1` lines in `display.log`
  - no active `10-monitor.conf`
  - no active global CRT timing files
- In that state, `DISPLAY=:0 xset q` succeeds from SSH, but `DISPLAY=:0 xrandr -q` and `DISPLAY=:0 batocera-resolution listOutputs` still hang. Treat visual confirmation as still pending.
- This is the current best-known starting point for future work. It is likely working on VGA, but not visually confirmed from SSH alone.
- Post-reset debug artifacts are archived under:
  - `docs/batocera/batocera-crt1/vga-only-debug/20260326T003745Z-pre-minimal-reset/`
  - `docs/batocera/batocera-crt1/vga-only-debug/20260326T0141Z-post-minimal-reset/`
