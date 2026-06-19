#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for f in web/bootstrap.js web/lib/bridge.js web/variants/classic/app.js; do node --check "$f"; done
python3 -m json.tool src-tauri/tauri.conf.json >/tmp/lawrence-tauri-conf-check.json

node --input-type=module <<'NODE'
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { Window } from './node_modules/happy-dom/lib/index.js';

const html = await readFile('web/index.html', 'utf8');
const window = new Window({ url: 'http://127.0.0.1:1423/' });
const { document, File } = window;
const invokes = [];
const bridgeCalls = [];
const windowCalls = [];
const jobs = new Map();
const eventSources = [];
const mockTasks = [];
const mockRemember = [];
const mockReminders = [];
const mockChats = [{
  id: 'chat-1',
  title: 'Current chat',
  created: '2026-06-18T00:00:00Z',
  updated: '2026-06-18T00:00:00Z',
  messages: 2
}];
const archivedChats = [];
let taskSeq = 0;
let reminderSeq = 0;
let chatSeq = 1;
let activeChat = 'chat-1';
const htmlSetCounts = { feed: 0, mdx: 0 };

let proto = window.Element.prototype;
let innerHtmlDescriptor = null;
while (proto && !innerHtmlDescriptor) {
  innerHtmlDescriptor = Object.getOwnPropertyDescriptor(proto, 'innerHTML');
  proto = Object.getPrototypeOf(proto);
}
if (innerHtmlDescriptor?.get && innerHtmlDescriptor?.set) {
  Object.defineProperty(window.Element.prototype, 'innerHTML', {
    get() {
      return innerHtmlDescriptor.get.call(this);
    },
    set(value) {
      if (this.id === 'feed') htmlSetCounts.feed += 1;
      if (this.classList?.contains('mdx')) htmlSetCounts.mdx += 1;
      return innerHtmlDescriptor.set.call(this, value);
    }
  });
}

window.EventSource = class MockEventSource {
  constructor(url) {
    this.url = url;
    eventSources.push(this);
  }
  close() {}
  emit(payload) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
  error() {
    this.onerror?.(new Error('event stream unavailable'));
  }
};
global.EventSource = window.EventSource;

window.__TAURI__ = {
  core: {
    invoke: async (cmd, payload) => {
      invokes.push({ cmd, payload });
      if (cmd === 'bridge_post') {
        return bridgePayload(payload.path, payload.body || {}, 'POST');
      }
      if (cmd === 'bridge_get') {
        return bridgePayload(payload.path, {}, 'GET');
      }
      if (cmd === 'bridge_delete') {
        return bridgePayload(payload.path, {}, 'DELETE');
      }
      if (cmd === 'send_turn') {
        return {
          answer: '---\ntitle: Native bridge answer\n---\n\n## Result\n\n- rendered as **MDX**\n- includes `code`',
          sources: [{ title: 'Native source', url: 'https://example.com/native', snippet: 'native citation' }],
          events: ['native ok']
        };
      }
      if (cmd === 'open_url') {
        return { accepted: true };
      }
      return { accepted: true };
    }
  },
  window: {
    getCurrentWindow: () => ({
      hide: async () => windowCalls.push('hide'),
      close: async () => windowCalls.push('close'),
      minimize: async () => windowCalls.push('minimize'),
      startResizeDragging: async (edge) => windowCalls.push(`resize:${edge}`)
    })
  }
};

function bridgePayload(url, body = {}, method = 'GET') {
  bridgeCalls.push({ url: String(url), body, method });
  let payload = { accepted: true };
  if (String(url).endsWith('/context')) {
    payload = { accepted: true, path: `/tmp/${body.action}.dat`, kind: body.kind === 'screen' ? 'screen' : 'audio' };
  } else if (String(url).endsWith('/turn/async')) {
    const jobId = `job-${jobs.size + 1}`;
    const longJob = String(body.turn?.text || '').includes('long job');
    jobs.set(jobId, {
      state: longJob ? 'running' : 'done',
      source: body.source || 'typed',
      elapsedSeconds: longJob ? 31 : 0,
      result: longJob ? undefined : {
        answer: '---\ntitle: Kernel bridge answer\n---\n\n## Result\n\n- rendered as **MDX**\n- includes `code`',
        sources: [
          { title: 'Kernel source', url: 'https://example.com/kernel', snippet: 'kernel citation' },
          { title: 'Asset source', url: 'https://assets.example.com/diagram.svg', kind: 'image' }
        ],
        events: ['bridge ok'],
        controls: {
          actionProposals: [{
            id: 'action-1',
            operation: 'artifact.write',
            args: { path: 'notes/mvp.md', text: 'MVP note' },
            risk: 'writes a local artifact',
            contextVersion: 1,
            status: 'pending',
            confirmationToken: 'confirm-action-1'
          }]
        }
      },
      createdAt: new Date().toISOString(),
      finishedAt: longJob ? undefined : new Date().toISOString()
    });
    payload = { accepted: true, jobId, state: 'queued' };
      } else if (String(url).includes('/jobs/')) {
        const jobId = String(url).split('/jobs/').pop();
        payload = jobs.get(jobId) || { state: 'error', error: 'missing job' };
      } else if (String(url).endsWith('/jobs')) {
        payload = { ok: true, items: [...jobs.entries()].map(([id, job]) => ({ id, ...job })) };
      } else if (String(url).endsWith('/health')) {
        payload = {
          ok: true,
      backend: 'test bridge',
      jobs: { queued: 0, running: 0 },
      context: { used: 1024, limit: 4096 },
          system: { load1: 0.1, memoryPercent: 30 },
          pipeline: { visual: 'idle', audio: 'idle', transcript: 'idle' },
          observers: { vision: false, audio: false },
          voice: { listening: true },
          policy: { cloudText: true, explicitCloudMedia: true },
          eventsUrl: 'http://127.0.0.1:8766/events'
        };
      } else if (String(url).endsWith('/voice/listen')) {
        payload = { accepted: true, listening: body.enabled, changed: true };
      } else if (String(url).endsWith('/tasks')) {
    payload = taskPayload(body);
  } else if (String(url).endsWith('/reminders')) {
    if (method === 'POST' && body.op === 'add' && body.text) {
      mockReminders.push({
        id: `reminder-${++reminderSeq}`,
        text: body.text,
        due: body.when || '',
        status: 'pending',
        source: 'user'
      });
    }
    payload = { ok: true, reminders: mockReminders.map((item) => ({ ...item })) };
  } else if (String(url).includes('/reminders/') && method === 'DELETE') {
    const id = decodeURIComponent(String(url).split('/reminders/').pop());
    const index = mockReminders.findIndex((item) => item.id === id);
    if (index >= 0) mockReminders.splice(index, 1);
    payload = { ok: true };
  } else if (String(url).endsWith('/actions')) {
    payload = {
      ok: true,
      action: {
        id: body.id,
        operation: 'artifact.write',
        args: { path: 'notes/mvp.md', text: 'MVP note' },
        status: body.op === 'confirm' ? 'done' : 'rejected'
      }
    };
  } else if (String(url).endsWith('/chats')) {
    if (method === 'POST') {
      activeChat = `chat-${++chatSeq}`;
      mockChats.push({
        id: activeChat,
        title: body.title || 'New chat',
        created: '2026-06-18T00:00:00Z',
        updated: '2026-06-18T00:00:00Z',
        messages: 0
      });
    }
    payload = { ok: true, active: activeChat, items: [...mockChats, ...archivedChats].map((item) => ({ ...item })) };
  } else if (String(url).includes('/chats/') && String(url).endsWith('/switch')) {
    activeChat = decodeURIComponent(String(url).split('/chats/').pop().replace('/switch', ''));
    payload = { ok: true, active: activeChat };
  } else if (String(url).includes('/chats/') && String(url).endsWith('/restore')) {
    const id = decodeURIComponent(String(url).split('/chats/').pop().replace('/restore', ''));
    const index = archivedChats.findIndex((item) => item.id === id);
    if (index >= 0) {
      const [chat] = archivedChats.splice(index, 1);
      chat.archived = false;
      mockChats.push(chat);
    }
    payload = { ok: true };
  } else if (String(url).includes('/chats/') && String(url).endsWith('/export')) {
    const id = decodeURIComponent(String(url).split('/chats/').pop().replace('/export', ''));
    payload = { ok: true, id, format: 'mdx', text: `# Saved ${id}\n\nTranscript.` };
  } else if (String(url).includes('/chats/') && method === 'DELETE') {
    const id = decodeURIComponent(String(url).split('/chats/').pop());
    const index = mockChats.findIndex((item) => item.id === id);
    if (index >= 0) {
      const [chat] = mockChats.splice(index, 1);
      chat.archived = true;
      archivedChats.push(chat);
    }
    activeChat = mockChats[0]?.id || '';
    payload = { ok: true, active: activeChat };
  } else if (String(url).includes('/chats/')) {
    const id = decodeURIComponent(String(url).split('/chats/').pop());
    payload = {
      ok: true,
      id,
      messages_list: [
        { role: 'user', text: 'What is the current plan?' },
        { role: 'assistant', text: 'Build the smallest autonomous loop.' }
      ]
    };
  } else if (String(url).endsWith('/history')) {
    payload = {
      ok: true,
      items: [
        { id: 'journal:2026-06-07', kind: 'journal', date: '2026-06-07', label: 'Journal 2026-06-07', size: 120, entries: 2 },
        { id: 'chat:2026-06-07', kind: 'chat', date: '2026-06-07', label: 'Chat log 2026-06-07', size: 240, entries: 0 }
      ]
    };
  } else if (String(url).includes('/history/journal/')) {
    payload = { ok: true, kind: 'journal', date: '2026-06-07', format: 'mdx', text: '# Journal\n\n## Entry\n\n- browsable' };
  } else if (String(url).includes('/history/chat/')) {
    payload = { ok: true, kind: 'chat', date: '2026-06-07', format: 'text', text: '[user] hello\n[assistant] hi' };
  }
  if (payload.state === 'error') throw new Error(payload.error);
  return payload;
}

function taskPayload(body = {}) {
  const op = body.op || 'list';
  if (op === 'add' && body.text) {
    mockTasks.push({ id: `task-${++taskSeq}`, text: body.text, status: 'open', source: 'user' });
  } else if (op === 'remember' && body.text) {
    mockRemember.push({ id: `remember-${++taskSeq}`, text: body.text, source: 'user' });
  } else if (op === 'done') {
    const item = mockTasks.find((task) => task.id === body.id);
    if (item) item.status = 'done';
  } else if (op === 'reopen') {
    const item = mockTasks.find((task) => task.id === body.id);
    if (item) item.status = 'open';
  } else if (op === 'remove') {
    const taskIndex = mockTasks.findIndex((task) => task.id === body.id);
    if (taskIndex >= 0) mockTasks.splice(taskIndex, 1);
    const rememberIndex = mockRemember.findIndex((item) => item.id === body.id);
    if (rememberIndex >= 0) mockRemember.splice(rememberIndex, 1);
  } else if (op === 'clear' && body.scope === 'done') {
    for (let i = mockTasks.length - 1; i >= 0; i -= 1) {
      if (mockTasks[i].status === 'done') mockTasks.splice(i, 1);
    }
  }
  return {
    ok: true,
    tasks: mockTasks.map((item) => ({ ...item })),
    remember: mockRemember.map((item) => ({ ...item })),
    counts: {
      open: mockTasks.filter((item) => item.status !== 'done').length,
      done: mockTasks.filter((item) => item.status === 'done').length,
      remember: mockRemember.length
    }
  };
}

window.fetch = async (url, init = {}) => {
  const body = init.body ? JSON.parse(init.body) : {};
  const payload = bridgePayload(url, body, init.method || 'GET');
  return {
    ok: payload.state !== 'error',
    status: payload.state === 'error' ? 404 : 200,
    json: async () => payload
  };
};

window.setTimeout = (fn, _delay, ...args) => { fn(...args); return 0; };
global.setTimeout = window.setTimeout;
global.window = window;
global.document = document;
global.HTMLElement = window.HTMLElement;
global.Event = window.Event;
global.KeyboardEvent = window.KeyboardEvent;
global.MouseEvent = window.MouseEvent;
global.SubmitEvent = window.SubmitEvent;
global.Intl = Intl;
global.requestAnimationFrame = window.requestAnimationFrame
  ? window.requestAnimationFrame.bind(window)
  : (fn) => setTimeout(() => fn(Date.now()), 0);

document.write(html);
document.close();
// Import the classic variant directly: bootstrap.js loads the variant via a
// fire-and-forget dynamic import (driven by /health.uiVariant), which would race
// this synchronous DOM harness. The classic variant is the behavioral baseline.
await import(`${pathToFileURL(`${process.cwd()}/web/variants/classic/app.js`).href}?stress=${Date.now()}`);

async function settle() {
  for (let i = 0; i < 20; i += 1) await Promise.resolve();
  await window.happyDOM.waitUntilComplete();
}

async function waitIdle() {
  for (let i = 0; i < 50; i += 1) {
    await settle();
    if (document.querySelector('#stream-state').textContent === 'Idle') return;
  }
  throw new Error('stream did not return to idle');
}

function click(selector, init = {}) {
  document.querySelector(selector).dispatchEvent(new window.MouseEvent('click', {
    bubbles: true,
    cancelable: true,
    ...init
  }));
}

function key(key) {
  document.dispatchEvent(new window.KeyboardEvent('keydown', {
    key,
    bubbles: true,
    cancelable: true
  }));
}

function shortcut(key, init = {}) {
  document.dispatchEvent(new window.KeyboardEvent('keydown', {
    key,
    bubbles: true,
    cancelable: true,
    ...init
  }));
}

function input(selector, value, eventName = 'input') {
  const el = document.querySelector(selector);
  el.value = value;
  el.dispatchEvent(new window.Event(eventName, { bubbles: true }));
}

function submitForm(selector) {
  document.querySelector(selector).dispatchEvent(new window.SubmitEvent('submit', {
    bubbles: true,
    cancelable: true
  }));
}

function submit(text) {
  const prompt = document.querySelector('#prompt');
  prompt.value = text;
  prompt.dispatchEvent(new window.Event('input', { bubbles: true }));
  document.querySelector('#composer').dispatchEvent(new window.SubmitEvent('submit', {
    bubbles: true,
    cancelable: true
  }));
}

function setFiles(files) {
  const input = document.querySelector('#file-input');
  Object.defineProperty(input, 'files', { configurable: true, value: files });
  input.dispatchEvent(new window.Event('change', { bubbles: true }));
}

click('#drawer-toggle');
if (document.querySelector('#option-drawer').hidden) throw new Error('option drawer did not open');

input('#content-zoom', '115');
if (document.documentElement.style.getPropertyValue('--ui-zoom') !== '1.15') throw new Error('content zoom CSS variable was not applied');
if (document.querySelector('.launcher').style.transform) throw new Error('content zoom should not use whole-window transform scaling');
input('#font-size', '16');
if (document.documentElement.style.getPropertyValue('--message-font') !== '16px') throw new Error('font size CSS variable was not applied');
input('#surface-opacity', '72');
if (document.documentElement.style.getPropertyValue('--surface-alpha') !== '0.72') throw new Error('surface opacity CSS variable was not applied');
const uiPrefs = JSON.parse(window.localStorage.getItem('lawrence-ui-prefs') || '{}');
if (uiPrefs.zoom !== '115' || uiPrefs.font !== '16' || uiPrefs.surface !== '72') throw new Error('UI zoom/font/surface prefs were not persisted');

if (document.querySelector('#audio-toggle').getAttribute('aria-pressed') !== 'true') {
  throw new Error('audio context should default to auto-on');
}
if (document.querySelector('#video-toggle').getAttribute('aria-pressed') !== 'true') {
  throw new Error('visual context should default to auto-on');
}
await settle();
const observerDefaults = bridgeCalls.filter((x) => x.url.endsWith('/observer'));
if (!observerDefaults.some((x) => x.body.observer === 'vision' && x.body.enabled === true)) {
  throw new Error('default visual observer was not enabled');
}
if (!observerDefaults.some((x) => x.body.observer === 'audio' && x.body.enabled === true)) {
  throw new Error('default passive audio observer was not enabled');
}
if (bridgeCalls.filter((x) => x.url.endsWith('/voice/listen') && x.body.enabled === true).length !== 1) {
  throw new Error('default voice-listen audio policy was not enabled');
}

shortcut('L', { ctrlKey: true, shiftKey: true });
await settle();
if (!invokes.some((x) => x.cmd === 'show_window')) {
  throw new Error('Ctrl+Shift+L focused-window fallback did not invoke show_window');
}

click('#audio-toggle');
await settle();
if (!bridgeCalls.some((x) => x.url.endsWith('/voice/listen') && x.body.enabled === false)) {
  throw new Error('audio off did not disable voice-listen');
}
if (!bridgeCalls.some((x) => x.url.endsWith('/observer') && x.body.observer === 'audio' && x.body.enabled === false)) {
  throw new Error('audio off did not disable passive audio observer');
}
click('#audio-toggle');
await settle();
if (!bridgeCalls.some((x) => x.url.endsWith('/observer') && x.body.observer === 'audio' && x.body.enabled === true)) {
  throw new Error('audio on did not enable passive audio observer');
}
if (!bridgeCalls.some((x) => x.url.endsWith('/voice/listen') && x.body.enabled === true)) {
  throw new Error('audio on did not restore voice-listen policy');
}

click('#video-toggle');
await settle();
if (!bridgeCalls.some((x) => x.url.endsWith('/observer') && x.body.observer === 'vision' && x.body.enabled === false)) {
  throw new Error('visual off did not disable vision observer');
}
click('#video-toggle');
await settle();
if (!bridgeCalls.some((x) => x.url.endsWith('/observer') && x.body.observer === 'vision' && x.body.enabled === true)) {
  throw new Error('visual on did not enable vision observer');
}

click('#deep-search-toggle');
if (document.querySelector('#deep-search-toggle').getAttribute('aria-pressed') !== 'true') {
  throw new Error('deep search toggle did not activate');
}
click('#refresh-context');
await settle();
if (bridgeCalls.filter((x) => x.url.endsWith('/context')).length !== 2) {
  throw new Error('refresh selected did not force visual/audio context requests');
}

click('#attach-url');
document.querySelector('#url-input').value = 'https://example.com/some/page?x=1';
click('#url-add');

setFiles([
  new File(['x'], 'image.png', { type: 'image/png' }),
  new File(['x'], 'audio.flac', { type: 'audio/flac' }),
  new File(['x'], 'clip.mp4', { type: 'video/mp4' }),
  new File(['x'], 'paper.pdf', { type: 'application/pdf' }),
  new File(['x'], 'notes.mdx', { type: '' }),
  new File(['x'], 'page.html', { type: 'text/html' }),
  new File(['x'], 'brief.docx', { type: '' }),
  new File(['x'], 'deck.pptx', { type: '' }),
  new File(['x'], 'data.xlsx', { type: '' }),
  new File(['x'], 'paper.tex', { type: '' }),
  new File(['x'], 'diagram.mermaid', { type: '' }),
  new File(['x'], 'rows.jsonl', { type: '' }),
  new File(['x'], 'book.epub', { type: '' }),
  new File(['x'], 'unknown.bin', { type: '' })
]);

document.querySelector('#timeout-enabled').checked = false;
document.querySelector('#timeout-enabled').dispatchEvent(new window.Event('change', { bubbles: true }));
input('#mirostat', '2', 'change');
input('#tfs-z', '0.97');
input('#epsilon-cutoff', '0.0004');
input('#eta-cutoff', '0.0007');
input('#repeat-last-n', '384');
input('#dry-multiplier', '0.8');
input('#grammar-schema', '{"type":"object"}');
input('#tool-rounds', '5');
input('#tool-call-limit', '13');
input('#web-depth', 'Comprehensive', 'change');
input('#citation-mode', 'Required', 'change');

const feed = document.querySelector('#feed');
let simulatedFeedTop = 240;
Object.defineProperty(feed, 'scrollTop', {
  configurable: true,
  get: () => simulatedFeedTop,
  set: (value) => { simulatedFeedTop = Number(value); }
});
Object.defineProperty(feed, 'scrollHeight', { configurable: true, get: () => 1200 });
Object.defineProperty(feed, 'clientHeight', { configurable: true, get: () => 300 });
submit('<b>use these</b>');
await waitIdle();
if (simulatedFeedTop !== 240) throw new Error('query invocation changed a manually positioned chat scroll');
const send = invokes.findLast((x) => x.cmd === 'send_turn');
const bridgeTurn = bridgeCalls.findLast((x) => x.url.endsWith('/turn/async'));
if (!send && !bridgeTurn) throw new Error('send turn transport missing');
const turn = bridgeTurn ? bridgeTurn.body.turn : send.payload.turn;
if (turn.kernelContext.length !== 2) throw new Error(`expected 2 kernel context requests, got ${turn.kernelContext.length}`);
if (turn.attachments.length !== 15) throw new Error(`expected 15 attachments, got ${turn.attachments.length}`);
if (turn.config.deepSearch !== true) throw new Error('deep search flag missing from turn config');
if (turn.config.webSearchMode !== 'deep') throw new Error('web search mode should be deep');
if (turn.config.webIntent?.shouldSearch !== true) throw new Error('web intent should request search whenever web is enabled');
if (turn.config.visualContext !== true) throw new Error('visual context flag missing from turn config');
if (turn.config.audioContext !== true) throw new Error('audio context flag missing from turn config');
if (turn.config.forceVisualContext !== true) throw new Error('forced visual context flag missing');
if (turn.config.forceAudioContext !== true) throw new Error('forced audio context flag missing');
if (turn.config.contextPolicy.visual !== 'auto-high-resolution-when-needed') throw new Error('visual context policy mismatch');
if (turn.config.contextPolicy.audio !== 'auto-transcribe-and-run-spoken-turns') throw new Error('audio context policy mismatch');
if (turn.config.voiceListen !== true) throw new Error('voice-listen flag missing');
if (turn.config.responseFormat !== 'mdx') throw new Error('MDX response format missing from turn config');
if (turn.config.decoding.timeoutEnabled !== false) throw new Error('timeout disabled flag missing');
if (turn.config.decoding.timeout !== 0) throw new Error('timeout should be 0 when disabled');
if (turn.config.decoding.mirostat !== 2) throw new Error('mirostat payload mismatch');
if (turn.config.decoding.tfsZ !== 0.97) throw new Error('tfs payload mismatch');
if (turn.config.decoding.repeatLastN !== 384) throw new Error('repeat last n payload mismatch');
if (turn.config.decoding.dryMultiplier !== 0.8) throw new Error('dry multiplier payload mismatch');
if (turn.config.decoding.grammarSchema !== '{"type":"object"}') throw new Error('grammar schema payload mismatch');
if (turn.config.agent.toolRounds !== 5) throw new Error('tool rounds payload mismatch');
if (turn.config.agent.toolCallLimit !== 13) throw new Error('tool call limit payload mismatch');
if (turn.config.agent.webDepth !== 'Comprehensive') throw new Error('web depth payload mismatch');
if (turn.config.agent.citationMode !== 'Required') throw new Error('citation mode payload mismatch');
let tokensMetric = [...document.querySelectorAll('.metric')].find((el) => el.textContent.includes('Tokens'));
const trajectoryMetric = [...document.querySelectorAll('.metric')].find((el) => el.textContent.includes('Trajectory'));
if (!tokensMetric || !/≈[1-9]\d*/.test(tokensMetric.textContent)) throw new Error('session token metric did not accumulate');
if (!trajectoryMetric || !trajectoryMetric.textContent.includes('user')) throw new Error('user context trajectory was not displayed');
tokensMetric.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
await settle();
tokensMetric = [...document.querySelectorAll('.metric')].find((el) => el.textContent.includes('Tokens'));
if (!tokensMetric?.textContent.includes('≈0')) throw new Error('session token reset did not work');

const byKind = Object.fromEntries(turn.attachments.map((item) => [item.kind, item]));
const forcedContext = Object.fromEntries(turn.kernelContext.map((item) => [item.forceKind, item]));
if (!forcedContext.visual?.force || forcedContext.visual.quality !== 'high') throw new Error('visual context was not forced high-res');
if (!forcedContext.audio?.force || forcedContext.audio.quality !== 'high' || forcedContext.audio.transcription !== 'auto') throw new Error('audio context was not forced high-res with auto transcription');
if (byKind.image.converter !== 'image normalize + OCR/vision route') throw new Error('image converter mismatch');
if (byKind.pdf.converter !== 'page text + OCR fallback + citation chunks') throw new Error('pdf converter mismatch');
if (byKind.webpage.source !== 'url') throw new Error('URL source mismatch');
if (byKind.mermaid.converter !== 'diagram source + render preview') throw new Error('mermaid converter mismatch');
if (byKind.spreadsheet.converter !== 'tabular parser + sheet summaries') throw new Error('spreadsheet converter mismatch');
if (!document.querySelector('.message.user:not(.voice) .mdx').innerHTML.includes('&lt;b&gt;')) throw new Error('submitted HTML was not escaped');
if (document.querySelectorAll('.message.user:not(.voice) .mdx b').length !== 0) throw new Error('submitted HTML created DOM nodes');
if (!document.querySelector('.message.assistant h2')) throw new Error('assistant MDX heading was not rendered');
if (!document.querySelector('.message.assistant ul')) throw new Error('assistant MDX list was not rendered');
if (!document.querySelector('.message.assistant code')) throw new Error('assistant MDX inline code was not rendered');
if (document.querySelectorAll('.source-card').length < 2) throw new Error('response sources were not rendered as source cards');
if (!document.querySelector('[data-action-id="action-1"]')) throw new Error('action proposal was not rendered');
click('[data-action-decision="confirm"]');
await settle();
if (!bridgeCalls.some((x) => x.url.endsWith('/actions') && x.body.op === 'confirm' && x.body.token === 'confirm-action-1')) {
  throw new Error('action confirmation was not sent to the kernel');
}
if (!document.querySelector('[data-action-id="action-1"]').textContent.includes('done')) throw new Error('confirmed action status did not render');
document.querySelector('.source-card').dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
await settle();
if (!invokes.some((x) => x.cmd === 'open_url' && x.payload.url === 'https://example.com/kernel')) {
  throw new Error('source card did not invoke native URL opener');
}
if (document.querySelectorAll('#attachment-row .attachment:not(.context)').length !== 0) throw new Error('document attachments should clear after send');
if (document.querySelectorAll('#attachment-row .attachment[data-type="context"]').length !== 0) throw new Error('forced visual/audio context should merge into live context cards');
if (document.querySelectorAll('#attachment-row .attachment[data-type="live"]').length !== 2) throw new Error('expected one visual and one audio live context card');

const savedSession = JSON.parse(window.localStorage.getItem('lawrence-ui-session') || '{}');
if (!Array.isArray(savedSession.messages) || savedSession.messages.length < 2) throw new Error('session messages were not persisted');
if (savedSession.controls?.visual !== true || savedSession.controls?.audio !== true) throw new Error('session context controls were not persisted');
if (savedSession.controls?.deep !== true) throw new Error('session deep-search state was not persisted');

click('#deep-search-toggle');
submit('just answer from wherever');
await waitIdle();
const defaultWebTurn = bridgeCalls.findLast((x) => x.url.endsWith('/turn/async')).body.turn;
if (defaultWebTurn.config.deepSearch !== false) throw new Error('deep search should only be explicit');
if (defaultWebTurn.config.webSearchMode !== 'single-pass') throw new Error('default web mode should be single-pass');
if (defaultWebTurn.config.webIntent?.shouldSearch !== true || defaultWebTurn.config.webIntent?.policy !== 'single-pass default') {
  throw new Error('web intent should always request default single-pass search when web is enabled');
}

click('#retrieval-toggle');
submit('web disabled for this turn');
await waitIdle();
const webOffTurn = bridgeCalls.findLast((x) => x.url.endsWith('/turn/async')).body.turn;
if (webOffTurn.config.webSearchMode !== 'off') throw new Error('web search off toggle did not affect turn config');
if (webOffTurn.config.webIntent?.enabled !== false || webOffTurn.config.webIntent?.shouldSearch !== false) {
  throw new Error('web disabled turn still requested web search');
}
click('#retrieval-toggle');

window.localStorage.setItem('lawrence-ui-config', JSON.stringify({
  updatedAt: Date.now(),
  controls: {
    '#top-k': { value: '7' },
    '#response-length': { value: 'Concise' },
    '#retrieval-toggle': { pressed: true, text: 'On' }
  }
}));
submit('stored config must apply');
await waitIdle();
const storedConfigTurn = bridgeCalls.findLast((x) => x.url.endsWith('/turn/async')).body.turn;
if (storedConfigTurn.config.decoding.topK !== 7) throw new Error('stored sidecar config top-k was not applied');
if (storedConfigTurn.config.responseLength !== 'Concise') throw new Error('stored sidecar response length was not applied');

submit('long job should detach');
await waitIdle();
if (!document.body.textContent.includes('Still Running')) throw new Error('long-running job did not detach into a pending MDX message');

const es = eventSources.at(-1);
if (!es) throw new Error('EventSource was not connected');
es.emit({ type: 'context', kind: 'audio', text: '[AUDIO 12:00:00] "remember this audio snippet"' });
await settle();
if (!document.body.textContent.includes('remember this audio snippet')) {
  throw new Error('passive audio transcript event was not reflected in telemetry');
}
es.emit({
  type: 'voice',
  event: 'final',
  uid: 'voice-utterance-1',
  transcript: 'move the planning call to Friday'
});
es.emit({
  type: 'response',
  source: 'voice',
  jobId: 'voice-job-1',
  transcript: 'move the planning call to Friday',
  answer: '## Voice Result\n\n- Added as spoken input.',
  confidence: 0.87
});
await waitIdle();
if (!document.querySelector('.message.user.voice')) throw new Error('spoken voice user turn was not rendered');
if (!document.body.textContent.includes('Voice Result')) throw new Error('voice assistant response was not rendered');
if (document.body.textContent.includes('Heard: move the planning call')) throw new Error('voice transcript should not be prepended inside assistant answer');
es.error();
await settle();
const transcriptMetric = [...document.querySelectorAll('.metric')].find((el) => el.textContent.includes('Transcript'));
if (!transcriptMetric?.classList.contains('fail')) throw new Error('failed subsystem metric was not highlighted');

click('#drawer-toggle');
click('#minimize-btn');
await settle();
if (!invokes.some((x) => x.cmd === 'dismiss_window')) throw new Error('minimize did not invoke native dismiss_window');
click('#drawer-toggle');
click('#close-btn');
await settle();
if (invokes.filter((x) => x.cmd === 'dismiss_window').length < 2) throw new Error('dismiss did not invoke native dismiss_window');

click('#settings-toggle');
if (!invokes.find((x) => x.cmd === 'open_panel' && x.payload.panel === 'settings')) throw new Error('settings did not request sidecar panel');
click('#advanced-open');
if (!invokes.find((x) => x.cmd === 'open_panel' && x.payload.panel === 'advanced')) throw new Error('advanced sampling did not request sidecar panel');
input('#top-p', '0.88');
input('#min-p', '0.03');
input('#typical-p', '0.92');
input('#seed', '12345');
input('#stop-sequences', 'END, STOP, DONE');

click('#drawer-toggle');
click('#tasks-open');
if (!invokes.find((x) => x.cmd === 'open_panel' && x.payload.panel === 'tasks')) throw new Error('tasks did not request sidecar panel');
input('#tasks-add-input', 'Ship the native host split');
submitForm('#tasks-add-form');
await settle();
if (!document.querySelector('#tasks-list').textContent.includes('Ship the native host split')) throw new Error('bullet journal task add did not render');
const taskCheck = document.querySelector('#tasks-list .task-check');
taskCheck.click();
await settle();
if (!document.querySelector('#tasks-list .task-item.done')) throw new Error('bullet journal task checkbox did not mark done');
click('#tasks-clear-done');
await settle();
if (document.querySelector('#tasks-list').textContent.includes('Ship the native host split')) throw new Error('clear done did not remove completed bullet');
input('#tasks-add-input', 'Remember source cards');
click('#remember-add');
await settle();
if (!document.querySelector('#remember-list').textContent.includes('Remember source cards')) throw new Error('bullet journal note add did not render');
document.querySelector('#remember-list .task-del').dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
await settle();
if (document.querySelector('#remember-list').textContent.includes('Remember source cards')) throw new Error('bullet journal note remove did not render');

click('#drawer-toggle');
click('#reminders-open');
if (!invokes.find((x) => x.cmd === 'open_panel' && x.payload.panel === 'reminders')) throw new Error('reminders did not request sidecar panel');
input('#reminder-title', 'Check host UI');
input('#reminder-rule', '10m');
submitForm('#reminders-add-form');
await settle();
if (!document.querySelector('#reminders-list').textContent.includes('Check host UI')) throw new Error('reminder add did not render');
if (!bridgeCalls.some((x) => x.url.endsWith('/reminders') && x.method === 'POST' && x.body.text === 'Check host UI')) {
  throw new Error('reminder add did not reach the kernel');
}
if (window.localStorage.getItem('lawrence-ui-reminders')) throw new Error('reminders must not be stored as local UI drafts');
document.querySelector('#reminders-list .task-del').dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
await settle();
if (document.querySelector('#reminders-list').textContent.includes('Check host UI')) throw new Error('reminder remove did not render');
if (!bridgeCalls.some((x) => x.url.includes('/reminders/reminder-1') && x.method === 'DELETE')) {
  throw new Error('reminder removal did not reach the kernel');
}

click('#drawer-toggle');
click('#history-open');
if (!invokes.find((x) => x.cmd === 'open_panel' && x.payload.panel === 'history')) throw new Error('history did not request sidecar panel');
click('#history-refresh');
await settle();
if (document.querySelectorAll('#history-list .history-item').length < 3) throw new Error('history refresh did not render chats and entries');
document.querySelector('#history-list [data-chat-id="chat-1"]').dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
await settle();
if (!document.querySelector('#history-preview').textContent.includes('smallest autonomous loop')) throw new Error('chat session did not load');
click('#chat-save');
await settle();
if (!bridgeCalls.some((x) => x.url.endsWith('/chats/chat-1/export'))) throw new Error('save chat did not export the active chat');
click('#chat-archive');
await settle();
if (!bridgeCalls.some((x) => x.url.endsWith('/chats/chat-1') && x.method === 'DELETE')) throw new Error('archive chat did not reach the kernel');
const restore = document.querySelector('[data-restore-chat="chat-1"]');
if (!restore) throw new Error('archived chat did not expose restore');
restore.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
await settle();
if (!bridgeCalls.some((x) => x.url.endsWith('/chats/chat-1/restore'))) throw new Error('restore chat did not reach the kernel');
click('#chat-new');
await settle();
if (!bridgeCalls.some((x) => x.url.endsWith('/chats') && x.method === 'POST')) throw new Error('new chat did not reach the kernel');
if (document.querySelectorAll('#feed .message').length !== 0) throw new Error('clear/new chat did not clear the visible conversation');
document.querySelector('#history-list [data-index="0"]').dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
await settle();
if (!document.querySelector('#history-preview').textContent.includes('browsable')) throw new Error('history item did not load MDX preview');

const feedHtmlBefore = htmlSetCounts.feed;
for (let i = 0; i < 90; i += 1) {
  submit(`stress ${i}`);
  await waitIdle();
}
if (document.querySelectorAll('.message').length !== 80) throw new Error('message cap should keep last 80 rendered entries');
const feedHtmlDuringStress = htmlSetCounts.feed - feedHtmlBefore;
if (feedHtmlDuringStress > 260) throw new Error(`streaming rebuilt the full feed too often (${feedHtmlDuringStress})`);

const report = {
  ok: true,
  verifiedFeatures: [
    'startup restores defaults and connects bridge/event stream',
    'Ctrl+Shift+L focused-window fallback invokes show_window',
    'visual/audio toggles gate kernel observers',
    'voice-listen policy starts with passive audio observer',
    'refresh selected forces high-resolution visual and audio context',
    'default web search policy and deep-search escalation are encoded in turn config',
    'advanced sampling/config controls are serialized into turn config',
    'stored sidecar config is applied before sending turns',
    'attachments are classified by converter route across common file types',
    'MDX rendering escapes user HTML and renders headings/lists/code',
    'source cards are parsed/rendered from responses and open through native URL command',
    'long-running jobs detach and restore through bridge polling',
    'passive audio transcript events render as spoken user input',
    'voice response events render transcript plus assistant response',
    'UI zoom/font/surface prefs apply without whole-window transform scaling',
    'web search off toggle disables web retrieval in turn config',
    'minimize and dismiss invoke native window dismissal',
    'bullet journal add/check/clear/remove operations render manager state',
    'action proposals require explicit kernel confirmation',
    'reminder add/list/remove operations use durable kernel state',
    'chat sessions and history previews load from the kernel',
    'policy state is visible in telemetry',
    'bottom telemetry highlights failures and shows resettable session tokens plus context trajectory',
    'settings/sampling/journal/reminders/history open as Tauri sidecar panels',
    'session state persists recent messages and control state',
    'streaming avoids excessive full-feed rebuilds',
    'feed caps rendered messages to the latest 80 entries'
  ],
  invokes: invokes.length,
  bridgeCalls: bridgeCalls.length,
  sendTurns: bridgeCalls.filter((x) => x.url.endsWith('/turn/async')).length + invokes.filter((x) => x.cmd === 'send_turn').length,
  renderedMessages: document.querySelectorAll('.message').length,
  feedFullRendersDuringStress: feedHtmlDuringStress,
  attachmentKinds: turn.attachments.map((item) => item.kind)
};
await mkdir('../../.runtime/desktop', { recursive: true });
await writeFile('../../.runtime/desktop/feature-test-report.json', `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
process.exit(0);
NODE
