# Monitoring

Source of truth: `config/homelab.yaml`.

## Nagios host
- VM: `nagios` (`10.20.30.133`, Tailscale: `100.120.89.28`)
- Internal URL: `https://nagios.laxdog.uk`
- External URL: `https://nagios.lax.dog` (behind Authentik)
- SSH: `ssh ubuntu@100.120.89.28` (via Tailscale)
- Config: `/usr/local/nagios/etc/objects/homelab.cfg` + `remote-nodes.cfg`
- 16 hosts monitored, ~142 service checks

## Remote node monitoring
- Both remote nodes monitored via Tailscale IPs from VM133
- rr-node-staging-local (100.88.35.124): PING, SSH, Disk, Tailscale, CPU Temp, NTP
- rr-node-prod-mums (100.118.218.126): PING, SSH, Disk, Tailscale, CPU Temp, NTP
- Check scripts: `/usr/local/nagios/libexec/check_remote_*.sh`
- Config: `/usr/local/nagios/etc/objects/remote-nodes.cfg`

## Observability (Prometheus + Grafana)
- CT172 at 10.20.30.172
- Grafana: https://grafana.laxdog.uk
- Prometheus: https://prometheus.laxdog.uk
- Scrapes RR prod + staging /statusz (35 metrics per env)
- 5 dashboards: Worker Health, Phase Timing, Playwright, Parse & Issues, Infra Health
- Complements Nagios — Prometheus provides trending/history, Nagios provides alerting

## What Nagios checks
- Host `PING` for all hosts in `config.nagios.hosts`.
- Host `SSH` for hosts where `check_ssh: true`.
- Service `TCP` checks for each entry in `config.validation.service_ports`.
- Service `DNS` checks from `config.nagios.dns_checks`.
- Service `DNS` checks for all `config.adguard.rewrites`.
- Service `HTTP` checks for all NPM hosts with `monitor_http: true`.
- Service `HTTP Domain` checks for explicit domains in `config.nagios.http_domain_checks` (including non-NPM endpoints), e.g. `/healthz` probes.
- Service `HTTP Backend` checks for direct backend endpoints in `config.nagios.http_backend_checks` (used for backend-layer detection independent of NPM path checks).
- Service `RaffleRaptor Healthz` and `RaffleRaptor Statusz` checks from `config.nagios.raffle_raptor_checks` using `/usr/local/nagios/libexec/check_raffle_raptor.py`.
  These checks implement the contract in `/home/mrobinson/source/raffle-raptor/docs/monitoring.md`.

## Alerting
- Notifications are sent to Discord via `discord_webhook` (vault secret).
- Script path: `/usr/local/bin/nagios-discord.sh`.

## Validation coverage
`scripts/run.py validate --mode full` includes Nagios-specific checks for:
- service active state (`nagios`)
- core version matches `config.nagios.core_version`
- full config syntax check: `nagios -v /usr/local/nagios/etc/nagios.cfg`
- web endpoint reachability (`/` redirect and `/nagios/cgi-bin/status.cgi`)
- rendered object count parity with `config/homelab.yaml` for host definitions
- rendered object count parity for `PING`, `SSH`, `TCP`, `DNS`, and `HTTP` service definitions

## Useful commands
- Apply only Nagios role: `ansible-playbook ansible/playbooks/guests.yml -l nagios`
- Fast validate: `scripts/run.py validate`
- Full validate: `scripts/run.py validate --mode full`
- Inspect generated object file: `ssh root@10.20.30.133 'sed -n "1,220p" /usr/local/nagios/etc/objects/homelab.cfg'`
- Manual plugin examples:
  - `ssh root@10.20.30.133 '/usr/local/nagios/libexec/check_raffle_raptor.py --mode healthz --base-url https://raffle-raptor-dev.lax.dog --target-ip 10.20.30.154'`
  - `ssh root@10.20.30.133 '/usr/local/nagios/libexec/check_raffle_raptor.py --mode statusz --base-url https://raffle-raptor-dev.lax.dog --target-ip 10.20.30.154 --success-fresh-minutes 15'`
