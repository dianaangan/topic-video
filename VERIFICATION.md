# Verification

Rechecked on Windows with Python 3.12, Pillow 12.3.0, and imageio-ffmpeg 0.6.0.

- Five unit tests pass, covering input validation, caption preservation, default scene count, clock formatting, and caption fitting (including 180 wide characters).
- End-to-end checks pass through the running HTTP API.
- Main sample: exactly 16 seconds, four scenes, 1280×720, 24 fps, H.264 video and AAC audio.
- Decoded frames match expected captions, scene counters, and clocks at 0, 3.9, 4.1, 8.1, and 12.1 seconds.
- Maximum test: exactly 28 seconds, seven scenes, six 180-character captions, music disabled; no audio stream.
- Both complete MP4s decode without errors.
- MP4 download returns HTTP 200; byte-range and suffix requests return correct data with HTTP 206; invalid ranges return HTTP 416.
- Invalid inputs return HTTP 400, overlapping renders return HTTP 409, cross-origin render requests return HTTP 403, and path traversal attempts return HTTP 404.
- Browser generation, preview, and download were checked. Actual playback reports a 16-second duration, 1280-pixel video width, advancing playback time, and no media error. The updated video frame was visually inspected.
- UI redesign checked at desktop, 390px phone, and 768px tablet widths; no horizontal page overflow.
- Browser tests passed for empty topic, seven caption lines, 181-character captions, error correction using the sample button, saved draft restoration, and refresh during rendering.
- Expanded scene timeline matches the four-scene sample. Browser playback and keyboard seeking work. Download MP4 saves an actual file to Downloads.
- Stopping the server produces a clear connection error, restores the Generate button, and preserves the previous preview.
- JavaScript syntax check passes. No browser warning/error logs during normal playback.

Run `tests/check_app.py` to repeat the API/encoder checks with the server running and idle. Read `TESTING.md` for manual sample inputs.

Not verified: non-Windows installation, screen-reader usage, or non-Latin typography. Public hosting is outside this local trial's scope.
