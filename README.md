bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/misc/post-pve-install.sh)"
# Reboot
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/misc/add-lxc-iptag.sh)"

apt-get update && apt-get install parted tmux vim btop htop fio

# Proxmox disk setup
lsblk # Search for the SSDs
# This next part is only if the sizes differ
parted /dev/sda
mklabel gpt
mkpart primary 1MiB 512110MB
quit

# Create the flash pool
zpool create -o ashift=12 flash raidz /dev/sda1 /dev/sdb /dev/sdc # /dev/sda1 if there were partitions created above
zpool status

# Tune the pool
zfs set compression=lz4 flash
zpool set autotrim=on flash
zfs set atime=off flash
zfs set sync=standard flash
zfs set primarycache=all flash
zfs set recordsize=16K flash

# Create the 'tank' storage pool
for disk in /dev/sde /dev/sdf /dev/sdg /dev/sdh /dev/sdi /dev/sdj /dev/sdk /dev/sdl; do
    wipefs -a $disk
    zpool labelclear -f $disk
done

zpool create -o ashift=12 tank raidz2 /dev/sde /dev/sdf /dev/sdg /dev/sdh /dev/sdi /dev/sdj /dev/sdk /dev/sdl
zfs set compression=lz4 tank
zfs set atime=off tank
zfs set recordsize=1M tank
zpool status tank

zfs create tank/backups


# Add the pools to proxmox
Add this to /etc/pve/storage.cfg
dir: tank
        path /tank/backups
        content backup

zfspool: flash
        pool flash
        content rootdir,images

# Restart daemons
systemctl restart pvedaemon pveproxy

