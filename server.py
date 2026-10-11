"""Small local HTTP API with one bounded background render worker."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import re
import threading
import uuid

from generator import render, validate

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT/'output'
jobs = {}
lock = threading.Lock()
pool = ThreadPoolExecutor(max_workers=1)


def run_job(job_id, data):
    def update(progress):
        with lock:
            jobs[job_id]['progress'] = progress
    try:
        result = render(data, OUTPUT/f'{job_id}.mp4', update)
        with lock:
            jobs[job_id].update(status='done', **result, url=f'/videos/{job_id}.mp4')
    except Exception:
        logging.exception('Render failed: %s', job_id)
        with lock:
            jobs[job_id].update(status='failed', error='Rendering failed. Check the server terminal and try again.')


class Handler(BaseHTTPRequestHandler):
    def json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        if self.path != '/api/jobs':
            return self.json(404, {'error': 'Not found.'})
        # Browser cross-origin requests cannot enqueue expensive jobs.
        origin = self.headers.get('Origin')
        if origin and origin != 'http://127.0.0.1:8000':
            return self.json(403, {'error': 'Open the app at http://127.0.0.1:8000.'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8192:
                raise ValueError('Request is empty or too large.')
            data = json.loads(self.rfile.read(size))
            validate(data)
        except (ValueError, TypeError):
            return self.json(400, {'error': 'Enter a topic (3–120 characters), up to six captions (180 characters each), and a valid theme.'})
        with lock:
            if any(j['status'] == 'rendering' for j in jobs.values()):
                return self.json(409, {'error': 'A video is rendering. Please wait until it finishes.'})
            job_id = uuid.uuid4().hex
            if len(jobs) >= 100:
                del jobs[next(iter(jobs))]
            jobs[job_id] = {'status': 'rendering', 'progress': 0}
        pool.submit(run_job, job_id, data)
        self.json(202, {'id': job_id})

    def do_GET(self):
        if self.path.startswith('/api/jobs/'):
            with lock:
                job = dict(jobs.get(self.path.split('/')[-1], {}))
            return self.json(200 if job else 404, job or {'error': 'Job not found. The server may have restarted.'})
        if self.path == '/':
            path, content_type = ROOT/'web'/'index.html', 'text/html; charset=utf-8'
        elif self.path in ('/styles.css', '/app.js'):
            path = ROOT/'web'/self.path[1:]
            content_type = 'text/css; charset=utf-8' if self.path.endswith('.css') else 'text/javascript; charset=utf-8'
        elif self.path.startswith('/videos/'):
            name = self.path.removeprefix('/videos/')
            if len(name) != 36 or not name.endswith('.mp4') or any(c not in '0123456789abcdef' for c in name[:-4]):
                return self.json(404, {'error': 'Not found.'})
            path, content_type = OUTPUT/name, 'video/mp4'
        else:
            return self.json(404, {'error': 'Not found.'})
        if not path.is_file():
            return self.json(404, {'error': 'Not found.'})
        size = path.stat().st_size
        start, end = 0, size - 1
        requested_range = self.headers.get('Range') if content_type == 'video/mp4' else None
        if requested_range:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested_range)
            if not match or not any(match.groups()):
                return self.range_error(size)
            first, last = match.groups()
            if first:
                start, end = int(first), min(int(last), end) if last else end
            else:
                start = max(0, size - int(last))
            if start > end or start >= size:
                return self.range_error(size)
        self.send_response(206 if requested_range else 200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', str(end-start+1))
        if content_type == 'video/mp4':
            self.send_header('Accept-Ranges', 'bytes')
            if requested_range:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with path.open('rb') as file:
                file.seek(start)
                remaining = end-start+1
                while remaining and (chunk := file.read(min(65536, remaining))):
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def range_error(self, size):
        self.send_response(416)
        self.send_header('Content-Range', f'bytes */{size}')
        self.send_header('Content-Length', '0')
        self.end_headers()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    server = ThreadingHTTPServer(('127.0.0.1', 8000), Handler)
    print('Topic Video is ready: http://127.0.0.1:8000', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping after any active render finishes.')
    finally:
        server.server_close()
        pool.shutdown(wait=True)
