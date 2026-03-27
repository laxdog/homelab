## Batocera VGA libVLC suppression test

Date: 2026-03-27
Host: `batocera-crt1` (`10.20.30.206`)

### Hypothesis

The black VGA-only EmulationStation session is primarily triggered by the theme/libVLC video-preview path.

### Evidence used before the test

- `es-theme-carbon` is the only installed theme.
- Active user config points at `es-theme-carbon`.
- Theme XML contains multiple `<video>` elements in normal views, including:
  - `views/detailed.xml`
  - `views/gamecarousel.xml`
  - `subsets/gameinfobar.xml`
  - `subsets/grid/previewbar.xml`
  - `subsets/systembackground/video.xml`
  - `subsets/systembackground/smallvideo.xml`
- Batocera ES source shows theme `<video>` elements instantiate `VideoVlcComponent`.
- Pre-test framebuffer capture: `before-libvlc-suppress.png`

### Test performed

One bounded reversible suppression test:

1. Backed up every theme XML file containing `<video name=`.
2. Removed all `<video ...>...</video>` blocks from the active `es-theme-carbon` XML files on-box.
3. Saved overlay.
4. Rebooted into the stock wrapper-managed VGA session.
5. Captured:
   - framebuffer
   - process tree
   - `lsof` for live ES process
   - display/X logs
6. Reverted the theme changes from the backup and requested another reboot.

### Results

- Post-test framebuffer capture `after-libvlc-suppress.png` remained effectively black.
- Pixel summary:
  - before: 307160 black pixels, 40 white pixels
  - after: 307140 black pixels, 60 white pixels
- After reboot, stock session still started:
  - `openbox`
  - `emulationstation-standalone`
  - `dbus-launch`
  - `emulationstation --exit-on-reboot-required --windowed`
- Live `lsof` for ES still showed the large VLC plugin stack loaded, including:
  - `libvlc`
  - `libglx_plugin`
  - `libgles2_plugin`
  - `libegl_x11_plugin`
  - many other VLC plugins
- `display.log` still showed normal DP-1 session selection at `640x480 @ 60`

### Interpretation

This test weakens the hypothesis that theme video preview activation is the primary trigger for the black screen.

More precise reading:

- removing theme `<video>` elements did not make the framebuffer visible
- removing theme `<video>` elements did not stop ES from loading the VLC plugin stack

So the remaining likely fault is deeper in ES runtime behavior, not just theme video previews.

### Cleanup / live state

- The temporary no-video theme override was reverted from backup.
- A reboot was requested after revert.
- At the time this summary was written, the host had dropped off-network again after that reboot request, so restored post-revert runtime was not yet re-verified remotely.
