# iGPU Hardware Transcoding -- Handoff Brief

Status: research complete, implementation plan ready, awaiting media-stack decisions.
Last updated: 2026-04-01

---

## 1. Hardware Summary

| Item | Value |
|---|---|
| CPU | Intel 10th Gen Core (Comet Lake) |
| iGPU | Intel UHD 630 (Gen 9.5 device `0000:00:02.0`) |
| Host | Proxmox VE 9.x on `10.20.30.46` |
| Guest | VM120, Ubuntu 24.04 (noble), Docker media stack |
| Quick Sync codecs | H.264 enc/dec, HEVC 8-bit enc/dec, HEVC 10-bit enc/dec, VP9 dec, JPEG enc/dec |
| AV1 | **Not supported** (requires 11th Gen+ for decode, 12th Gen+ for encode) |

### What the hardware supports and does not support

| Approach | Supported? | Notes |
|---|---|---|
| SR-IOV | **No** | Requires 12th Gen+ (Alder Lake) with specific i915 patches |
| GVT-g | **No** | Removed from mainline kernel in 6.x; was unstable on 10th gen anyway |
| VFIO full PCI passthrough | **No** | i915 GT ring-reset wedge under VT-d; hardware-level dead end |
| LXC + host render node | **Yes** | Consensus best practice for this generation |
| virtio-gpu (virgl/venus) | Theoretical | Only exposes GL/Vulkan, not hardware codec rings; not viable for VAAPI/QSV |
| Discrete GPU passthrough | **Yes** | Works but unnecessary cost; UHD 630 handles 4-6 simultaneous 1080p transcodes |

---

## 2. Investigation Summary

### What was tried (VFIO passthrough to VM120)

1. Installed `linux-firmware`, `intel-media-va-driver-non-free`, `libva2`, `vainfo` inside VM120.
2. Changed CPU type from `x86-64-v2-AES` to `host` -- no effect.
3. Changed machine type to `q35` (from default i440fx) -- no effect.
4. Tried `legacy-igd=1` with `vga: none` -- made things worse (no VBT/ROM, legacy mode immediately disabled by firmware).
5. Tried guest kernel params: `intel_iommu=off`, `iommu=off`, `iommu=pt`, `i915.reset=0`, `i915.enable_dc=0`, `enable_guc=3` -- none changed the hardware state.
6. Attempted runtime debugfs GT wedge reset -- caused a kernel hang.

### Root cause

VFIO exposes the GPU to the guest through the host's hardware IOMMU (VT-d). The i915 driver inside the guest sees VT-d active in the GPU's register space at init time. This triggers the VT-d-aware GT initialization path, which attempts a render-engine ring reset. That ring reset consistently times out at ~205 ms, causing `intel_gt_set_wedged_on_init`. Once wedged, no render node (`/dev/dri/renderD128`) is created, so VAAPI is unavailable.

DMC firmware loads successfully; the failure is specifically in the GT ring-reset during i915 init. This is a hardware-level interaction between VFIO and the integrated GPU -- the guest kernel cannot override it because the IOMMU state is baked into the PCI config space by the host.

Intel iGPUs were never designed for VFIO passthrough in the way discrete GPUs are. The `legacy-igd` hack in QEMU exists as a workaround but only works on specific older platforms and firmware combinations.

### Current VM120 state (clean, reverted)

- cpu: `x86-64-v2-AES`
- machine type: default (i440fx)
- GRUB cleaned of all investigation parameters
- All 12 Docker containers confirmed healthy
- Software transcoding active (libx264)

---

## 3. Recommended Approach

### Clear recommendation: Jellyfin in a Proxmox LXC with host `/dev/dri/renderD128` bind-mount

This is the consensus best practice across all sources consulted (Jellyfin official docs, Proxmox forums, community guides, ktz.me blog). The host i915 driver owns the GPU natively (no IOMMU involvement), and the LXC guest accesses the render node directly. This approach:

- Is proven and widely deployed in the Proxmox/Jellyfin community
- Requires no firmware hacks, no wedge risk
- Provides full VAAPI and QSV support
- Works on Proxmox 8.x and 9.x with both privileged and unprivileged LXC
- Is the only viable modern path for Intel 10th gen iGPU hardware transcoding in a virtualized environment

### Why NOT keep Jellyfin in VM120

A KVM virtual machine (VM120) cannot access the host render node. The only way to give a VM GPU access is VFIO passthrough, which is the dead end documented above. There is no mechanism to bind-mount `/dev/dri/renderD128` from the Proxmox host into a KVM guest. LXC is the only container type that supports this.

**Conclusion: Jellyfin must move out of VM120 to get hardware transcoding.**

### Jellyfin-only LXC vs full stack migration

**Recommendation: Jellyfin-only LXC (Option B).**

Rationale:
- Only Jellyfin (and optionally Tdarr) needs GPU access for transcoding
- The rest of the media stack (Sonarr, Radarr, Prowlarr, Bazarr, qBittorrent, SABnzbd, Gluetun, Cleanuparr) has no GPU dependency
- Keeping the non-GPU stack in VM120 avoids a large migration
- The Jellyfin LXC can be purpose-built and minimal
- Gluetun (VPN) stays with download containers in VM120, avoiding VPN complexity in the LXC
- If the LXC approach fails for any reason, the rest of the stack is unaffected

If Tdarr also needs hardware transcoding, it should move to the same LXC as Jellyfin or get its own LXC with the same `/dev/dri` passthrough.

### Jellyfin hwaccel mode: QSV (preferred) or VAAPI (fallback)

Per Jellyfin's official documentation:
- **QSV is preferred on Linux** for Intel GPUs Broadwell (5th gen) and newer -- this includes 10th gen
- **VAAPI is the fallback** for pre-Broadwell or when QSV has issues
- QSV uses the Intel Media SDK / oneVPL runtime on top of VAAPI, providing better performance and more codec options
- Both QSV and VAAPI use the same underlying hardware (Quick Sync), but QSV has better pipeline integration in Jellyfin's ffmpeg

**Note:** Intel has deprecated MediaSDK in favor of oneVPL for newer generations, but 10th gen is still supported by MediaSDK. Jellyfin's bundled `jellyfin-ffmpeg7` includes all necessary media drivers except OpenCL.

---

## 4. Exact Implementation Plan

### 4a. Host side (Proxmox `10.20.30.46`)

**Verify i915 is loaded and render node exists:**
```bash
lsmod | grep i915
ls -la /dev/dri/
# Expect: card0 and renderD128 owned by root:render
```

**Identify render group GID:**
```bash
getent group render | cut -d: -f3
# Typically 104 on Proxmox; note this value for LXC config
```

**Install verification tools on host (if not present):**
```bash
apt install -y intel-gpu-tools vainfo intel-media-va-driver
```

**Verify host VAAPI is healthy:**
```bash
vainfo
# Should list H264, HEVC, VP9 encode/decode profiles
intel_gpu_top
# Should show GPU idle (or active if anything is using it)
```

**Set stable device permissions (udev rule):**
```bash
cat > /etc/udev/rules.d/99-intel-render.rules << 'EOF'
SUBSYSTEM=="drm", KERNEL=="renderD128", GROUP="render", MODE="0660"
EOF
udevadm control --reload-rules && udevadm trigger
```

**For unprivileged LXC -- update subordinate GID mapping:**
```bash
# Add the host render group GID to root's subgid allowance
# Replace 104 with actual render GID if different
echo "root:104:1" >> /etc/subgid
```

**Host does NOT need `intel_iommu=on` or any GRUB changes for this approach.** The iGPU stays on the host with native i915. If `intel_iommu=on` is still in GRUB from the VFIO investigation, it is harmless but unnecessary.

**GuC/HuC firmware:** For 10th gen, `enable_guc=3` is optional. The default i915 settings work. If GuC submission is desired for better scheduling, it can be enabled later but is not required for VAAPI/QSV.

### 4b. LXC configuration

**OS choice:** Debian 12 (bookworm) is recommended over Ubuntu 24.04 for the LXC. Jellyfin's official docs and most community guides target Debian. Ubuntu works but adds a layer of complexity (universe repo, snap interference). The LXC is purpose-built for Jellyfin, so a minimal Debian base is ideal.

**Create the LXC (example via Proxmox CLI):**
```bash
# Use next available CTID; example uses 121
pct create 121 local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
  --hostname jellyfin \
  --memory 4096 \
  --cores 4 \
  --rootfs local-lvm:16 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --features nesting=1 \
  --start 0
```

**Option A: Unprivileged LXC config (recommended for security)**

Add to `/etc/pve/lxc/121.conf`:
```
# GPU device passthrough
lxc.cgroup2.devices.allow: c 226:0 rwm
lxc.cgroup2.devices.allow: c 226:128 rwm
lxc.mount.entry: /dev/dri/renderD128 dev/dri/renderD128 none bind,optional,create=file

# GID mapping: map container render GID to host render GID
# Container GID 993 -> Host GID 104 (render)
# Adjust 993 to match container's render group; adjust 104 to match host's
lxc.idmap: u 0 100000 65536
lxc.idmap: g 0 100000 993
lxc.idmap: g 993 104 1
lxc.idmap: g 994 100994 64542
```

The critical line is `lxc.idmap: g 993 104 1` which maps whatever GID the container's render group uses to the host's actual render GID (104). The GID 993 is chosen during container setup; verify with `getent group render` inside the LXC after first boot.

**Option B: Privileged LXC config (simpler, viable for single-purpose LXC)**

Add to `/etc/pve/lxc/121.conf`:
```
# GPU device passthrough
lxc.cgroup2.devices.allow: c 226:0 rwm
lxc.cgroup2.devices.allow: c 226:128 rwm
lxc.mount.entry: /dev/dri/renderD128 dev/dri/renderD128 none bind,optional,create=file
```

Set `unprivileged: 0` in the LXC config. No GID mapping needed -- the container's render group GID maps directly to the host.

**Proxmox 8.2+ alternative (GUI device passthrough):**

In Proxmox web UI: Container > Resources > Add > Device Passthrough:
- Device Path: `/dev/dri/renderD128`
- GID in CT: `104` (or container's render GID)
- Mode: `0666`

This generates a `dev0:` line in the config that replaces the manual `lxc.mount.entry` lines.

**Storage bind-mounts for media access:**
```
# In /etc/pve/lxc/121.conf -- bind-mount ZFS datasets
mp0: /tank/media,mp=/mnt/tank-media,ro=1
mp1: /tank/downloads,mp=/mnt/tank-downloads,ro=0
```
Note: These paths assume the ZFS datasets are directly mounted on the Proxmox host. If they are only exported via virtiofs to VM120, the host will need direct ZFS mount points for the LXC.

### 4c. Guest side (inside the LXC)

**Install required packages:**
```bash
apt update && apt upgrade -y
apt install -y \
  curl \
  gnupg \
  intel-media-va-driver \
  vainfo \
  intel-gpu-tools \
  libdrm-intel1
```

Note: `intel-media-va-driver` (iHD driver) is the correct driver for 10th gen+. The older `i965` driver (`libva-intel-driver`) is for pre-Broadwell only. The `-non-free` variant adds some additional codec profiles but the standard package covers H.264 and HEVC for 10th gen.

**Install Jellyfin (official repo, not snap):**
```bash
curl -fsSL https://repo.jellyfin.org/install-debuntu.sh | bash
```

This installs `jellyfin-server`, `jellyfin-web`, and `jellyfin-ffmpeg7`. The bundled ffmpeg includes Intel media drivers.

**Install OpenCL runtime (needed for HDR tone mapping):**
```bash
apt install -y intel-opencl-icd
```

If the Debian repo version is too old (must be 22.xx+), install from Intel's compute-runtime GitHub releases.

**Add Jellyfin user to render group:**
```bash
usermod -aG render jellyfin
usermod -aG video jellyfin
systemctl restart jellyfin
```

**Verify VAAPI works before touching Jellyfin settings:**
```bash
# Check render device exists and is accessible
ls -la /dev/dri/
# Expect renderD128

# Check VAAPI profiles
/usr/lib/jellyfin-ffmpeg/vainfo --display drm --device /dev/dri/renderD128
# Should list VAProfileH264*, VAProfileHEVC*, VAProfileVP9* entries

# Check OpenCL (for tone mapping)
/usr/lib/jellyfin-ffmpeg/ffmpeg -v verbose \
  -init_hw_device vaapi=va:/dev/dri/renderD128 \
  -init_hw_device opencl@va 2>&1 | head -20
# Should show "Successfully created opencl device"
```

**Configure Jellyfin for QSV:**
1. Open Jellyfin web UI > Dashboard > Playback > Transcoding
2. Hardware acceleration: **Intel QuickSync (QSV)**
3. Hardware device: `/dev/dri/renderD128`
4. Enable: H.264, HEVC, HEVC 10-bit hardware decoding
5. Enable: H.264, HEVC hardware encoding
6. Enable hardware-accelerated tone mapping (OpenCL method for 10th gen)
7. Save and restart Jellyfin

**Verify transcoding works:**
```bash
# On the Proxmox host, run:
intel_gpu_top
# Then play a video in Jellyfin that requires transcoding
# The Video and Render bars should show activity
```

### 4d. Can Jellyfin stay in VM120 with host render? -- No

A KVM virtual machine cannot bind-mount host device nodes. The only path to give a VM access to a host GPU is PCI passthrough (VFIO), which is the dead end documented in section 2. There is no virtio or 9p mechanism to expose `/dev/dri/renderD128` into a KVM guest in a way that preserves the DRM/VAAPI interface.

**Jellyfin must run in an LXC or directly on the Proxmox host to use the iGPU.** Running it on the host is viable but violates the principle of keeping the hypervisor clean.

---

## 5. Decisions Needed from Media-Stack Agent

Before homelab can execute, media-stack must decide:

1. **Jellyfin-only LXC or full stack migration?**
   - Recommendation is Jellyfin-only LXC (see section 3)
   - If Tdarr also needs GPU, does it move with Jellyfin?
   - Does Plex (if present) also need transcode?

2. **Appdata location for Jellyfin:**
   - Currently at `/opt/media-stack/appdata/jellyfin` on VM120 root disk
   - Options: copy to LXC local storage, or put on a shared ZFS dataset
   - Jellyfin metadata/cache can be large (10-50GB); plan storage accordingly

3. **Media library access from LXC:**
   - VM120 uses virtiofs mounts (`tank-media`, `tank-downloads`)
   - The LXC will use Proxmox bind-mounts from ZFS datasets instead
   - Are the ZFS datasets mounted directly on the Proxmox host, or only via virtiofs?
   - If only virtiofs, homelab needs to create direct mount points

4. **Acceptable downtime window:**
   - Jellyfin migration requires service interruption
   - Users lose transcoding (already software-only) during migration
   - Estimate: 1-2 hours for LXC creation, config, data copy, and validation

5. **Network identity:**
   - Will the Jellyfin LXC get a new IP, or should it take VM120's Jellyfin port?
   - If new IP: Heimdall dashboard, Bazarr, and any reverse proxy configs need updating
   - If same port on different IP: DNS/routing changes needed

6. **Privileged vs unprivileged LXC:**
   - Unprivileged is more secure but requires GID mapping (more complex setup)
   - Privileged is simpler and avoids Proxmox 9 AppArmor complications
   - For a single-purpose Jellyfin LXC on a trusted home network, privileged is pragmatic
   - Recommendation: privileged, unless media-stack has a strong preference otherwise

---

## 6. What Homelab Will Own in the Migration

- LXC definition and Proxmox config (`/etc/pve/lxc/<CTID>.conf`)
- Device passthrough of `/dev/dri/renderD128` into LXC
- Host render node health verification (udev rules, i915 loaded, vainfo healthy)
- ZFS bind-mount configuration for media/download datasets into LXC
- Storage allocation for Jellyfin appdata on LXC root disk or separate mount
- Networking: IP assignment, firewall rules, any routing changes
- Monitoring: `intel_gpu_top` on host to verify GPU utilization post-migration

---

## 7. What Media-Stack Will Own in the Migration

- Jellyfin application configuration and hardware acceleration settings (QSV, device path, codec toggles)
- Validating transcodes work after homelab proves the render path is healthy
- Jellyfin appdata migration (copy from VM120 to LXC)
- Docker compose changes if Jellyfin is extracted from the VM120 compose
- Updating any service references (Bazarr, Heimdall, reverse proxy) to point to new Jellyfin IP
- Tdarr migration (if it moves to the LXC)
- End-to-end playback validation (multiple codecs, tone mapping, subtitles)

---

## 8. Sources Consulted

| # | Source | Date | Contribution |
|---|---|---|---|
| 1 | [ktz.me -- Why I stopped using GVT-g on Proxmox](https://blog.ktz.me/why-i-stopped-using-intel-gvt-g-on-proxmox/) | ~2020, updated 2023 | Confirms GVT-g is unstable (58-82% perf loss, kernel panics). Author abandoned it. Recommends running on host or LXC. |
| 2 | [PerfectMediaServer -- iGPU passthrough / GVT-g](https://perfectmediaserver.com/05-advanced/passthrough-igpu-gvtg/) | ~2021 | Documents GVT-g setup with disclaimer that author abandoned the method. Does not cover LXC. Confirms GVT-g is a dead end. |
| 3 | [Jellyfin docs -- Hardware Acceleration (Intel)](https://jellyfin.org/docs/general/post-install/transcoding/hardware-acceleration/intel/) | Current (2025+) | Official source. QSV preferred over VAAPI on Linux for 5th gen+. Lists exact packages, Docker/LXC device config, verification commands. Confirms 10th gen supports H.264/HEVC/VP9. No AV1. |
| 4 | [Proxmox forum -- Jellyfin + QSV + unprivileged LXC guide](https://forum.proxmox.com/threads/guide-jellyfin-remote-network-shares-hw-transcoding-with-intels-qsv-unprivileged-lxc.142639/) | Mar 2024, PVE 8.2 | Detailed guide with exact LXC config lines, GID mapping for unprivileged LXC, `lxc.hook.pre-start` for chown. Tested on i7-1165G7. |
| 5 | [DiyMediaServer -- Jellyfin + Intel QuickSync unprivileged LXC](https://diymediaserver.com/post/jellyfin_intel_quicksync_unprivileged_lxc/) | Jul 2025, updated Oct 2025 | Most current comprehensive guide. Full `lxc.idmap` config for unprivileged LXC, host subgid setup, udev rules, guest packages. Confirms 8th-10th gen: 4-6 simultaneous 1080p H.264 streams. |
| 6 | [Proxmox forum -- HW accel on Jellyfin LXC for Intel i9 10th gen](https://forum.proxmox.com/threads/hardware-acceleration-on-jellyfin-lxc-for-intel-i9-10th-gen.132282/) | 2024 | **Directly matches our hardware.** 10th gen i9 user with same setup. Confirms LXC passthrough works. Required privileged LXC and `intel-media-va-driver`. Used VAAPI (not QSV) in that case. |
| 7 | [erikdevries.com -- HW transcoding in Jellyfin on Proxmox with Intel iGPU](https://erikdevries.com/posts/hardware-transcoding-in-jellyfin-on-proxmox-with-intel-integrated-graphics) | 2024-2025 | Step-by-step guide using Proxmox 8+ GUI device passthrough (`dev0:` config line). Tested with 13th gen but approach applies to 10th gen. Recommends QSV, Debian 12 LXC. |
| 8 | [ktz.me -- Proxmox 9 made unprivileged LXCs annoying for QuickSync](https://blog.ktz.me/proxmox-9-made-unprivileged-lxcs-pointless-for-quicksync-users/) | Sep 2025 | **Critical for PVE 9.** AppArmor 4.1 in PVE 9 breaks `intel_gpu_top` in unprivileged LXCs (perf_event_open denied). Transcoding itself still works. Monitoring must be done from host. Author leans toward privileged LXC as pragmatic choice. |
| 9 | [Proxmox forum -- LXC iGPU passthrough tutorial](https://forum.proxmox.com/threads/proxmox-lxc-igpu-passthrough.141381/) | 2024, PVE 8.1 | General tutorial. Includes unnecessary GVT-g/IOMMU steps that are not needed for LXC bind-mount approach. Useful for basic config lines. |
| 10 | [Jellyfin forum -- SOLVED: Proxmox LXC HW transcoding](https://forum.jellyfin.org/t-solved-proxmox-lxc-hardware-transcoding) | 2024 | Confirms `intel-media-va-driver-non-free` and `intel-opencl-icd` needed on Ubuntu 24.04 LXC. Render group GID mapping was the fix. |
| 11 | [Proxmox wiki -- Linux Container](https://pve.proxmox.com/wiki/Linux_Container) | Current | Official Proxmox LXC documentation. Covers cgroup2 device allow syntax, mount entries, privileged vs unprivileged, and device passthrough in PVE 8.2+. |

---

## 9. Risks and Known Issues

### Proxmox 9.x + AppArmor 4.1 (PVE 9 specific)

PVE 9.0 shipped AppArmor 4.1, which restricts `perf_event_open()` in unprivileged LXCs. This means:
- `intel_gpu_top` **will not work** inside an unprivileged LXC on PVE 9
- **Transcoding itself is unaffected** -- the render device still works
- Workarounds (disabling AppArmor, setting `perf_event_paranoid=0`) weaken security
- **Mitigation:** Run `intel_gpu_top` on the Proxmox host, not in the LXC. Use a privileged LXC if monitoring from inside is required.

### Render device numbering

If a discrete GPU is ever added, `/dev/dri/renderD128` might shift to `renderD129`. The LXC config hardcodes the device path. A udev rule on the host can pin the Intel iGPU to a stable path if needed.

### Kernel upgrades

The i915 driver is in the kernel. Proxmox kernel upgrades could theoretically change behavior, though i915 for 10th gen is mature and stable. No regressions reported in community sources.

### Intel MediaSDK deprecation

Intel has deprecated MediaSDK in favor of oneVPL for 12th gen+. For 10th gen, MediaSDK is still the active runtime. Jellyfin's bundled ffmpeg handles this transparently. This is a long-term concern (years) not an immediate risk.

### LXC container restart and /dev/dri

Some users report `/dev/dri` disappearing after LXC restart if the host's i915 hasn't finished initializing. The `optional` flag in the mount entry handles this gracefully -- the LXC starts without the device, and a restart after the host GPU is ready fixes it. In practice, on a system where i915 loads at boot, this is not an issue.

### Fallback

If the LXC approach fails for any unexpected reason, **software transcoding in VM120 is working now** (libx264). This is the safe fallback. No data is at risk during the LXC migration because VM120 remains untouched until the new LXC is proven healthy.

---

## 10. Summary of Key Findings

1. **LXC + host render node is confirmed as the right path** for Intel 10th gen on Proxmox 9.x. Every source consulted agrees. There are no contradictions in the research.

2. **QSV is the preferred hwaccel mode** per Jellyfin's official docs, with VAAPI as fallback. Both work on 10th gen UHD 630.

3. **Jellyfin-only LXC is the recommended migration scope.** The rest of the media stack stays in VM120. This minimizes risk and complexity.

4. **Privileged LXC is the pragmatic choice** for a single-purpose Jellyfin container on a home network, especially given PVE 9's AppArmor complications with unprivileged LXCs. Unprivileged is viable but requires more complex GID mapping.

5. **No surprises or contradictions found.** All sources converge on the same recommendation. The 10th gen i9 Proxmox forum thread directly validates this approach on matching hardware.
