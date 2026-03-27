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
- VGA-only kernel workaround on this host: `amdgpu.dc=0`
- connector candidates:
  - `card0-DP-1`
  - `card0-DP-2`

Apply commands:
- baseline only:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_baseline`
- reset the box to the proven minimal VGA-safe state:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_vga_safe`
  - removes forced `global.videooutput` and `es.resolution`
  - ensures the default Batocera boot entry contains the host-scoped VGA workaround kernel arg `amdgpu.dc=0`
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

Visual-proxy findings from 2026-03-26:
- A direct X screenshot was captured from `DISPLAY=:0` with `ffmpeg -f x11grab` and archived at:
  - `docs/batocera/batocera-crt1/vga-only-debug/20260326T015347Z-visual-proxy/frame0.png`
- That screenshot shows a fully black frame with only the mouse cursor visible.
- Additional captures before and after killing the visible `emulationstation` PID remained visually identical:
  - `docs/batocera/batocera-crt1/vga-only-debug/20260326T015347Z-visual-proxy/compare/before.png`
  - `docs/batocera/batocera-crt1/vga-only-debug/20260326T015347Z-visual-proxy/compare/after_kill.png`
- This proves the X session is not rendering the Batocera UI to the captured `:0` framebuffer. The visible output from X at capture time was black, not a hidden but healthy UI.
- The running `emulationstation` process still had SDL2, Mesa/GL, and image/theme libraries mapped, but its `es_log.txt` remained empty.
- A temporary stock-wrapper experiment removing `--windowed` from `/usr/bin/emulationstation-standalone` did not produce a usable session and triggered a bad restart path instead. That experiment was reverted. Logs are archived under:
  - `docs/batocera/batocera-crt1/vga-only-debug/20260326T015347Z-visual-proxy/wrapper-test/`
- Strongest current hypothesis:
  - Batocera is launching EmulationStation on the correct VGA/X session, but the ES scene being presented to X is black.
  - This is no longer a pure output-selection problem.
  - The remaining likely fault domain is ES/SDL/OpenGL rendering behavior on this VGA-only path, or a Batocera session-launch quirk specific to this hardware/output combination.

Simple-X-client findings from 2026-03-26:
- A temporary `x11vnc` server was started against `DISPLAY=:0` using the bundled binary from the pinned CRT-script tree.
- A simple `xterm` client was launched on `DISPLAY=:0` and verified as a real X11 client with mapped X11 libraries.
- The live VNC capture showed the terminal prompt rendered correctly on the same `:0` session:
  - `docs/batocera/batocera-crt1/vga-only-debug/20260326T0636Z-vnc-proxy/vnc-current.png`
- This proves the basic X/render path is functional on VGA. The machine can draw visible X client content on `:0`.
- Therefore EmulationStation is the black component, or the Batocera ES/openbox/session wrapper around it is the black component. The fault is no longer at the generic X/VGA framebuffer layer.
- Additional probe artifacts are archived under:
  - `docs/batocera/batocera-crt1/vga-only-debug/20260326T0629Z-simple-x-probe/`
  - `docs/batocera/batocera-crt1/vga-only-debug/20260326T0634Z-xterm-visible-probe/`
  - `docs/batocera/batocera-crt1/vga-only-debug/20260326T0636Z-vnc-proxy/`
- Best next debugging target:
  - isolate EmulationStation startup from the stock wrapper
  - capture direct ES stdout/stderr on a working `:0`
  - test SDL/GL software-render or renderer-selection changes one at a time

AMDGPU Display Core findings from 2026-03-27:
- On the stock VGA-only install, full `dmesg` captured repeated AMDGPU display-pipeline failures while X was running:
  - `flip_done timed out`
  - `commit wait timed out`
  - warnings in `amdgpu_dm_atomic_commit_tail`
- A fresh stock Batocera live USB reproduced splash-then-black on the same hardware/VGA path, so this is not best explained as repo drift on the installed system.
- A bounded kernel-argument test was run by adding `amdgpu.dc=0` to the default Batocera boot entry in `/boot/EFI/batocera/syslinux.cfg`.
- With `amdgpu.dc=0` active:
  - the stock wrapper-managed session still started
  - `xrandr` responded cleanly on `DISPLAY=:0.0`
  - the captured framebuffer changed from a cursor-only black image to a full non-black frame
  - the sampled `dmesg` no longer contained the previous `amdgpu_dm_atomic_commit_tail`, `flip_done timed out`, or `commit wait timed out` lines
  - the sampled Xorg log no longer contained the earlier `Present-flip ... Device or resource busy` warnings
- Current strongest judgment:
  - the failing boundary on this hardware/VGA path is AMDGPU Display Core / `amdgpu_dm`, not EmulationStation alone
  - `amdgpu.dc=0` is the current minimal workaround for VGA-only use on this host
- Debug artifacts for this pass are archived under:
  - `docs/batocera/batocera-crt1/vga-only-debug/20260327T1810Z-amdgpu-dc0/`
