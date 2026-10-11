"""Deterministic, offline video renderer. No network requests or shell commands."""
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave
from array import array
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

WIDTH, HEIGHT, FPS = 1280, 720, 24
SECONDS_PER_SCENE = 4
THEMES = {'ocean': ((12, 28, 44), (57, 211, 190)),
          'sunset': ((41, 22, 43), (255, 155, 94)),
          'ink': ((24, 26, 36), (157, 167, 255))}


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object.')
    topic = data.get('topic', '')
    if not isinstance(topic, str) or not 3 <= len(topic.strip()) <= 120:
        raise ValueError('Enter a topic between 3 and 120 characters.')
    captions = data.get('captions', [])
    if not isinstance(captions, list) or len(captions) > 6:
        raise ValueError('Use up to six captions.')
    if any(not isinstance(c, str) or not 1 <= len(c.strip()) <= 180 for c in captions):
        raise ValueError('Each caption must contain 1–180 characters.')
    theme = data.get('theme', 'ocean')
    if not isinstance(theme, str) or theme not in THEMES:
        raise ValueError('Choose a supported theme.')
    music = data.get('music', True)
    if not isinstance(music, bool):
        raise ValueError('Music must be true or false.')
    return topic.strip(), [c.strip() for c in captions], theme, music


def plan(topic, captions):
    # An honest template, not fabricated facts about arbitrary topics.
    return [topic] + (captions or [
        f'An introduction to {topic}',
        'Start with the basics. Focus on one clear idea.',
        'Choose a practical example and explore it step by step.',
        'Try it yourself. Notice what works and keep improving.'])


@lru_cache(maxsize=16)
def font(size):
    candidates = [os.getenv('VIDEO_FONT', ''), 'C:/Windows/Fonts/arial.ttf',
                  '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for path in candidates:
        if path and Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def timestamp(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f'{minutes:02d}:{seconds:02d}'


@lru_cache(maxsize=128)
def caption_layout(text):
    """Wrap by rendered width, including long words, and fit a fixed safe area."""
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    for size in (52, 48, 44, 40, 36, 32):
        face = font(size)
        lines, line = [], ''
        for char in ' '.join(text.split()):
            if draw.textlength(line + char, font=face) > 1128:
                # Prefer word boundaries, but split long unbroken words too.
                split = line.rfind(' ')
                if split > 0:
                    lines.append(line[:split])
                    line = line[split+1:] + char
                else:
                    lines.append(line)
                    line = char
            else:
                line += char
        lines.append(line.strip())
        wrapped = '\n'.join(lines)
        bounds = draw.multiline_textbbox((0, 0), wrapped, font=face, spacing=12)
        if bounds[2] - bounds[0] <= 1128 and bounds[3] - bounds[1] <= 350:
            return wrapped, face
    raise ValueError('Caption cannot fit the video layout. Please shorten it.')


def frame(text, index, count, progress, theme):
    base, accent = THEMES[theme]
    im = Image.new('RGB', (WIDTH, HEIGHT), base)
    draw = ImageDraw.Draw(im)
    # Slowly moving geometric artwork stays clear behind the captions.
    shift = int(progress * 100)
    for radius in range(390, 0, -8):
        factor = (1 - radius / 390) * .2
        color = tuple(int(b + (a-b)*factor) for b, a in zip(base, accent))
        draw.ellipse((890-radius+shift, 270-radius, 890+radius+shift, 270+radius), fill=color)
    draw.text((76, 60), 'TOPIC / VIDEO', font=font(22), fill=accent)
    draw.text((76, 136), f'Scene {index+1:02d} / {count:02d}', font=font(24), fill=(170, 184, 196))
    elapsed = (index + progress) * SECONDS_PER_SCENE
    draw.text((920, 136), f'{timestamp(elapsed)} / {timestamp(count * SECONDS_PER_SCENE)}',
              font=font(24), fill=(170, 184, 196))
    wrapped, face = caption_layout(text)
    draw.multiline_text((76, 235), wrapped, font=face, fill=(246, 247, 250), spacing=12)
    draw.rectangle((76, 630, 1204, 634), fill=(50, 62, 75))
    draw.rectangle((76, 630, 76+int(1128*(index+progress)/count), 634), fill=accent)
    draw.text((76, 660), 'A small idea. A clear story.', font=font(19), fill=(170, 184, 196))
    return im


def soundtrack(path, seconds):
    rate = 22050
    samples = array('h')
    for n in range(int(seconds*rate)):
        t = n/rate
        fade = min(1, t/1.5, (seconds-t)/1.5)
        value = sum(math.sin(2*math.pi*f*t) for f in (130.81, 164.81, 196)) / 3
        samples.append(int(1800*value*fade))
    with wave.open(str(path), 'wb') as out:
        out.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        out.writeframes(samples.tobytes())


def render(data, destination, update=lambda value: None):
    topic, captions, theme, music = validate(data)
    scenes = plan(topic, captions)
    seconds_per_scene = SECONDS_PER_SCENE
    total = len(scenes)*seconds_per_scene
    encoder = imageio_ffmpeg.get_ffmpeg_exe()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='topic-video-', dir=destination.parent) as temp:
        temp = Path(temp)
        silent = temp/'silent.mp4'
        command = [encoder, '-y', '-loglevel', 'error', '-f', 'rawvideo',
                   '-pix_fmt', 'rgb24', '-s', f'{WIDTH}x{HEIGHT}', '-r', str(FPS),
                   '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'veryfast',
                   '-crf', '23', '-pix_fmt', 'yuv420p', str(silent)]
        with (temp/'encoder.log').open('wb') as log:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
            try:
                for index, caption in enumerate(scenes):
                    for n in range(seconds_per_scene*FPS):
                        proc.stdin.write(frame(caption, index, len(scenes), n/(seconds_per_scene*FPS), theme).tobytes())
                    update(int((index+1)/len(scenes)*90))
                proc.stdin.close()
                if proc.wait(timeout=120) != 0:
                    raise RuntimeError((temp/'encoder.log').read_text(errors='replace')[-2000:])
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        command = [encoder, '-y', '-loglevel', 'error', '-i', str(silent)]
        if music:
            soundtrack(temp/'music.wav', total)
            command += ['-i', str(temp/'music.wav'), '-c:a', 'aac', '-b:a', '128k']
        complete = temp/'complete.mp4'
        command += ['-c:v', 'copy', '-movflags', '+faststart', str(complete)]
        subprocess.run(command, check=True, timeout=120, capture_output=True)
        complete.replace(destination)
    update(100)
    return {'duration': total, 'scenes': scenes, 'resolution': '1280 × 720',
            'timeline': [{'scene': i+1, 'start': i*SECONDS_PER_SCENE,
                          'end': (i+1)*SECONDS_PER_SCENE} for i in range(len(scenes))]}
