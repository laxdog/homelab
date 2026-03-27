# Historical Batocera Investigation

This directory contains archived investigation artifacts from the earlier Batocera debugging passes.

These materials are preserved because they contain useful evidence, especially:
- repeated AMDGPU Display Core timeout signatures on VGA
- the `amdgpu.dc=0` workaround proof
- framebuffer captures and X/EmulationStation investigation history

They are not the active source of truth for how this host should now be managed.

Active configuration guidance now lives in:
- `docs/batocera/batocera-crt1/README.md`

Historical items retained in the repo:
- `docs/batocera/batocera-crt1/vga-only-debug/`
- `docs/batocera/batocera-crt1/baseline/`

Historical Batocera automation retained but no longer active in the main playbook:
- `ansible/roles/batocera_crt_script`
- `ansible/roles/batocera_crt_config`
- old CRT-centric investigative logic and debug-only mutations

Those CRT-related roles are intentionally not part of the current minimal VGA baseline.
If CRT/UMSA work resumes later, it should restart from the clean baseline and re-validate any reused logic first.
