// lightweight in-memory series store for sparklines
const SERIES_LEN = 30;
const series = {};
const charts = new Map();

function ensureSeries(key) {
  if (!series[key]) series[key] = [];
  return series[key];
}

function pushSeries(key, value) {
  const s = ensureSeries(key);
  s.push(typeof value === 'number' ? value : 0);
  while (s.length > SERIES_LEN) s.shift();
}

function fmt(n) {
  if (n === null || n === undefined) return '-';
  if (Math.abs(n) >= 1e9) return (n/1e9).toFixed(2)+'B';
  if (Math.abs(n) >= 1e6) return (n/1e6).toFixed(2)+'M';
  if (Math.abs(n) >= 1e3) return (n/1e3).toFixed(1)+'k';
  return String(n);
}

function createCard(key, value) {
  const container = document.getElementById('metrics');
  let card = document.getElementById('metric-'+key.replace(/\s+/g,'-'));
  if (card) return card;
  card = document.createElement('div');
  card.id = 'metric-'+key.replace(/\s+/g,'-');
  card.className = 'bg-white dark:bg-gray-800 shadow p-4 rounded flex flex-col justify-between';
  card.innerHTML = `
    <div class="flex justify-between items-start gap-2">
      <div class="text-sm text-gray-500 dark:text-gray-400 truncate max-w-xs" title="${key}">${key}</div>
      <div class="text-sm text-gray-400">&nbsp;</div>
    </div>
    <div class="mt-1 flex items-center gap-4">
      <div class="text-2xl font-semibold" data-key-value>${fmt(value)}</div>
      <div class="flex-1">
        <div class="spark-canvas" data-spark></div>
      </div>
    </div>
  `;
  container.appendChild(card);

  // init chart
  const elm = card.querySelector('[data-spark]');
  const cfg = {
    chart: { type: 'area', height: 40, sparkline: { enabled: true } },
    stroke: { curve: 'smooth', width: 2 },
    series: [{ data: [] }],
    colors: ['#60a5fa'],
    fill: { type: 'gradient', gradient: { shade: 'light', type: 'vertical', shadeIntensity: 0.6, opacityFrom: 0.35, opacityTo: 0.05 } },
    tooltip: { enabled: false }
  };
  const chart = new ApexCharts(elm, cfg);
  chart.render();
  charts.set(key, chart);
  return card;
}

function updateCard(key, value) {
  const card = createCard(key, value);
  const valEl = card.querySelector('[data-key-value]');
  if (valEl) valEl.textContent = fmt(value);
  pushSeries(key, typeof value === 'number' ? value : 0);
  const chart = charts.get(key);
  if (chart) {
    chart.updateSeries([{ data: series[key].slice(-SERIES_LEN) }], true);
  }
}

function truncateHash(h) {
  if (!h) return '';
  return h.slice(0,10)+'…'+h.slice(-6);
}

function copyText(t) {
  navigator.clipboard?.writeText(t).catch(()=>{});
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/v1/status');
    if (!res.ok) throw new Error('Failed to fetch status');
    const data = await res.json();
    document.getElementById('status-text').textContent = `${data.chain ?? '-'} · ${data.block_count ?? '-'} blocks`;
    document.getElementById('status-dot').classList.remove('bg-red-500');
    document.getElementById('status-dot').classList.add('bg-emerald-500');

    // Key metrics
    updateCard('Chain Height', Number(data.block_count) || 0);
    updateCard('Difficulty', Number(data.difficulty) || 0);
    updateCard('Mempool Tx', data.mempool?.size || (data.mempool?.bytes ? Math.round(data.mempool.bytes/1000) : 0));
    updateCard('Connected Peers', data.peers || 0);

    // Best block hash displayed separately with truncation and copy
    const best = data.best_block_hash || '';
    let bestEl = document.getElementById('best-block');
    if (!bestEl) {
      bestEl = document.createElement('div');
        bestEl.id = 'best-block';
        bestEl.className = 'mt-4 text-sm text-gray-600 dark:text-gray-300 flex items-center gap-2';
        bestEl.innerHTML = `<span class="truncate max-w-md" id="best-block-text">${truncateHash(best)}</span> <button id="best-copy" class="text-xs px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded">Copy</button>`;
      document.querySelector('main').prepend(bestEl);
      document.getElementById('best-copy').addEventListener('click', ()=>copyText(best));
    } else {
      document.getElementById('best-block-text').textContent = truncateHash(best);
      // update copy handler (in case hash changed)
      document.getElementById('best-copy').onclick = ()=>copyText(best);
    }

    // Recent blocks
    const blocksList = document.getElementById('blocks-list');
    blocksList.innerHTML = '';
    (data.recent_blocks || []).slice(0,8).forEach(b=>{
      const node = document.createElement('div');
      node.className = 'p-2 bg-white dark:bg-gray-800 rounded flex items-center justify-between';
              node.innerHTML = `<div class="flex items-center gap-3">
          <div class="text-sm font-medium truncate max-w-xs" title="${b.hash}">${truncateHash(b.hash)}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400">txs: ${b.tx_count}</div>
        </div>
        <div class="text-xs text-gray-400">${b.time ? new Date(b.time*1000).toLocaleTimeString() : ''}</div>`;
      node.querySelector('.truncate')?.addEventListener('click', ()=>copyText(b.hash));
      blocksList.appendChild(node);
    });

  } catch (e) {
    document.getElementById('status-text').textContent = 'Error';
    document.getElementById('status-dot').classList.remove('bg-emerald-500');
    document.getElementById('status-dot').classList.add('bg-red-500');
    console.error(e);
  }
}

// Theme toggle
function initThemeToggle(){
  const btn = document.getElementById('theme-toggle');
  if(!btn) return;
  btn.addEventListener('click', ()=>{
    document.documentElement.classList.toggle('dark');
  });
}

// Wire search box to call /api/v1/search and show simple alert with results
function initSearch(){
  const input = document.getElementById('global-search');
  if(!input) return;
  input.addEventListener('keydown', async (e)=>{
    if(e.key !== 'Enter') return;
    const q = input.value.trim();
    if(!q) return;
    try{
      const res = await fetch('/api/v1/search?q='+encodeURIComponent(q));
      if(!res.ok) { alert('Not found or error'); return; }
      const data = await res.json();
      showSearchResult(data);
    }catch(err){
      alert('Search error');
    }
  });
}

function showSearchResult(data){
  const modal = document.getElementById('search-modal');
  const body = document.getElementById('search-result-body');
  if(!modal || !body) { alert(JSON.stringify(data)); return; }
  body.innerHTML = '';
  if(data.type === 'block' && data.block){
    const b = data.block;
    const h = document.createElement('div');
    h.className = 'mb-2';
    h.innerHTML = `<div class="text-sm text-gray-500 dark:text-gray-400">Height: ${b.height ?? '-'} · Time: ${b.time ? new Date(b.time*1000).toLocaleString() : '-'} · Txs: ${b.nTx ?? (b.tx ? b.tx.length : '-')}</div><div class="font-mono break-words mt-1">${b.hash}</div>`;
    body.appendChild(h);

    // tx list (if present)
    const txs = b.tx || [];
    const list = document.createElement('div');
    list.className = 'space-y-1 mt-2';
    const maxShow = 50;
    txs.slice(0, maxShow).forEach((tx, idx)=>{
      const txid = (typeof tx === 'string') ? tx : (tx.txid || tx.hash || tx.wtxid || tx.hex || '');
      const el = document.createElement('div');
      el.className = 'flex items-center justify-between gap-2';
      const link = `https://blockstream.info/tx/${txid}`;
      el.innerHTML = `<a class="text-xs text-blue-600 dark:text-blue-400 truncate" href="${link}" target="_blank" rel="noopener noreferrer">${txid}</a><div class="text-xs text-gray-500">${idx+1}</div>`;
      list.appendChild(el);
    });
    if(txs.length > maxShow){
      const more = document.createElement('div'); more.className='text-xs text-gray-500 mt-2'; more.textContent = `Showing ${maxShow}/${txs.length} txs`; body.appendChild(more);
    }
    body.appendChild(list);
  } else if(data.error){
    body.textContent = data.error;
  } else {
    body.textContent = JSON.stringify(data, null, 2);
  }

  modal.classList.remove('hidden');
  document.getElementById('search-close').onclick = ()=>{ modal.classList.add('hidden'); };
}

// WebSocket stub for real-time updates (reconnects)
function initWS(){
  // prefer short-lived token from server if WS_TOKEN was not embedded
  async function getToken(){
    try{
      if(window.WS_TOKEN) return window.WS_TOKEN;
      const r = await fetch('/ws-token');
      if(!r.ok) return '';
      const j = await r.json();
      return j.token || '';
    }catch(e){ return ''; }
  }

  const scheme = (location.protocol === 'https:' ? 'wss://' : 'ws://');
  let tokenPromise = getToken();
  let ws;
  let retry = 1000;
  function connect(){
    tokenPromise.then(token=>{
      const url = scheme + location.host + '/ws' + (token ? '?token='+encodeURIComponent(token) : '');
      try{
        ws = new WebSocket(url);
      }catch(e){ setTimeout(connect, retry); retry = Math.min(30000, retry*1.5); return; }
      ws.onopen = ()=>{ console.debug('ws open'); retry = 1000; };
      ws.onmessage = (ev)=>{
        try{
          const msg = JSON.parse(ev.data);
          if (msg.type === 'metric'){
            if(msg.metrics){
              for(const [k,v] of Object.entries(msg.metrics)) updateCard(k, v);
            }
            if(msg.recent_blocks) {
              const blocksList = document.getElementById('blocks-list');
              blocksList.innerHTML = '';
              msg.recent_blocks.slice(0,8).forEach(b=>{
                const node = document.createElement('div');
                node.className = 'p-2 bg-white dark:bg-gray-800 rounded flex items-center justify-between';
                node.innerHTML = `<div class="flex items-center gap-3"><div class="text-sm font-medium truncate max-w-xs" title="${b.hash}">${truncateHash(b.hash)}</div><div class="text-xs text-gray-500 dark:text-gray-400">txs: ${b.tx_count}</div></div><div class="text-xs text-gray-400">${b.time ? new Date(b.time*1000).toLocaleTimeString() : ''}</div>`;
                node.querySelector('.truncate')?.addEventListener('click', ()=>copyText(b.hash));
                blocksList.appendChild(node);
              });
            }
          } else if(msg.type === 'ping'){
            // respond with a pong
            try{ ws.send(JSON.stringify({type:'pong', ts: msg.ts || Date.now()})); }catch(e){}
          }
        }catch(e){}
      };
      ws.onclose = ()=>{ console.debug('ws closed, reconnecting'); setTimeout(()=>{ tokenPromise = getToken(); connect(); }, retry); retry = Math.min(30000, retry*1.5); };
      ws.onerror = ()=>{ ws.close(); };
    });
  }
  connect();
}

window.addEventListener('load', () => {
  initThemeToggle();
  initWS();
  initSearch();
  fetchStatus();
  setInterval(fetchStatus, 3000);
});
