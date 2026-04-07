# Pre-SSD-Install Storage Baseline

**Captured:** 2026-04-07
**Host:** Proxmox `pve` at `10.20.30.46`
**Purpose:** Baseline snapshot of storage and guest topology immediately
before two 500 GB SATA SSDs are installed in the Proxmox host. This file
exists so the post-install state can be compared against a known-good
reference and so any drift introduced by the install can be detected
quickly.

The host will be powered down to install the drives. This document is
the rollback reference if anything is unexpected after power-on.

---

## Disks present today

Three rotational SATA disks (`sda`, `sdb`, `sdc`) form the `tank` ZFS
raidz1 pool. One NVMe (`nvme0n1`) carries Proxmox itself and the
LVM-thin `pve-data` pool.

```
$ ls -la /dev/sd* /dev/nvme*
crw------- 1 root root 240,  0 /dev/nvme0
brw-rw---- 1 root disk 259,  0 /dev/nvme0n1
brw-rw---- 1 root disk 259,  1 /dev/nvme0n1p1
brw-rw---- 1 root disk 259,  2 /dev/nvme0n1p2
brw-rw---- 1 root disk 259,  3 /dev/nvme0n1p3
brw-rw---- 1 root disk   8,  0 /dev/sda
brw-rw---- 1 root disk   8,  1 /dev/sda1
brw-rw---- 1 root disk   8,  9 /dev/sda9
brw-rw---- 1 root disk   8, 16 /dev/sdb
brw-rw---- 1 root disk   8, 17 /dev/sdb1
brw-rw---- 1 root disk   8, 25 /dev/sdb9
brw-rw---- 1 root disk   8, 32 /dev/sdc
brw-rw---- 1 root disk   8, 33 /dev/sdc1
brw-rw---- 1 root disk   8, 41 /dev/sdc9
```

After installation, two new SATA SSDs are expected to appear, most
likely as `/dev/sdd` and `/dev/sde`. Existing `/dev/sd[abc]` may be
re-enumerated by the kernel depending on SATA port assignment — pool
membership uses `/dev/disk/by-id/wwn-*` so ZFS will not care about
re-lettering.

---

## lsblk -f

```
NAME                           FSTYPE      FSVER            LABEL           UUID                                   FSAVAIL FSUSE% MOUNTPOINTS
sda                                                                                                                               
├─sda1                         zfs_member  5000             tank            15003572227522770058                                  
└─sda9                                                                                                                            
sdb                                                                                                                               
├─sdb1                         zfs_member  5000             tank            15003572227522770058                                  
└─sdb9                                                                                                                            
sdc                                                                                                                               
├─sdc1                         zfs_member  5000             tank            15003572227522770058                                  
└─sdc9                                                                                                                            
zd0                                                                                                                               
├─zd0p1                        ext4        1.0              cloudimg-rootfs 8515de1c-ba7e-467b-adde-6d9f8a8dbc1f                  
├─zd0p14                                                                                                                          
├─zd0p15                       vfat        FAT32            UEFI            9FE0-DE2B                                             
└─zd0p16                       ext4        1.0              BOOT            7dc15ce9-d090-44d7-bb05-2a36d545a8e3                  
nvme0n1                                                                                                                           
├─nvme0n1p1                                                                                                                       
├─nvme0n1p2                    vfat        FAT32                            BD7C-B639                              1013.2M     1% /boot/efi
└─nvme0n1p3                    LVM2_member LVM2 001                         yG35T9-nWz5-cAaY-3B7X-payT-jpNB-XQfHhT                
  ├─pve-swap                   swap        1                                1ce187d5-6e32-40e5-8b26-be81ea153fee                  [SWAP]
  ├─pve-root                   ext4        1.0                              0d99d398-6229-4ea4-99e5-00d08382df26     52.9G    17% /
  ├─pve-data_tmeta                                                                                                                
  │ └─pve-data-tpool                                                                                                              
  │   ├─pve-data                                                                                                                  
  │   ├─pve-vm--122--disk--1                                                                                                      
  │   ├─pve-vm--122--disk--2                                                                                                      
  │   ├─pve-vm--120--cloudinit iso9660     Joliet Extension cidata          2026-04-02-00-17-59-00                                
  │   ├─pve-vm--120--disk--0                                                                                                      
  │   ├─pve-vm--133--cloudinit iso9660     Joliet Extension cidata          2026-04-02-00-35-49-00                                
  │   ├─pve-vm--171--cloudinit iso9660     Joliet Extension cidata          2026-04-02-00-18-05-00                                
  │   ├─pve-vm--171--disk--0                                                                                                      
  │   ├─pve-vm--128--disk--0   ext4        1.0                              01b5cdef-66d9-4b45-a3ba-e296c86004e8                  
  │   ├─pve-vm--154--disk--0   ext4        1.0                              0d6d6cef-03fb-4bd0-908b-458f9e37b44a                  
  │   ├─pve-vm--153--disk--0   ext4        1.0                              e0725ea3-d2c0-45e8-b308-e29920e77544                  
  │   ├─pve-vm--158--disk--0   ext4        1.0                              c73855f8-a224-4fda-bd41-0830d40685d3                  
  │   ├─pve-vm--156--disk--0   ext4        1.0                              f0b83334-6595-41a5-ae7b-7b1b1890575c                  
  │   ├─pve-vm--157--disk--0   ext4        1.0                              24d7d6c9-51a9-44f4-85ca-a297a0f44d8b                  
  │   ├─pve-vm--159--disk--0   ext4        1.0                              332f9050-7ce0-43b1-9bb0-1c933f8fbc6c                  
  │   ├─pve-vm--160--disk--0   ext4        1.0                              f501aa3a-b073-410d-8e58-909721593174                  
  │   ├─pve-vm--162--disk--0   ext4        1.0                              3e3f4ae3-d33d-459c-80ac-a64cfa013579                  
  │   ├─pve-vm--161--disk--0   ext4        1.0                              f3b04793-f0f5-4384-8856-d9a9510f639b                  
  │   ├─pve-vm--164--disk--0   ext4        1.0                              9a10cab5-7812-42a4-a20f-92c1e3a11100                  
  │   └─pve-vm--166--disk--0   ext4        1.0                              2f0d2763-766b-43c8-a51e-45a51da4f87b                  
  └─pve-data_tdata                                                                                                                
    └─pve-data-tpool                                                                                                              
      ├─pve-data                                                                                                                  
      ├─pve-vm--122--disk--1                                                                                                      
      ├─pve-vm--122--disk--2                                                                                                      
      ├─pve-vm--120--cloudinit iso9660     Joliet Extension cidata          2026-04-02-00-17-59-00                                
      ├─pve-vm--120--disk--0                                                                                                      
      ├─pve-vm--133--cloudinit iso9660     Joliet Extension cidata          2026-04-02-00-35-49-00                                
      ├─pve-vm--171--cloudinit iso9660     Joliet Extension cidata          2026-04-02-00-18-05-00                                
      ├─pve-vm--171--disk--0                                                                                                      
      ├─pve-vm--128--disk--0   ext4        1.0                              01b5cdef-66d9-4b45-a3ba-e296c86004e8                  
      ├─pve-vm--154--disk--0   ext4        1.0                              0d6d6cef-03fb-4bd0-908b-458f9e37b44a                  
      ├─pve-vm--153--disk--0   ext4        1.0                              e0725ea3-d2c0-45e8-b308-e29920e77544                  
      ├─pve-vm--158--disk--0   ext4        1.0                              c73855f8-a224-4fda-bd41-0830d40685d3                  
      ├─pve-vm--156--disk--0   ext4        1.0                              f0b83334-6595-41a5-ae7b-7b1b1890575c                  
      ├─pve-vm--157--disk--0   ext4        1.0                              24d7d6c9-51a9-44f4-85ca-a297a0f44d8b                  
      ├─pve-vm--159--disk--0   ext4        1.0                              332f9050-7ce0-43b1-9bb0-1c933f8fbc6c                  
      ├─pve-vm--160--disk--0   ext4        1.0                              f501aa3a-b073-410d-8e58-909721593174                  
      ├─pve-vm--162--disk--0   ext4        1.0                              3e3f4ae3-d33d-459c-80ac-a64cfa013579                  
      ├─pve-vm--161--disk--0   ext4        1.0                              f3b04793-f0f5-4384-8856-d9a9510f639b                  
      ├─pve-vm--164--disk--0   ext4        1.0                              9a10cab5-7812-42a4-a20f-92c1e3a11100                  
      └─pve-vm--166--disk--0   ext4        1.0                              2f0d2763-766b-43c8-a51e-45a51da4f87b                  
```

---

## LVM (NVMe / `pve-data` thin pool)

```
$ pvs
  PV             VG  Fmt  Attr PSize    PFree
  /dev/nvme0n1p3 pve lvm2 a--  <237.00g 1.00g

$ vgs
  VG  #PV #LV #SN Attr   VSize    VFree
  pve   1  23   0 wz--n- <237.00g 1.00g

$ lvs --units g pve
  LV               VG  Attr       LSize   Pool Origin Data%  Meta%
  data             pve twi-aotz-- 155.87g             76.35  3.65
  root             pve -wi-ao----  69.25g
  swap             pve -wi-ao----   8.00g
  vm-120-cloudinit pve Vwi-aotz--   0.00g data        9.38
  vm-120-disk-0    pve Vwi-aotz--  40.00g data        53.62
  vm-122-disk-0    pve Vwi---tz--   0.00g data
  vm-122-disk-1    pve Vwi-aotz--  48.00g data        67.19
  vm-122-disk-2    pve Vwi-aotz--   0.00g data        14.06
  vm-128-disk-0    pve Vwi-aotz--   8.00g data        52.42
  vm-133-cloudinit pve Vwi-aotz--   0.00g data        9.38
  vm-153-disk-0    pve Vwi-aotz--   8.00g data        52.25
  vm-154-disk-0    pve Vwi-aotz--  16.00g data        96.13
  vm-156-disk-0    pve Vwi-aotz--   8.00g data        55.84
  vm-157-disk-0    pve Vwi-aotz--   8.00g data        47.22
  vm-158-disk-0    pve Vwi-aotz--   8.00g data        54.27
  vm-159-disk-0    pve Vwi-aotz--   8.00g data        54.20
  vm-160-disk-0    pve Vwi-aotz--   8.00g data        32.72
  vm-161-disk-0    pve Vwi-aotz--   8.00g data        50.17
  vm-162-disk-0    pve Vwi-aotz--   8.00g data        57.63
  vm-164-disk-0    pve Vwi-aotz--   8.00g data        47.51
  vm-166-disk-0    pve Vwi-aotz--   8.00g data        52.91
  vm-171-cloudinit pve Vwi-aotz--   0.00g data        9.38
  vm-171-disk-0    pve Vwi-aotz--  16.00g data        33.51
```

`pve-data` thin pool: **76.35%** data used, 3.65% metadata.

---

## ZFS pool `tank`

```
$ zpool list
NAME   SIZE  ALLOC   FREE  CKPOINT  EXPANDSZ   FRAG    CAP  DEDUP    HEALTH  ALTROOT
tank  27.3T  1.19T  26.1T        -         -     0%     4%  1.00x    ONLINE  -

$ zpool status tank
  pool: tank
 state: ONLINE
status: Some supported and requested features are not enabled on the pool.
	The pool can still be used, but some features are unavailable.
action: Enable all features using 'zpool upgrade'. Once this is done,
	the pool may no longer be accessible by software that does not support
	the features. See zpool-features(7) for details.
  scan: scrub repaired 0B in 00:10:34 with 0 errors on Sun Mar  8 00:34:35 2026
config:

	NAME                        STATE     READ WRITE CKSUM
	tank                        ONLINE       0     0     0
	  raidz1-0                  ONLINE       0     0     0
	    wwn-0x5000c50094bbbe1f  ONLINE       0     0     0
	    wwn-0x5000c50094bbcbef  ONLINE       0     0     0
	    wwn-0x5000c50094bba7c3  ONLINE       0     0     0

errors: No known data errors

$ zfs list
NAME                     USED  AVAIL  REFER  MOUNTPOINT
tank                     819G  17.2T   202K  /tank
tank/backups             635G  17.2T   635G  /tank/backups
tank/downloads          7.36M  17.2T  7.36M  /tank/downloads
tank/media               146G  17.2T   146G  /tank/media
tank/personal            128K  17.2T   128K  /tank/personal
tank/scratch             128K  17.2T   128K  /tank/scratch
tank/subvol-163-disk-0  12.6G  27.4G  12.6G  /tank/subvol-163-disk-0
tank/subvol-167-disk-0  3.64G  16.4G  3.64G  /tank/subvol-167-disk-0
tank/subvol-170-disk-0  2.68G  5.32G  2.68G  /tank/subvol-170-disk-0
tank/templates          1.79G  17.2T  1.79G  /tank/templates
tank/vm-133-disk-0      16.3G  17.3T  8.47G  -
```

Pool composition: single `raidz1-0` vdev with three drives. 3.64 GB
host-side dataset for CT167 jellyfin-hw, 2.68 GB for CT170 authentik,
12.6 GB for CT163 raffle-raptor-dev, 8.47 GB for VM133 nagios. Bulk
data: 146 G media library, 635 G Proxmox backups.

---

## Proxmox storage view

```
$ pvesm status
Name                  Type     Status     Total (KiB)      Used (KiB) Available (KiB)        %
local                  dir     active        70892712        11739180        55506660   16.56%
local-lvm          lvmthin     active       163442688       124788492        38654195   76.35%
tank-backups           dir     active     19183166336       666209408     18516956928    3.47%
tank-templates         dir     active     18518836992         1880064     18516956928    0.01%
tank-vmdata        zfspool     active     19375390815       858433887     18516956928    4.43%
```

---

## Guests

```
$ qm list
      VMID NAME                 STATUS     MEM(MB)    BOOTDISK(GB) PID
       120 media-stack          running    8192              40.00 1791
       122 home-assistant       running    4096              48.00 2931241
       133 nagios               running    2048              16.00 55488
       171 tailscale-gateway    running    1024              16.00 1989

$ pct list
VMID       Status     Lock         Name
128        running                 couchdb
153        running                 adguard
154        running                 nginx-proxy-manager
156        running                 apt-cacher-ng
157        running                 freshrss
158        running                 netalertx
159        running                 healthchecks
160        running                 dashboard
161        running                 static-sites
162        running                 browser
163        running                 raffle-raptor-dev
164        running                 organizr
166        running                 heimdall
167        running                 jellyfin-hw
170        running                 authentik
```

All 4 VMs and 15 LXCs running.

---

## Storage location of each guest, at baseline

| VMID | Name | Storage | Notes |
|---|---|---|---|
| 120 | media-stack | local-lvm (rootfs scsi0, 40 G), tank virtiofs (media, downloads) | virtiofs0/1 mappings to `/tank/media` and `/tank/downloads` |
| 122 | home-assistant | **local-lvm** (scsi0, 48 G) | Drift candidate — 67% thin alloc but only ~6.75 G real |
| 133 | nagios | tank-vmdata (scsi0, 16 G) | Moved from local-lvm |
| 171 | tailscale-gateway | local-lvm (16 G) | |
| 128 | couchdb | local-lvm (8 G) | |
| 153 | adguard | local-lvm (8 G) | |
| 154 | nginx-proxy-manager | **local-lvm** (16 G) | **96.13% used — drift candidate** |
| 156 | apt-cacher-ng | local-lvm (8 G) | |
| 157 | freshrss | local-lvm (8 G) | |
| 158 | netalertx | local-lvm (8 G) | |
| 159 | healthchecks | local-lvm (8 G) | |
| 160 | dashboard | local-lvm (8 G) | |
| 161 | static-sites | local-lvm (8 G) | |
| 162 | browser | local-lvm (8 G) | |
| 163 | raffle-raptor-dev | tank-vmdata (40 G) | Moved from local-lvm |
| 164 | organizr | local-lvm (8 G) | |
| 166 | heimdall | local-lvm (8 G) | |
| 167 | jellyfin-hw | tank-vmdata (20 G) | Privileged LXC, GPU device passthrough, /tank/media bind-mount |
| 170 | authentik | tank-vmdata (8 G) | Moved from local-lvm |

---

## Things to verify after power-on

1. `tank` pool comes up `ONLINE` with the same three rotational members and `errors: No known data errors`. The new SSDs must NOT have been auto-imported into `tank` — they should appear as untouched block devices.
2. `pve-data` thin pool data_percent ≈ 76% (should not change from a clean shutdown).
3. NVMe enumeration unchanged: `nvme0n1` with `nvme0n1p1` (BIOS), `nvme0n1p2` (EFI), `nvme0n1p3` (LVM PV).
4. All 4 VMs and 15 LXCs auto-start and reach `running`.
5. Spot checks (rerun the same set this baseline used):
   - `dig +short @10.20.30.53 heimdall.laxdog.uk` → `10.20.30.154`
   - `curl -sk https://heimdall.laxdog.uk/` → 200
   - `curl -sk https://jellyfin.laxdog.uk/` → 200
   - `curl -sk https://auth.laxdog.uk/` → 302
6. Two new block devices visible — likely `/dev/sdd` and `/dev/sde`, ~500 GB each.
