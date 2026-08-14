async function fetchStatus() {
  try {
    const res = await fetch('/api/v1/status');
    if (!res.ok) throw new Error('Failed to fetch status');
    const data = await res.json();
    document.getElementById('status-text').textContent = `${data.chain} · ${data.block_count} blocks`;
    const metrics = [
      { key: 'Chain Height', value: data.block_count },
      { key: 'Best Block', value: data.best_block_hash },
      { key: 'Difficulty', value: data.difficulty },
      { key: 'Mempool Tx', value: data.mempool?.size || data.mempool?.bytes || 0 },
    ];
    const container = document.getElementById('metrics');
    container.innerHTML = '';
    for (const m of metrics) {
      const card = document.createElement('div');
      card.className = 'bg-white dark:bg-gray-800 shadow p-4 rounded';
      card.innerHTML = `<div class="text-sm text-gray-500 dark:text-gray-400">${m.key}</div><div class="text-2xl font-semibold mt-1">${m.value}</div>`;
      container.appendChild(card);
    }
  } catch (e) {
    document.getElementById('status-text').textContent = 'Error';
    document.getElementById('status-dot').classList.remove('bg-emerald-500');
    document.getElementById('status-dot').classList.add('bg-red-500');
    console.error(e);
  }
}

window.addEventListener('load', () => {
  fetchStatus();
  setInterval(fetchStatus, 3000);
});
