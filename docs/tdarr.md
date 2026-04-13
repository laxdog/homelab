# Tdarr

Tdarr runs on VM `120` as part of the existing `arr` compose project.

## Runtime Layout
- Compose project: `/opt/media-stack/arr/docker-compose.yaml`
- Server container: `tdarr`
- Node container: `tdarr-node`
- Web UI: `http://10.20.30.120:8265`
- Server comms: `10.20.30.120:8266`
- Appdata:
  - `/opt/media-stack/appdata/tdarr/server`
  - `/opt/media-stack/appdata/tdarr/configs`
  - `/opt/media-stack/appdata/tdarr/logs`
- Data mounts:
  - `/srv/data/media` -> `/media`
  - `/srv/data/tdarr/cache` -> `/temp`

## Deployment Shape
- `tdarr` server and `tdarr-node` are both in the `arr` compose project.
- The node is CPU-only.
- Current worker limits:
  - `transcodecpuWorkers=1`
  - `healthcheckcpuWorkers=1`
  - `transcodegpuWorkers=0`
  - `healthcheckgpuWorkers=0`
- Current runtime node ID on VM `120`: `QyKZlyoUY`
- Current node name: `MediaStackTdarrCpuNode`

## Current Watch Scope
- Real media roots remain:
  - TV: `/media/tv`
  - Movies: `/media/movies`
- Guarded test libraries currently configured:
  - `tdarr_test_mr_robot_s2`
    - folder: `/media/tv/Mr. Robot/Season 2`
    - purpose: full-library discovery only, not broad automatic replacement
  - `tdarr_test_mr_robot_sample`
    - folder: `/media/tv/Tdarr Samples/Season 1`
    - purpose: bounded validation of the first-pass policy
  - `tdarr_test_av1_sample`
    - folder: `/media/tv/Tdarr Samples/Season 1/AV1`
    - purpose: isolated AV1 -> HEVC validation
  - `tdarr_test_dv_sample`
    - folder: `/media/tv/Tdarr Samples/Season 1/DV`
    - purpose: isolated Dolby Vision / HEVC behavior validation

## Current Policy
- Container target: `mkv`
- Video policy:
  - convert `h264` -> `hevc`
  - skip `av1` for now
  - skip existing `hevc`, including current Dolby Vision samples, for now
  - leave `vp9` alone for now
- Encoder:
  - `libx265`
  - preset `medium`
  - CRF `21`
- Resolution:
  - preserve source resolution
- Audio:
  - copy original audio
- Subtitles:
  - copy embedded subtitles
- Stream cleanup:
  - reorder streams so video is first
  - remove unwanted image streams
- Replacement guardrail:
  - only keep a transcode result if it is at most `85%` of the original size
  - that is the current repo/runtime implementation of the “must save at least 15%” rule

## Active Classic Plugin Stack
1. `Tdarr_Plugin_00td_filter_by_codec`
   - `codecsToProcess=h264`
2. `Tdarr_Plugin_lmg1_Reorder_Streams`
3. `Tdarr_Plugin_MC93_MigzImageRemoval`
4. `Tdarr_Plugin_vdka_Tiered_CPU_CRF_Based_Configurable`
5. `Tdarr_Plugin_a9he_New_file_size_check`

## How To Operate

### Start / Restart
On VM `120`:

```bash
cd /opt/media-stack/arr
sudo docker compose up -d tdarr
sudo docker compose up -d tdarr-node
```

Use that order. `tdarr-node` shares `network_mode: service:tdarr`, so starting the node before the server can fail.

### Stop

```bash
cd /opt/media-stack/arr
sudo docker compose stop tdarr-node tdarr
```

### Pause Processing
Preferred: pause the live node via API using the runtime node ID:

```bash
python3 - <<'PY'
import json, urllib.request
payload = {
    "data": {
        "nodeID": "QyKZlyoUY",
        "nodeUpdates": {"nodePaused": True},
    }
}
req = urllib.request.Request(
    "http://127.0.0.1:8265/api/v2/update-node",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)
print(urllib.request.urlopen(req).read().decode())
PY
```

To resume, set `nodePaused` to `False`.

Important:
- use the live runtime node ID from `GET /api/v2/get-nodes`
- do not use the persisted human node name as the `nodeID`

### Inspect Runtime State

```bash
curl -fsS http://127.0.0.1:8265/api/v2/status
curl -fsS http://127.0.0.1:8265/api/v2/get-nodes
sudo docker compose -f /opt/media-stack/arr/docker-compose.yaml ps tdarr tdarr-node
sudo docker logs --tail 120 tdarr
sudo docker logs --tail 120 tdarr-node
```

### Review Results
- Tdarr SQL DB:
  - `/opt/media-stack/appdata/tdarr/server/Tdarr/DB2/SQL/database.db`
- Key tables:
  - `librarysettingsjsondb`
  - `filejsondb`
  - `stagedjsondb`
  - `jobsjsondb`
- Cache work dirs:
  - `/srv/data/tdarr/cache`

### Add / Remove Test Files
- Test samples should stay under:
  - `/srv/data/media/tv/Tdarr Samples/Season 1`
- Keep them isolated from normal shows/movies so test replacements are obvious.
- The current Mr. Robot sample was created from a real episode with stream copy and a 120-second clip.
- Current additional downloaded validation samples:
  - `/srv/data/media/tv/Tdarr Samples/Season 1/AV1/Test Jellyfin 1080p AV1 10bit 3M.mp4`
  - `/srv/data/media/tv/Tdarr Samples/Season 1/DV/Test Jellyfin 1080p DV P8.1.mp4`

### Recover From A Bad Rule
- Pause the node first.
- Review `stagedjsondb` and cached outputs under `/srv/data/tdarr/cache`.
- Because guarded test mode leaves results staged for review, do not accept or replace blindly.
- If a library scan creates stale media paths for playback clients after a replacement, trigger a targeted Jellyfin refresh against the affected series or library path.

## Current Guarded Mode
- Tdarr is up.
- The CPU node is currently paused after the first successful sample run.
- No broad automatic replacement has been enabled yet.
- Current validation status:
  - AVC/H.264 -> HEVC on the Mr. Robot sample is working and staged cleanly.
  - AV1 sample is now skipped cleanly as `Not required`.
  - HEVC/DV sample is now skipped cleanly as `Not required`.
- Operational conclusion:
  - safe for AVC-only guarded promotion later
  - AV1 remains deferred because the earlier `libx265 CRF 21` path expanded the sample badly
  - DV/HEVC remains deferred until there is a separate compatibility-aware branch
  - keep the node paused until AV1/DV handling is adjusted
