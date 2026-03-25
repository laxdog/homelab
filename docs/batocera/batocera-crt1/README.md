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
- connector candidates:
  - `card0-DP-1`
  - `card0-DP-2`

Apply commands:
- baseline only:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_baseline`
- install CRT script + stage config without switching away from HDMI:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_crt`
- finalize CRT connector selection after the VGA -> UMSA -> SCART chain is connected:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_crt -e batocera_crt_apply_mode=finalize`
- run the test task:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_crt_test -e batocera_crt_apply_mode=finalize`

Rollback:
- restore HDMI-first monitor config:
  - `ansible-playbook ansible/playbooks/batocera.yml --limit batocera-crt1 --tags batocera_crt_recovery`

Operational flow:
1. Run baseline while HDMI is attached and archive the collected facts under `docs/batocera/batocera-crt1/baseline/`.
2. Run the CRT playbook in default `stage` mode. This installs the pinned Batocera-CRT-Script tree and stages switchres plus videomodes without disabling HDMI.
3. After the physical CRT chain is connected, rerun with `-e batocera_crt_apply_mode=finalize` to write `10-monitor.conf` for the selected CRT connector and persist overlay-backed files.
4. If video recovery is needed, rerun with `--tags batocera_crt_recovery` to restore an HDMI-first config.
