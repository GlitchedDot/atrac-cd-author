# UI mock — "burn-aero" (Claude, 2026-10-23)

A single-file HTML mock of the ATRAC CD Author, made by Claude in Lola's free
chat and shared as `burn-aero.zip`. Kept at `~/workspace/user/files/burn-aero/burn-aero.html`
(CP's copy carries the custom-wallpaper addition below).

- Windows Aero glass styling (Vista/7): translucent blurred window, generated
  SVG ribbon wallpapers behind the glass, Segoe UI, SonicStage-style
  Library → Disc transfer layout with a live capacity bar.
- **Wallpapers:** a random generated palette on every page load, switchable in
  the Wallpaper menu. **Custom picture support added by CP (2026-10-23, Lola's
  ask):** "Your own picture…" in the same menu opens a file picker; the image
  becomes the backdrop (cover-fit), is downscaled to ≤1920 px, and is saved in
  localStorage so it returns on later visits; picking a generated palette
  switches back without deleting the saved picture. Lola: the wallpaper
  behavior is "something to add" to the real app.
- Mock numbers, NOT pipeline numbers — when this face is wired to the real
  core, fix: (1) the bitrate list (mock: 64/105/132/256/352; real: the measured
  9-rung ladder 48–352.8k), (2) size math (mock ignores the +1,120 B/track and
  the session overhead), (3) there is no Groups UI yet — groups are mandatory
  in the design.
