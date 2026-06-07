#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

node --check web/app.js
python3 -m json.tool src-tauri/tauri.conf.json >/tmp/lawrence-tauri-conf-check.json

node --input-type=module <<'NODE'
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { Window } from './node_modules/happy-dom/lib/index.js';

const html = await readFile('web/index.html', 'utf8');
const window = new Window({ url: 'http://127.0.0.1:1423/' });
const { document, File } = window;
const invokes = [];
const bridgeCalls = [];
const windowCalls = [];
const jobs = new Map();

window.__TAURI__ = {
  core: {
    invoke: async (cmd, payload) => {
      invokes.push({ cmd, payload });
      return { accepted: true };
    }
  },
  window: {
    getCurrentWindow: () => ({
      hide: async () => windowCalls.push('hide'),
      close: async () => windowCalls.push('close'),
      minimize: async () => windowCalls.push('minimize')
    })
  }
};

window.fetch = async (url, init = {}) => {
  const body = init.body ? JSON.parse(init.body) : {};
  bridgeCalls.push({ url: String(url), body });
  let payload = { accepted: true };
  if (String(url).endsWith('/context')) {
    payload = { accepted: true, path: `/tmp/${body.action}.dat`, kind: body.kind === 'screen' ? 'screen' : 'audio' };
  } else if (String(url).endsWith('/turn/async')) {
    const jobId = `job-${jobs.size + 1}`;
    jobs.set(jobId, {
      state: 'done',
      result: {
        answer: '---\ntitle: Kernel bridge answer\n---\n\n## Result\n\n- rendered as **MDX**\n- includes `code`',
        events: ['bridge ok']
      }
    });
    payload = { accepted: true, jobId, state: 'queued' };
  } else if (String(url).includes('/jobs/')) {
    const jobId = String(url).split('/jobs/').pop();
    payload = jobs.get(jobId) || { state: 'error', error: 'missing job' };
  }
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

document.write(html);
document.close();
await import(`${pathToFileURL(`${process.cwd()}/web/app.js`).href}?stress=${Date.now()}`);

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

click('#screen-now');
click('#mic-now');
click('#audio-toggle');
click('#video-toggle');
click('#deep-search-toggle');
if (document.querySelector('#deep-search-detail').getAttribute('aria-pressed') !== 'true') {
  throw new Error('deep search drawer toggle did not sync');
}
await settle();
if (invokes.filter((x) => x.cmd === 'request_kernel_context').length !== 2) {
  if (bridgeCalls.filter((x) => x.url.endsWith('/context')).length !== 2) {
    throw new Error('kernel context bridge calls were not invoked');
  }
}
if (invokes.filter((x) => x.cmd === 'set_kernel_observer').length !== 2) {
  if (bridgeCalls.filter((x) => x.url.endsWith('/observer')).length !== 2) {
    throw new Error('observer bridge calls were not invoked');
  }
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
document.querySelector('#mirostat').value = '2';
document.querySelector('#tfs-z').value = '0.97';
document.querySelector('#epsilon-cutoff').value = '0.0004';
document.querySelector('#eta-cutoff').value = '0.0007';
document.querySelector('#repeat-last-n').value = '384';
document.querySelector('#dry-multiplier').value = '0.8';
document.querySelector('#grammar-schema').value = '{"type":"object"}';
document.querySelector('#tool-rounds').value = '5';
document.querySelector('#tool-call-limit').value = '13';
document.querySelector('#web-depth').value = 'Comprehensive';
document.querySelector('#citation-mode').value = 'Required';

submit('<b>use these</b>');
await waitIdle();
const send = invokes.findLast((x) => x.cmd === 'send_turn');
const bridgeTurn = bridgeCalls.findLast((x) => x.url.endsWith('/turn/async'));
if (!send && !bridgeTurn) throw new Error('send turn transport missing');
const turn = bridgeTurn ? bridgeTurn.body.turn : send.payload.turn;
if (turn.kernelContext.length !== 2) throw new Error(`expected 2 kernel context requests, got ${turn.kernelContext.length}`);
if (turn.attachments.length !== 15) throw new Error(`expected 15 attachments, got ${turn.attachments.length}`);
if (turn.config.deepSearch !== true) throw new Error('deep search flag missing from turn config');
if (turn.config.visualContext !== true) throw new Error('visual context flag missing from turn config');
if (turn.config.audioContext !== true) throw new Error('audio context flag missing from turn config');
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

const byKind = Object.fromEntries(turn.attachments.map((item) => [item.kind, item]));
if (byKind.image.converter !== 'image normalize + OCR/vision route') throw new Error('image converter mismatch');
if (byKind.pdf.converter !== 'page text + OCR fallback + citation chunks') throw new Error('pdf converter mismatch');
if (byKind.webpage.source !== 'url') throw new Error('URL source mismatch');
if (byKind.mermaid.converter !== 'diagram source + render preview') throw new Error('mermaid converter mismatch');
if (byKind.spreadsheet.converter !== 'tabular parser + sheet summaries') throw new Error('spreadsheet converter mismatch');
if (!document.querySelector('.message.user .mdx').innerHTML.includes('&lt;b&gt;')) throw new Error('submitted HTML was not escaped');
if (document.querySelectorAll('.message.user .mdx b').length !== 0) throw new Error('submitted HTML created DOM nodes');
if (!document.querySelector('.message.assistant h2')) throw new Error('assistant MDX heading was not rendered');
if (!document.querySelector('.message.assistant ul')) throw new Error('assistant MDX list was not rendered');
if (!document.querySelector('.message.assistant code')) throw new Error('assistant MDX inline code was not rendered');
if (!document.querySelector('#attachment-row').hidden) throw new Error('attachments should clear after send');

click('#settings-toggle');
if (document.querySelector('#settings').hidden) throw new Error('quick settings did not open');
click('#advanced-open');
if (document.querySelector('#advanced-panel').hidden) throw new Error('advanced panel did not open');
document.querySelector('#top-p').value = '0.88';
document.querySelector('#min-p').value = '0.03';
document.querySelector('#typical-p').value = '0.92';
document.querySelector('#seed').value = '12345';
document.querySelector('#stop-sequences').value = 'END, STOP, DONE';
key('Escape');
if (!document.querySelector('#advanced-panel').hidden) throw new Error('escape did not close advanced panel');

for (let i = 0; i < 90; i += 1) {
  submit(`stress ${i}`);
  await waitIdle();
}
if (document.querySelectorAll('.message').length !== 80) throw new Error('message cap should keep last 80 rendered entries');

console.log(JSON.stringify({
  ok: true,
  invokes: invokes.length,
  bridgeCalls: bridgeCalls.length,
  sendTurns: bridgeCalls.filter((x) => x.url.endsWith('/turn/async')).length + invokes.filter((x) => x.cmd === 'send_turn').length,
  renderedMessages: document.querySelectorAll('.message').length,
  attachmentKinds: turn.attachments.map((item) => item.kind)
}, null, 2));
process.exit(0);
NODE
