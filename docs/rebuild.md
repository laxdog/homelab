# Rebuild

## Minimal manual bootstrap
1. Install Proxmox.
2. Set management IP to `10.20.30.46/24` and enable SSH access.
3. Ensure your SSH public key is installed for `root`.

## Repo-driven rebuild
1. Install Python deps: `pip install -r scripts/requirements.txt`
2. Run orchestrator: `scripts/run.py apply`
2. Host baseline is applied first, then guests.

Any remaining manual steps should be documented here.
