# iGPU Passthrough Investigation -- Brief

Status: investigation complete, VFIO passthrough abandoned, VM120 reverted to pre-investigation state.

## What was attempted

The goal was to get VAAPI hardware transcoding working inside VM120 (media-stack)
by passing through the host iGPU (Intel UHD 630, device `0000:00:02.0`) via VFIO
to a KVM guest on Proxmox.

### Steps tried

1. Installed `linux-firmware`, `intel-media-va-driver-non-free`, `libva2`, `vainfo`
   inside VM120.
2. Changed `cpu: x86-64-v2-AES` to `cpu: host` -- no effect.
3. Changed machine type to `q35` (from default i440fx) -- no effect.
4. Tried `legacy-igd=1` with `vga: none` -- made things worse (no VBT/ROM,
   legacy mode immediately disabled by firmware).
5. Tried guest kernel params: `intel_iommu=off`, `iommu=off`, `iommu=pt`,
   `i915.reset=0`, `i915.enable_dc=0`, `enable_guc=3` -- none changed the
   hardware state.
6. Attempted runtime debugfs GT wedge reset -- caused a kernel hang.

### Root cause

VFIO exposes the GPU to the guest through the host's hardware IOMMU (VT-d).
The i915 driver inside the guest sees VT-d active in the GPU's register space
at init time. This triggers the VT-d-aware GT initialization path, which
attempts a render-engine ring reset. That ring reset consistently times out
at ~205 ms, causing `intel_gt_set_wedged_on_init`. Once wedged, no render node
(`/dev/dri/renderD128`) is created, so VAAPI is unavailable.

DMC firmware loads successfully; the failure is specifically in the GT ring-reset
during i915 init. This is a hardware-level interaction between VFIO and the
integrated GPU -- the guest kernel cannot override it because the IOMMU state is
baked into the PCI config space by the host.

This is a known limitation. Intel iGPUs were never designed for VFIO passthrough
in the way discrete GPUs are. The `legacy-igd` hack in QEMU exists as a
workaround but only works on specific older platforms and firmware combinations.

## What perfectmediaserver.com says

The PMS guide (https://perfectmediaserver.com/05-advanced/passthrough-igpu-gvtg/)
covers two methods:

1. **Full PCIe passthrough** -- acknowledged but not detailed for iGPU.
2. **GVT-g (mediated devices)** -- splits one iGPU across multiple VMs using
   `i915.enable_gvt=1` on the host and `kvmgt` kernel module.

Critically, the author added a disclaimer that he **abandoned GVT-g due to
instability and poor performance**. GVT-g was removed from the kernel entirely
in Linux 6.x. It is not a viable path.

The guide does not discuss LXC or virtio-gpu approaches. It does not change the
assessment -- VFIO passthrough of Intel iGPUs is a dead end on this hardware
generation, and the only method PMS documented (GVT-g) has been abandoned by
both the author and the kernel.

## Three viable paths forward

### 1. Host i915 + LXC bind-mount (recommended)

Run the transcoding workload in a Proxmox LXC container with `/dev/dri` bind-mounted
from the host. The host i915 driver owns the GPU natively (no IOMMU involvement),
and the LXC guest accesses the render node directly.

- Proven approach, used widely in the Proxmox/Jellyfin community.
- No firmware hacks, no wedge risk, full VAAPI/QSV support.
- Requires moving at least Jellyfin out of VM120 into an LXC, or moving the
  entire media stack.

### 2. Host i915 + virtio-gpu with render node forwarding

Keep VM120 as a KVM guest. Load i915 on the host. Use `virtio-gpu` with
`virgl` or `venus` to expose a virtual GPU to the guest that proxies render
operations to the host GPU.

- Experimental, less community support for VAAPI passthrough specifically.
- Would avoid any migration but may not expose the hardware codec rings
  that VAAPI needs for transcode (only GL/Vulkan compute).
- Not recommended unless LXC is ruled out.

### 3. Discrete GPU (PCIe add-in card)

Add a dedicated GPU (e.g., Intel Arc A380) and pass it through via standard
VFIO. Discrete GPUs handle VFIO correctly because they have proper option ROM
and do not share IOMMU groups with the chipset.

- Works but costs money and a PCIe slot.
- Overkill if only Jellyfin needs transcode.

## Recommended path: LXC with host render node

The simplest and most reliable path is an LXC container with `/dev/dri`
bind-mounted from the Proxmox host.

### What this requires

There are two sub-options:

**Option A -- Move the entire media stack to an LXC.**
All Docker containers (Jellyfin, Plex, Sonarr, Radarr, Prowlarr, Bazarr,
qBittorrent, SABnzbd, Gluetun, Tdarr, Cleanuparr) move from VM120 to a
privileged or unprivileged LXC running Docker.

**Option B -- Split: Jellyfin in an LXC, everything else stays in VM120.**
Only Jellyfin (and optionally Tdarr/Plex) moves to a dedicated LXC with GPU
access. The rest of the stack remains in VM120.

### Ownership boundaries

| Concern | homelab owns | media-stack owns |
|---|---|---|
| LXC definition (Proxmox config, cloud-init) | Yes | No |
| `/dev/dri` bind-mount in LXC config | Yes | No |
| virtiofs share definitions for tank-media/tank-downloads | Yes | No |
| Docker Compose templates and container config | No | Yes |
| Jellyfin VAAPI device mapping in compose | No | Yes |
| Appdata volume layout and migration | No | Yes |
| Network policy (which containers talk to what) | Shared | Shared |

### Risks and constraints

1. **virtiofs mounts.** VM120 currently uses `virtiofs0: tank-media` and
   `virtiofs1: tank-downloads`. LXC containers use bind mounts instead.
   homelab would need to set up bind mounts from the ZFS datasets into the
   LXC rootfs. This is straightforward but is a different mechanism.

2. **Appdata layout.** All container appdata currently lives on VM120's
   `local-lvm` disk (`/opt/appdata` or similar). If only Jellyfin moves,
   its appdata needs to be migrated or shared. If the whole stack moves,
   all appdata moves.

3. **Existing container bind mounts.** The Docker Compose files bind-mount
   paths like `/mnt/tank-media` and `/mnt/tank-downloads` inside VM120.
   In an LXC, these paths would be backed by LXC bind mounts instead of
   virtiofs, but the container-level paths can stay the same.

4. **Networking.** VM120 uses Gluetun for VPN-routed traffic (qBittorrent).
   If the stack splits, Gluetun stays with the download containers in VM120.
   If the whole stack moves, Gluetun moves too and needs the same network
   config in the LXC.

5. **Privileged vs unprivileged LXC.** `/dev/dri` access in an unprivileged
   LXC requires UID/GID mapping for the `render` group. A privileged LXC is
   simpler but has a larger attack surface.

## Decisions needed from media-stack before homelab can proceed

1. **Option A or B?** Move the whole stack or just Jellyfin?
   - If B, does Plex also need transcode, or only Jellyfin?
   - If B, does Tdarr (which also transcodes) move with Jellyfin?

2. **Appdata migration strategy.** Copy appdata to the new LXC's local
   storage, or put appdata on a shared ZFS dataset?

3. **Compose refactor scope.** If splitting, media-stack needs to produce
   two compose files (one for the LXC, one for VM120). Is that acceptable?

4. **Gluetun placement.** If splitting, which side gets Gluetun?

Once these decisions are made, homelab can design the LXC definition,
storage mounts, and Proxmox config. media-stack can then adapt the compose
templates to target the new topology.
