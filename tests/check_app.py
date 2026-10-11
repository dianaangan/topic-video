"""Repeatable end-to-end check against the running local app (about 30 seconds)."""
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'.packages'), str(ROOT)]
import imageio_ffmpeg
from PIL import Image, ImageChops, ImageStat
from generator import frame

BASE = 'http://127.0.0.1:8000'


def request(path, data=None, headers=None):
    payload = json.dumps(data).encode() if data is not None else None
    req = Request(BASE+path, data=payload, headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, response.headers, response.read()
    except HTTPError as error:
        return error.code, error.headers, error.read()


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    print('PASS:', description, flush=True)


def generate(data, filename):
    status, _, body = request('/api/jobs', data)
    check(status == 202, 'job accepted')
    job_id = json.loads(body)['id']
    check(request('/api/jobs', data)[0] == 409, 'overlapping render rejected')
    deadline = time.monotonic()+120
    while time.monotonic() < deadline:
        status, _, body = request('/api/jobs/'+job_id)
        job = json.loads(body)
        check(status == 200, 'job status available') if job.get('status') == 'failed' else None
        if job.get('status') == 'failed':
            raise AssertionError(job['error'])
        if job.get('status') == 'done':
            break
        time.sleep(.5)
    else:
        raise TimeoutError('Render exceeded 120 seconds.')
    expected = 4*(1+len(data['captions']))
    check(job['duration'] == expected and job['progress'] == 100, f'duration {expected}s and progress 100%')
    check(job['timeline'] == [{'scene': i+1, 'start': i*4, 'end': (i+1)*4} for i in range(len(job['scenes']))], 'scene timeline has exact 4-second boundaries')
    status, _, video = request(job['url'])
    check(status == 200 and video[4:8] == b'ftyp', 'MP4 download works')
    (ROOT/filename).write_bytes(video)
    status, headers, part = request(job['url'], headers={'Range': 'bytes=0-99'})
    check(status == 206 and part == video[:100] and headers['Content-Range'].startswith('bytes 0-99/'), 'browser seeking byte range works')
    check(request(job['url'], headers={'Range': 'bytes=999999999-'})[0] == 416, 'invalid byte range rejected')
    check(request(job['url'], headers={'Range': 'bytes=-100'})[2] == video[-100:], 'suffix byte range works')
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    decoded = subprocess.run([exe, '-hide_banner', '-i', str(ROOT/filename), '-f', 'null', '-'], capture_output=True, text=True)
    check(decoded.returncode == 0, 'entire MP4 decodes without errors')
    check(f'Duration: 00:00:{expected:02d}.00' in decoded.stderr and '1280x720' in decoded.stderr and '24 fps' in decoded.stderr, 'encoded duration, resolution, and frame rate match')
    check(('Audio: aac' in decoded.stderr) == data['music'], 'audio stream matches music setting')
    if filename == 'sample.mp4':
        # Decode immediately on both sides of the first scene boundary.
        for t, scene in [(0, 0), (3.9, 0), (4.1, 1), (8.1, 2), (12.1, 3)]:
            raw = subprocess.run([exe, '-loglevel', 'error', '-ss', str(t), '-i', str(ROOT/filename), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
            decoded_frame = Image.frombytes('RGB', (1280,720), raw)
            expected_frame = frame(job['scenes'][scene], scene, len(job['scenes']), (t%4)/4, data['theme'])
            delta = ImageStat.Stat(ImageChops.difference(decoded_frame, expected_frame).crop((76, 136, 1204, 600)))
            check(max(delta.mean) < 3, f'caption, scene counter, and clock match at {t}s')
        subprocess.run([exe, '-y', '-loglevel', 'error', '-ss', '4.1', '-i', str(ROOT/filename), '-frames:v', '1', str(ROOT/'sample-frame.png')], check=True)
    return job


if __name__ == '__main__':
    check(request('/')[0] == 200, 'interface loads')
    check(request('/styles.css')[0] == 200 and request('/app.js')[0] == 200, 'UI stylesheet and script load')
    for bad in [{'topic': 'x'}, {'topic': 'Valid', 'captions': ['x']*7}, {'topic': 'Valid', 'theme': []}]:
        check(request('/api/jobs', bad)[0] == 400, 'invalid input rejected')
    check(request('/api/jobs', {'topic': 'Valid'}, {'Origin': 'https://example.com'})[0] == 403, 'cross-origin render rejected')
    check(request('/videos/../../README.md')[0] == 404, 'video route blocks path traversal')
    generate({'topic': 'Healthy morning routine', 'captions': ['Drink a glass of water.', 'Stretch for five minutes.', 'Choose one priority for today.'], 'theme': 'ocean', 'music': True}, 'sample.mp4')
    generate({'topic': 'Maximum-length test', 'captions': ['W'*180]*6, 'theme': 'ink', 'music': False}, 'output/maximum-test.mp4')
    print('All end-to-end checks passed.')
