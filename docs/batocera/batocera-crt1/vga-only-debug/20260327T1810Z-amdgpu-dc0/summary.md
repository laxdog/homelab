## Batocera VGA `amdgpu.dc=0` test

Date: 2026-03-27
Host: `batocera-crt1` (`10.20.30.206`)

### Hypothesis

The failing boundary on this VGA-only path is AMDGPU Display Core / `amdgpu_dm`, not EmulationStation alone.

### Baseline before change

Default boot command line:

```text
BOOT_IMAGE=/boot/linux label=BATOCERA console=tty3 quiet loglevel=0 vt.global_cursor_default=0 initrd=/boot/initrd.gz
```

Baseline captured evidence:

- repeated `flip_done timed out`
- repeated `commit wait timed out`
- warnings in `amdgpu_dm_atomic_commit_tail`
- Xorg `Present-flip ... Device or resource busy`
- framebuffer capture was effectively all black except cursor

Artifacts:

- `frame-before-dc0.png`
- `baseline-amdgpu-key-lines.txt`

### Change applied

Edited `/boot/EFI/batocera/syslinux.cfg` on the installed system and added `amdgpu.dc=0` to the default `LABEL batocera` `APPEND` line.

This was done as a bounded, reversible boot-arg test.

### Post-change state

Confirmed live `/proc/cmdline`:

```text
BOOT_IMAGE=/boot/linux label=BATOCERA console=tty3 quiet loglevel=0 vt.global_cursor_default=0 amdgpu.dc=0 initrd=/boot/initrd.gz
```

Post-boot session:

- `openbox`
- `emulationstation-standalone`
- `dbus-launch`
- `emulationstation --exit-on-reboot-required --windowed`

### Results

The `amdgpu.dc=0` test materially changed both logs and the live framebuffer:

- sampled post-boot `dmesg` no longer contained:
  - `amdgpu_dm_atomic_commit_tail`
  - `flip_done timed out`
  - `commit wait timed out`
- sampled post-boot Xorg log no longer contained:
  - `Present-flip ... Device or resource busy`
- `xrandr -q --display :0.0` returned cleanly
- framebuffer capture changed from an almost entirely black image to a full non-black frame

Black-pixel ratio:

- before: `0.9998697916666667`
- after: `0.00013671875`

Artifacts:

- `frame-after-dc0.png`
- `after-amdgpu-key-lines.txt`
- `Xorg.0.log`
- `proc-cmdline.txt`
- `processes.txt`

### Judgment

This strongly supports the conclusion that the failing boundary on this hardware/VGA path is AMDGPU Display Core / `amdgpu_dm`.

`amdgpu.dc=0` is the current minimal workaround for VGA-only operation on this host.

### Rollback

Remove `amdgpu.dc=0` from the default `APPEND` line in `/boot/EFI/batocera/syslinux.cfg`, or remove the host-scoped kernel-arg entry from Ansible and reapply `--tags batocera_vga_safe`, then reboot.
