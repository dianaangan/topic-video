# Quick testing guide

Open http://127.0.0.1:8000 with the server running. Refresh the page to load the latest changes.

## Main sample (16 seconds)

Topic:

```text
Healthy morning routine
```

Scene captions (paste all three lines):

```text
Drink a glass of water.
Stretch for five minutes.
Choose one priority for today.
```

Or click **Use sample** to fill these inputs automatically. Choose **Ocean**, leave music enabled, and click **Generate video**. Expect four scenes and a 16-second, 720p MP4:

- 00:00–00:04: topic title, Scene 01 / 04.
- 00:04–00:08: water caption, Scene 02 / 04.
- 00:08–00:12: stretch caption, Scene 03 / 04.
- 00:12–00:16: priority caption, Scene 04 / 04.

The topic title counts as a scene. The on-video clock is elapsed time / total duration. It uses whole elapsed seconds, so the last frame reads 00:15 / 00:16; the video ends at 16 seconds. The browser player also shows its own playback time.

Play the video, seek to 9 seconds, and check that the stretch caption appears. Download the MP4 and open it in a video player; its captions and timing should match the preview. The soft synthesized soundtrack should be audible with your player unmuted.

## Other useful checks

- **Automatic outline:** enter `Learning Python`, leave captions blank. Expect five scenes and 20 seconds. Captions are a general template.
- **Music disabled:** use the main sample, uncheck music, choose Sunset. Expect 16 seconds with no audio stream.
- **Maximum scenes:** enter six short caption lines. Expect seven scenes and 28 seconds.
- **Validation:** enter seven caption lines, or a caption longer than 180 characters. Expect a clear error and no render. A topic of one or two characters is blocked by the form.
- **Recovery:** after a validation error, correct the input and generate again. Expect normal completion.
- **Refresh recovery:** refresh while rendering. Expect the settings to remain filled and progress to resume. After completion, the preview should also survive a refresh.
- **Previous video:** generate another video. The previous preview and download remain available while the new one renders.
- **Timeline:** open Scene timeline below the preview. Its times and captions should match the video.
- **Small screen:** narrow the browser window. Expect the form and preview to stack with no sideways scrolling.
- **Connection failure:** stop the server, then click Generate. Expect a clear connection error and an enabled Generate button. Restart the server and reload to continue.

## Recording a short demo

Show the main sample input, click Generate, wait for “Your video is ready,” play it, seek to 9 seconds, and download. Explain that each scene lasts four seconds and the title is the first scene. The render waiting time is separate from the MP4's duration.

## Automated checks

From the project folder, with a normal installed virtual environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe tests/check_app.py
```

The second command requires the server running and idle. It generates two videos, replaces `sample.mp4` with the main sample, and stores a maximum-length test in `output/`. It checks actual encoded timing, scene boundary frames, audio settings, validation, overlapping jobs, downloads, and seeking responses. A failure exits with an error.

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.
