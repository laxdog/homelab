# Monitoring

Source of truth: `config/homelab.yaml`.

## Nagios host
- VM: `nagios` (`10.20.30.133`)
- Internal URL: `https://nagios.laxdog.uk`
- External URL: `https://nagios.lax.dog` (behind Authentik)

## What Nagios checks
- Host `PING` for all hosts in `config.nagios.hosts`.
- Host `SSH` for hosts where `check_ssh: true`.
- Service `TCP` checks for each entry in `config.validation.service_ports`.
- Service `DNS` checks from `config.nagios.dns_checks`.
- Service `DNS` checks for all `config.adguard.rewrites`.
- Service `HTTP` checks for all NPM hosts with `monitor_http: true`.
- Service `HTTP Domain` checks for explicit domains in `config.nagios.http_domain_checks` (including non-NPM endpoints), e.g. `/healthz` probes.

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
