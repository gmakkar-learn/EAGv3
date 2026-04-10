const BASE = 'https://paper-api.alpaca.markets/v2';
let API_KEY = '';
let API_SECRET = '';

function getHeaders() {
  return {
    'APCA-API-KEY-ID': API_KEY,
    'APCA-API-SECRET-KEY': API_SECRET,
    'Content-Type': 'application/json'
  };
}

async function api(path, opts = {}) {
  const r = await fetch(BASE + path, { headers: getHeaders(), ...opts });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ message: r.statusText }));
    throw new Error(e.message || r.statusText);
  }
  return r.json();
}

function fmt(n) {
  return '$' + parseFloat(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function showTab(t) {
  document.querySelectorAll('.tab').forEach(el => el.classList.toggle('active', el.dataset.tab === t));
  document.querySelectorAll('.section').forEach(el => el.classList.toggle('active', el.id === t));
  if (t === 'portfolio') loadPortfolio();
  if (t === 'orders') loadOrders();
}

async function loadPortfolio() {
  if (!API_KEY) { showNoCredentials('positions-body'); return; }
  document.getElementById('positions-body').innerHTML = '<div class="empty">Loading...</div>';
  try {
    const [acct, positions] = await Promise.all([api('/account'), api('/positions')]);
    document.getElementById('status-dot').className = 'dot live';

    const pnl = parseFloat(acct.equity) - parseFloat(acct.last_equity);
    document.getElementById('m-equity').textContent = fmt(acct.equity);
    document.getElementById('m-cash').textContent = fmt(acct.cash);
    document.getElementById('m-bp').textContent = fmt(acct.buying_power);
    const pnlEl = document.getElementById('m-pnl');
    pnlEl.textContent = (pnl >= 0 ? '+' : '') + fmt(pnl);
    pnlEl.className = pnl >= 0 ? 'pos' : 'neg';

    if (!positions.length) {
      document.getElementById('positions-body').innerHTML = '<div class="empty">No open positions</div>';
      return;
    }
    const rows = positions.map(p => {
      const pl = parseFloat(p.unrealized_pl);
      const side = p.side === 'long' ? 'sell' : 'buy';
      return `<tr>
        <td><strong>${p.symbol}</strong></td>
        <td>${p.qty}</td>
        <td>${fmt(p.avg_entry_price)}</td>
        <td>${fmt(p.current_price)}</td>
        <td class="${pl >= 0 ? 'pos' : 'neg'}">${pl >= 0 ? '+' : ''}${fmt(pl)}</td>
        <td><button class="btn-close" data-symbol="${p.symbol}" data-qty="${p.qty}" data-side="${side}">Close</button></td>
      </tr>`;
    }).join('');
    document.getElementById('positions-body').innerHTML = `
      <table>
        <thead><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Price</th><th>P&L</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;

    // Wire up close buttons
    document.querySelectorAll('.btn-close').forEach(btn => {
      btn.addEventListener('click', () => closePosition(btn.dataset.symbol, btn.dataset.qty, btn.dataset.side, btn));
    });
  } catch (e) {
    document.getElementById('positions-body').innerHTML = `<div class="empty">Error: ${e.message}</div>`;
  }
}

async function cancelOpenOrdersForSymbol(symbol) {
  try {
    const orders = await api(`/orders?status=open&symbols=${symbol}`);
    await Promise.all(orders.map(o => api(`/orders/${o.id}`, { method: 'DELETE' })));
    return orders.length;
  } catch (e) {
    return 0;
  }
}

async function closePosition(symbol, qty, side, btn) {
  if (btn) { btn.textContent = '...'; btn.disabled = true; }
  try {
    // Cancel any open orders for this symbol first to avoid wash trade
    await cancelOpenOrdersForSymbol(symbol);
    // Use close position endpoint — Alpaca handles this cleanly
    await api(`/positions/${symbol}`, { method: 'DELETE' });
    setTimeout(loadPortfolio, 1000);
  } catch (e) {
    if (btn) { btn.textContent = 'Close'; btn.disabled = false; }
    alert(`Error closing ${symbol}: ${e.message}`);
  }
}

async function loadOrders() {
  if (!API_KEY) { showNoCredentials('orders-body'); return; }
  document.getElementById('orders-body').innerHTML = '<div class="empty">Loading...</div>';
  try {
    const orders = await api('/orders?limit=20&status=all');
    if (!orders.length) {
      document.getElementById('orders-body').innerHTML = '<div class="empty">No orders found</div>';
      return;
    }
    const rows = orders.map(o => {
      const d = new Date(o.submitted_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      const stBadge = o.status === 'filled' ? 'filled' : o.status === 'canceled' ? 'canceled' : 'pending';
      return `<tr>
        <td><strong>${o.symbol}</strong></td>
        <td><span class="badge badge-${o.side}">${o.side}</span></td>
        <td>${o.qty}</td>
        <td><span class="badge badge-${stBadge}">${o.status}</span></td>
        <td>${o.filled_avg_price ? fmt(o.filled_avg_price) : '—'}</td>
        <td style="color:#999;font-size:11px">${d}</td>
      </tr>`;
    }).join('');
    document.getElementById('orders-body').innerHTML = `
      <table>
        <thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Status</th><th>Fill</th><th>Time</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (e) {
    document.getElementById('orders-body').innerHTML = `<div class="empty">Error: ${e.message}</div>`;
  }
}

function togglePriceFields() {
  const t = document.getElementById('t-type').value;
  document.getElementById('limit-field').style.display = (t === 'limit' || t === 'stop_limit') ? 'block' : 'none';
  document.getElementById('stop-field').style.display = (t === 'stop' || t === 'stop_limit') ? 'block' : 'none';
}

async function placeOrder(side) {
  const statusEl = document.getElementById('trade-status');
  if (!API_KEY) {
    statusEl.className = 'status error';
    statusEl.textContent = 'Please save your API credentials in Settings first.';
    return;
  }
  const symbol = document.getElementById('t-symbol').value.trim().toUpperCase();
  const qty = document.getElementById('t-qty').value;
  const type = document.getElementById('t-type').value;
  const tif = document.getElementById('t-tif').value;

  if (!symbol || !qty) {
    statusEl.className = 'status error';
    statusEl.textContent = 'Symbol and quantity are required.';
    return;
  }

  statusEl.className = 'status loading';
  statusEl.textContent = 'Submitting order...';

  const body = { symbol, qty, side, type, time_in_force: tif };
  if (type === 'limit' || type === 'stop_limit') body.limit_price = document.getElementById('t-limit').value;
  if (type === 'stop' || type === 'stop_limit') body.stop_price = document.getElementById('t-stop').value;

  try {
    const order = await api('/orders', { method: 'POST', body: JSON.stringify(body) });
    statusEl.className = 'status success';
    statusEl.textContent = `✓ ${order.side.toUpperCase()} ${order.qty} ${order.symbol} submitted (${order.type}, ${order.time_in_force.toUpperCase()}) — ID: ${order.id.slice(0, 8)}...`;
  } catch (e) {
    // Wash trade detected — cancel open orders and retry
    if (e.message && e.message.toLowerCase().includes('wash trade')) {
      statusEl.textContent = 'Wash trade detected — cancelling open orders and retrying...';
      const cancelled = await cancelOpenOrdersForSymbol(symbol);
      if (cancelled > 0) {
        await new Promise(r => setTimeout(r, 800));
        try {
          const order = await api('/orders', { method: 'POST', body: JSON.stringify(body) });
          statusEl.className = 'status success';
          statusEl.textContent = `✓ ${order.side.toUpperCase()} ${order.qty} ${order.symbol} submitted after clearing ${cancelled} open order(s).`;
          return;
        } catch (e2) {
          statusEl.className = 'status error';
          statusEl.textContent = `Error after retry: ${e2.message}`;
          return;
        }
      }
      // If no open orders to cancel, try using the close position endpoint
      if (side === 'sell') {
        try {
          await api(`/positions/${symbol}`, { method: 'DELETE' });
          statusEl.className = 'status success';
          statusEl.textContent = `✓ Position in ${symbol} closed via market order.`;
          return;
        } catch (e3) {
          statusEl.className = 'status error';
          statusEl.textContent = `Error: ${e3.message}`;
          return;
        }
      }
    }
    statusEl.className = 'status error';
    statusEl.textContent = `Error: ${e.message}`;
  }
}

function saveCredentials() {
  const key = document.getElementById('s-key').value.trim();
  const secret = document.getElementById('s-secret').value.trim();
  if (!key || !secret) return;
  chrome.storage.local.set({ alpaca_key: key, alpaca_secret: secret }, () => {
    API_KEY = key;
    API_SECRET = secret;
    const badge = document.getElementById('saved-badge');
    badge.style.display = 'inline';
    setTimeout(() => { badge.style.display = 'none'; }, 2000);
    loadPortfolio();
  });
}

function showNoCredentials(elId) {
  document.getElementById(elId).innerHTML = '<div class="empty">Go to Settings to enter your API credentials</div>';
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => showTab(tab.dataset.tab));
  });
  document.getElementById('refresh-portfolio').addEventListener('click', loadPortfolio);
  document.getElementById('refresh-orders').addEventListener('click', loadOrders);
  document.getElementById('t-type').addEventListener('change', togglePriceFields);
  document.getElementById('btn-buy').addEventListener('click', () => placeOrder('buy'));
  document.getElementById('btn-sell').addEventListener('click', () => placeOrder('sell'));
  document.getElementById('btn-save').addEventListener('click', saveCredentials);

  chrome.storage.local.get(['alpaca_key', 'alpaca_secret'], (result) => {
    if (result.alpaca_key && result.alpaca_secret) {
      API_KEY = result.alpaca_key;
      API_SECRET = result.alpaca_secret;
      document.getElementById('s-key').value = result.alpaca_key;
      document.getElementById('s-secret').value = result.alpaca_secret;
      loadPortfolio();
    } else {
      showNoCredentials('positions-body');
    }
  });
});
