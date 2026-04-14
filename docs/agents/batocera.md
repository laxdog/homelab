# Batocera Agent

## Status
INACTIVE — repo docs are out of date. Hardware was set up manually. Agent needs to be restarted fresh when work resumes.

## Known state
- IP: 10.20.30.212
- Connected to CRT display
- Setup was done manually — repo does not fully reflect live state

## What's in the repo
~15 commits of CRT/VGA/GL debug and baseline work under `docs/batocera/`. Check `git log` for batocera-related commits. Current repo content is likely stale vs live state.

## When resuming
1. Start with a fresh audit of what's on the host
2. Compare against what's in the repo
3. Establish what needs Ansible or scripts to be reproducible
4. Do not trust existing repo docs as accurate

## Backlog

- [ ] Fresh audit of batocera host vs repo
  - Context: host was manually configured, repo is stale. Need to reconcile before any further work.
  - Effort: medium
  - Added: 2026-04-14

- [ ] Batocera debug screenshot cleanup
  - Context: `docs/batocera/.../glxgears.png` leftover debug file. Trivially removable.
  - Effort: low
  - Added: 2026-04-14
