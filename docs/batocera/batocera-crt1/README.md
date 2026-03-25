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
1. Run baseline while HDMI is attached and archive the collected facts under `docs/batocera/batocera-crt1/baseline/`.
2. Run the CRT playbook in default `stage` mode. This installs the pinned Batocera-CRT-Script tree and keeps the box in an HDMI-safe hybrid state without installing global CRT timing files.
3. After the physical CRT chain is connected, rerun with `-e batocera_crt_apply_mode=finalize`. The default finalize path is `hybrid`: it keeps HDMI available as a recovery output while also enabling the CRT candidate connector.
4. In `hybrid` and `batocera_crt_test`, the role now avoids installing global CRT timing files. This is intentional: “HDMI enabled” is not sufficient if HDMI is still being driven with CRT-safe timings.
5. Do not treat DRM or XRandR `connected` state as proof that the CRT path is good. On this host, `DP-1` can appear connected even while the user still needs HDMI recovery.
6. Use `DISPLAY=:0.0 xrandr -q` for PC-display-side testing. Do not rely on `batocera-resolution listOutputs` as the only live test path.
7. `crt_only` is explicit and higher risk. That is the mode that applies the global CRT timing files. If CRT sync fails in that mode, the box can still end up headless until you recover over SSH and reboot back into HDMI-first config.
8. If video recovery is needed, rerun with `--tags batocera_crt_recovery`, then reboot before judging the result.
