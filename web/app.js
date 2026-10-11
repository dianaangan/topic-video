const element = id => document.getElementById(id);
const form = element('form');
let pollTimer;
let activeJob = null;
let lastResult = null;

// Private browsing can disable storage; the app still works without it.
function save(key, value) {
  try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, JSON.stringify(value)); } catch {}
}
function restore(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}
function captions() {
  return element('captions').value.split('\n').map(line => line.trim()).filter(Boolean);
}
function clock(seconds) {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}
function updateSummary() {
  const lines = captions();
  const count = lines.length;
  const invalidCaptions = count > 6 || lines.some(line => line.length > 180);
  const scenes = count ? count + 1 : 5;
  element('topic-count').textContent = `${element('topic').value.length}/120`;
  element('caption-count').textContent = `${count}/6 lines`;
  element('scene-count').textContent = invalidCaptions ? 'Check captions' : `${scenes} scenes`;
  element('duration').textContent = invalidCaptions ? 'Up to 28 seconds' : `${scenes * 4} seconds`;
  const colors = { ocean: '#285654', sunset: '#633b42', ink: '#3e426b' };
  element('placeholder').style.setProperty('--preview-color', colors[element('theme').value]);
}
function saveDraft() {
  save('topic-video-draft', { topic: element('topic').value, captions: element('captions').value,
    theme: element('theme').value, music: element('music').checked });
}
function clearError() {
  element('error').hidden = true;
  for (const id of ['topic', 'captions']) element(id).removeAttribute('aria-invalid');
}
function showError(message, field) {
  element('error').textContent = message;
  element('error').hidden = false;
  if (field) {
    element(field).setAttribute('aria-invalid', 'true');
    element(field).focus();
  }
}
function setBusy(busy) {
  element('fields').disabled = busy;
  element('sample').disabled = busy;
  element('generate').disabled = busy;
  element('generate').textContent = busy ? 'Generating…' : 'Generate video';
  element('form').setAttribute('aria-busy', String(busy));
  element('progress').hidden = !busy;
  element('state').textContent = busy ? 'Rendering' : lastResult ? 'Ready' : 'No video yet';
}
async function request(url, options) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    const body = await response.json();
    if (!response.ok) {
      const error = new Error(body.error || 'Request failed. Please try again.');
      error.status = response.status;
      throw error;
    }
    return body;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The server took too long to respond. Wait a moment, then reload to check your render.');
    if (error instanceof TypeError) throw new Error('Cannot reach the local server. Keep its terminal running, then reload this page.');
    throw error;
  } finally { clearTimeout(timeout); }
}
function showResult(job) {
  lastResult = job;
  const video = element('video');
  video.src = job.url;
  video.hidden = false;
  element('placeholder').hidden = true;
  element('download').href = job.url;
  element('download').download = 'topic-video.mp4';
  element('download').hidden = false;
  element('details').textContent = `${job.resolution} · ${job.duration} seconds · ${job.scenes.length} scenes`;
  element('timeline').replaceChildren();
  job.scenes.forEach((caption, i) => {
    const row = document.createElement('li');
    const time = document.createElement('time');
    time.textContent = `${clock(i * 4)}–${clock((i + 1) * 4)}`;
    const text = document.createElement('span');
    text.textContent = caption;
    row.append(time, text);
    element('timeline').append(row);
  });
  element('scene-details').hidden = false;
  element('status').textContent = 'Your video is ready. Play it or download the MP4.';
  save('topic-video-result', job);
}
function finish() {
  clearTimeout(pollTimer);
  activeJob = null;
  save('topic-video-job', null);
  setBusy(false);
}
async function poll(id) {
  try {
    const job = await request(`/api/jobs/${id}`);
    element('progress').value = job.progress;
    element('status').textContent = `${job.progress >= 90 ? 'Finishing your MP4' : 'Rendering your scenes'}… ${job.progress}%`;
    if (job.status === 'failed') {
      finish();
      throw new Error(job.error);
    }
    if (job.status === 'done') {
      showResult(job);
      finish();
    } else { pollTimer = setTimeout(() => poll(id), 1000); }
  } catch (error) {
    // Keep the ID on connection failure so a reload can recover the job.
    clearTimeout(pollTimer);
    if (error.status === 404) save('topic-video-job', null);
    activeJob = null;
    setBusy(false);
    showError(error.message);
    element('status').textContent = lastResult ? 'Your previous video is still available.' : 'Render status unavailable.';
  }
}
form.addEventListener('input', () => { clearError(); updateSummary(); saveDraft(); });
form.addEventListener('change', () => { updateSummary(); saveDraft(); });
element('sample').addEventListener('click', () => {
  element('topic').value = 'Healthy morning routine';
  element('captions').value = 'Drink a glass of water.\nStretch for five minutes.\nChoose one priority for today.';
  element('theme').value = 'ocean';
  element('music').checked = true;
  clearError();
  updateSummary();
  saveDraft();
  element('topic').focus();
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (activeJob || element('generate').disabled) return;
  clearError();
  const topic = element('topic').value.trim();
  const lines = captions();
  if (topic.length < 3 || topic.length > 120) return showError('Enter a topic between 3 and 120 characters.', 'topic');
  if (lines.length > 6) return showError('Use up to six caption lines.', 'captions');
  if (lines.some(line => line.length > 180)) return showError('Keep each caption to 180 characters or fewer.', 'captions');
  setBusy(true);
  element('video').pause();
  element('progress').value = 0;
  element('status').textContent = 'Starting your render…';
  try {
    const job = await request('/api/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, captions: lines, theme: element('theme').value, music: element('music').checked }) });
    activeJob = job.id;
    save('topic-video-job', activeJob);
    poll(activeJob);
  } catch (error) {
    setBusy(false);
    showError(error.message);
    element('status').textContent = lastResult ? 'Your previous video is still available.' : 'Ready to try again.';
  }
});
element('video').addEventListener('error', () => {
  if (element('video').getAttribute('src')) showError('This video could not be loaded. Check that the server is running, or generate a new video.');
});
const draft = restore('topic-video-draft');
if (draft && typeof draft.topic === 'string' && typeof draft.captions === 'string') {
  element('topic').value = draft.topic.slice(0, 120);
  element('captions').value = draft.captions;
  if (['ocean', 'sunset', 'ink'].includes(draft.theme)) element('theme').value = draft.theme;
  element('music').checked = draft.music !== false;
}
updateSummary();
const previous = restore('topic-video-result');
if (previous && typeof previous.url === 'string' && /^\/videos\/[a-f0-9]{32}\.mp4$/.test(previous.url) && Array.isArray(previous.scenes)) showResult(previous);
activeJob = restore('topic-video-job');
if (typeof activeJob === 'string' && /^[a-f0-9]{32}$/.test(activeJob)) { setBusy(true); poll(activeJob); }
else { activeJob = null; setBusy(false); }
