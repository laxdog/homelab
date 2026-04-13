# Tdarr Validation Report — 2026-04-07

## Scope
- Host: `media-stack` VM `120`
- Tdarr server/node running in the `arr` compose project
- Current playback target to keep in mind during validation: Jellyfin on CT `167`
- Validation target for this pass:
  - local Mr. Robot content under `/srv/data/media/tv`
  - initial bounded sample only
  - one isolated AV1 sample
  - one isolated Dolby Vision sample

## Libraries Used
- Discovery library:
  - `tdarr_test_mr_robot_s2`
  - folder: `/media/tv/Mr. Robot/Season 2`
  - result: 12 source files discovered
- Validation library:
  - `tdarr_test_mr_robot_sample`
  - folder: `/media/tv/Tdarr Samples/Season 1`
  - result: 1 isolated sample file discovered
- AV1 validation library:
  - `tdarr_test_av1_sample`
  - folder: `/media/tv/Tdarr Samples/Season 1/AV1`
  - result: 1 isolated sample file discovered
- DV validation library:
  - `tdarr_test_dv_sample`
  - folder: `/media/tv/Tdarr Samples/Season 1/DV`
  - result: 1 isolated sample file discovered

## Samples Used
- Source episode:
  - `/media/tv/Mr. Robot/Season 2/Mr.Robot.S02E07.eps2.5.h4ndshake.sme.1080p.AMZN.WEB-DL.DDP.5.1.H.264.-EDGE2020.mkv`
- Test sample created from that source:
  - `/media/tv/Tdarr Samples/Season 1/Mr.Robot.S02E07.sample.120s.mkv`
- Downloaded AV1 sample:
  - `/media/tv/Tdarr Samples/Season 1/AV1/Test Jellyfin 1080p AV1 10bit 3M.mp4`
- Downloaded DV sample:
  - `/media/tv/Tdarr Samples/Season 1/DV/Test Jellyfin 1080p DV P8.1.mp4`

## Working Policy Exercised
- Filter by codec:
  - only process `h264`
- Reorder streams
- Remove image streams
- Transcode selected `h264` video to `libx265`
- Preserve resolution
- Copy audio
- Copy subtitles
- Keep `mkv`
- Require the output to be `<= 85%` of the original size

## Result Summary
- Files processed:
  - 3 bounded sample jobs
- Files skipped:
  - 11 Mr. Robot full-episode files explicitly left `Not required` during guarded testing
- Files failed / rejected by guardrail:
  - 2 sample jobs
- Files cancelled:
  - 1 earlier full-episode dry run on `S02E01` was cancelled because the full 1080p CPU transcode was too slow for a practical validation loop

## Sample Outcome
- Input:
  - container: `mkv`
  - video: `h264`
  - audio: `eac3 5.1`
  - subtitles: embedded `subrip (eng)`
  - size: `105,927,195` bytes (`101.02 MiB`)
- Tdarr staged output:
  - container: `mkv`
  - video: `hevc`
  - audio: `eac3 5.1` copied
  - subtitles: embedded `subrip (eng)` preserved
  - size: `26,441,373` bytes (`25.22 MiB`)
- Savings:
  - absolute: `79,485,822` bytes
  - percentage: `75.04%`
- Time taken:
  - about `183.8s` from job start to staged cache creation

## AV1 Sample Outcome
- Input:
  - path: `/media/tv/Tdarr Samples/Season 1/AV1/Test Jellyfin 1080p AV1 10bit 3M.mp4`
  - container: `mp4`
  - video: `av1 Main 10`
  - resolution: `1920x1080`
  - audio: none
  - subtitles: none
  - size: `11,215,840` bytes (`10.70 MiB`)
- Outcome:
  - under the refined policy, the AV1 sample is now skipped cleanly as `Not required`
  - no new output file is produced
- Conclusion:
  - earlier validation proved the AV1 -> HEVC path would grow this sample by `127.12%`
  - AV1 is now intentionally deferred instead of being sent through the transcode path

## Dolby Vision Sample Outcome
- Input:
  - path: `/media/tv/Tdarr Samples/Season 1/DV/Test Jellyfin 1080p DV P8.1.mp4`
  - container: `mp4`
  - video: `hevc Main 10`
  - HDR/DV state:
    - `Dolby Vision Profile 8`
    - `HDR10 compatible`
    - BT.2020 / PQ metadata present
  - resolution: `1920x1080`
  - audio: none
  - subtitles: none
  - size: `48,198,953` bytes (`45.97 MiB`)
- Outcome:
  - under the refined policy, the DV sample is now skipped cleanly as `Not required`
  - source file remains untouched
  - no replacement candidate is created
- Conclusion:
  - DV is safely deferred for now
  - a separate compatibility-aware branch is still needed later if DV normalization becomes a goal

## Guardrail Outcome
- The 15% replacement rule worked.
- The staged log recorded:
  - `New file has size 25.216 MB which is 24% of original file size: 101.020 MB`
- That is well inside the configured `upperBound=85` threshold.

## Compatibility / Stream Preservation
- Codec/container change performed:
  - `H.264 MKV` -> `HEVC MKV`
- Audio handling:
  - original `E-AC-3 5.1` preserved
- Subtitle handling:
  - embedded English `SubRip` subtitle preserved
- Resolution handling:
  - preserved at `1920x1080`
- Chapters:
  - not present in this sample
- AV1-specific action:
  - current policy skips AV1 by design
- DV-related action:
  - exercised on an isolated `HEVC/DV P8.1` sample
  - current policy now skips HEVC/DV cleanly by design

## Current State After Validation
- Tdarr server is up.
- Tdarr node is up.
- Tdarr node is paused again after validation.
- The validated output remains in Tdarr staged/manual-review state.
- No production media file was auto-replaced in this pass.

## Jellyfin Caveat
- Jellyfin library refresh behavior is a known operational concern when files are replaced.
- A previous Mr. Robot playback issue came from stale Jellyfin paths after file changes, not from media corruption.
- If Tdarr replacements are later accepted into the live library, plan to watch Jellyfin refresh behavior and trigger a targeted refresh if paths or playback look stale.

## Recommendation
- Classification:
  - safe for AVC-only guarded promotion later
- Keep the node paused.
- Not ready for broad unattended replacement of all media or new downloads yet.
- Reason:
  - the AVC path validated cleanly on real local content and remains the reference staged result
  - AV1 now skips cleanly by design
  - DV/HEVC now skips cleanly by design
  - a dedicated AV1 policy and a dedicated DV compatibility path are still deferred
