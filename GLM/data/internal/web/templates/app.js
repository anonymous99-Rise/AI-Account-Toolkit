"use strict";

const $ = id => document.getElementById(id);
let state = { key: localStorage.getItem('mc_local_key') || '', currentAcc: null, conversationId: localStorage.getItem('mc_conv_id') || '' };
let defaultSystem = '';

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (state.key) headers['X-API-Key'] = state.key;
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401) {
    let hint = '';
    try {
      const j = await res.clone().json();
      hint = ((j.error && j.error.message) || '') + ' ' + ((j.error && j.error.type) || '');
    } catch (e) { /* ignore */ }
    if (hint.indexOf('/login') !== -1 || hint.indexOf('登录') !== -1) {
      location.href = '/login';
    }
  }
  return res;
}

function setHealth(ok, text) {
  $('healthDot').className = 'dot ' + (ok ? 'ok' : 'bad');
  $('healthText').textContent = text;
}

function flash(btn, text) {
  const old = btn.textContent;
  btn.textContent = text;
  setTimeout(() => { btn.textContent = old; }, 1200);
}

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/* ==================== Tab 切换 ==================== */
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'accounts') loadAccounts();
    if (btn.dataset.tab === 'settings') { loadKeyPool(); loadProxies(); }
  });
});

/* ==================== 通用 ==================== */
async function loadConfig() {
  try {
    const res = await api('/api/config');
    if (res.status === 401) { setHealth(false, '缺少本地 key，请到系统设置粘贴'); return; }
    const cfg = await res.json();
    defaultSystem = cfg.default_system_prompt || '';
    if (!$('system').value) $('system').value = defaultSystem;
    if (!$('globalSystem').value) $('globalSystem').value = defaultSystem;
    setHealth(true, 'online');
  } catch (e) {
    setHealth(false, 'offline');
  }
}

function bindSlider(id, outId) {
  $(id).addEventListener('input', () => { $(outId).textContent = $(id).value; });
}
bindSlider('temperature', 'tempVal');
bindSlider('top_p', 'toppVal');
bindSlider('accTemperature', 'accTempVal');
bindSlider('accTopP', 'accToppVal');

$('saveKey').addEventListener('click', () => {
  const v = $('apiKey').value.trim();
  if (!v) return;
  state.key = v;
  localStorage.setItem('mc_local_key', v);
  flash($('saveKey'), '已保存');
  loadKeyPool();
});
$('apiKey').addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); $('saveKey').click(); }
});
$('resetSys').addEventListener('click', () => { $('system').value = defaultSystem; });

/* 全局默认系统提示词：网页输入 → 保存写入 data/system_prompt.txt */
$('saveGlobalSystem').addEventListener('click', async () => {
  const val = $('globalSystem').value;
  const res = await api('/api/config', { method: 'PUT', body: JSON.stringify({ system_prompt: val }) });
  if (res.ok) {
    defaultSystem = val;
    $('system').value = val; // 同步到 Playground tab 的系统提示词
    flash($('saveGlobalSystem'), '已写入文件');
  } else {
    let msg = 'HTTP ' + res.status;
    try { const j = await res.json(); msg = (j.error && j.error.message) || msg; } catch (e) { /* ignore */ }
    alert('保存失败：' + msg);
  }
});
$('resetGlobalSystem').addEventListener('click', () => { $('globalSystem').value = defaultSystem; });
$('globalSystem').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); $('saveGlobalSystem').click(); }
});

/* ==================== Playground 对话 ==================== */
function addMsg(containerId, role, text) {
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + role;
  const head = document.createElement('div');
  head.className = 'msg-head';
  head.textContent = role === 'user' ? 'YOU' : 'MISTRAL';
  const body = document.createElement('div');
  body.className = 'msg-body';
  body.textContent = text;
  wrap.appendChild(head);
  wrap.appendChild(body);
  $(containerId).appendChild(wrap);
  $(containerId).scrollTop = $(containerId).scrollHeight;
  return body;
}

function collectTools() {
  const arr = [];
  if ($('tool_code').checked) arr.push({ type: 'code_interpreter' });
  if ($('tool_image').checked) arr.push({ type: 'image_generation' });
  if ($('tool_search').checked) arr.push({ type: 'web_search', open_results: false });
  if ($('tool_local').checked) arr.push(
    { type: 'function', function: { name: 'list_directory', description: '列出目录', parameters: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] } } },
    { type: 'function', function: { name: 'read_file', description: '读取文件', parameters: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] } } },
    { type: 'function', function: { name: 'write_file', description: '写入文件', parameters: { type: 'object', properties: { path: { type: 'string' }, content: { type: 'string' } }, required: ['path', 'content'] } } },
    { type: 'function', function: { name: 'append_file', description: '追加文件', parameters: { type: 'object', properties: { path: { type: 'string' }, content: { type: 'string' } }, required: ['path', 'content'] } } },
  );
  return arr.length ? arr : null;
}

function parseSSEBlock(block, cb) {
  for (const line of block.split('\n')) {
    const t = line.trim();
    if (!t.startsWith('data:')) continue;
    const data = t.slice(5).trim();
    if (data === '[DONE]') continue;
    let j;
    try { j = JSON.parse(data); } catch (e) { continue; }
    cb(j);
  }
}

async function send() {
  const text = $('input').value.trim();
  if (!text || $('send').disabled) return;
  if (!state.key) { alert('请先在左上填入本地 API Key 并保存'); return; }
  $('input').value = '';
  addMsg('messages', 'user', text);

  const sysVal = $('system').value.trim();
  const messages = [];
  if (sysVal) messages.push({ role: 'system', content: sysVal });
  messages.push({ role: 'user', content: text });

  const body = {
    model: $('model').value,
    messages,
    temperature: parseFloat($('temperature').value),
    top_p: parseFloat($('top_p').value),
    max_tokens: parseInt($('max_tokens').value, 10),
    reasoning_effort: $('reasoning_effort').value,
    stream: true,
  };
  if (state.conversationId) body.conversation_id = state.conversationId;
  const tools = collectTools();
  if (tools) body.tools = tools;

  const botBody = addMsg('messages', 'assistant', '');
  const cursor = document.createElement('span');
  cursor.className = 'cursor';
  botBody.appendChild(cursor);
  $('send').disabled = true;
  $('send').textContent = '…';

  try {
    const res = await api('/v1/chat/completions', { method: 'POST', body: JSON.stringify(body) });
    const cid = res.headers.get('X-Conversation-ID');
    if (cid) {
      state.conversationId = cid;
      localStorage.setItem('mc_conv_id', cid);
      setHealth(true, 'conv ' + cid.slice(0, 20) + '…');
    }
    if (!res.ok) {
      let msg = 'HTTP ' + res.status;
      try { const j = await res.json(); msg = (j.error && j.error.message) || msg; } catch (e) { /* ignore */ }
      cursor.remove();
      botBody.textContent = '❌ ' + msg;
      return;
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '', full = '', reasoning = '';
    const reasoningEl = document.createElement('div');
    reasoningEl.className = 'reasoning';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        parseSSEBlock(block, j => {
          const d = (j.choices && j.choices[0] && j.choices[0].delta) || {};
          if (d.reasoning_content) {
            reasoning += d.reasoning_content;
            reasoningEl.textContent = '⟡ ' + reasoning;
            if (!reasoningEl.parentNode) botBody.insertBefore(reasoningEl, cursor);
          }
          if (d.content) {
            full += d.content;
            cursor.textContent = full;
          }
          if (d.tool_calls) {
            const tc = d.tool_calls[0];
            if (tc && tc.function && tc.function.name) {
              const el = document.createElement('div');
              el.className = 'toolcall';
              el.textContent = '⚙ tool: ' + tc.function.name;
              botBody.insertBefore(el, cursor);
            }
          }
        });
      }
      $('messages').scrollTop = $('messages').scrollHeight;
    }
    cursor.remove();
    if (!full) botBody.textContent = reasoning ? '（仅输出推理过程）' : '（空响应）';
  } catch (e) {
    cursor.remove();
    botBody.textContent = '❌ ' + e.message;
  } finally {
    $('send').disabled = false;
    $('send').textContent = '发送';
  }
}
$('send').addEventListener('click', send);
$('input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});

$('newConv').addEventListener('click', () => {
  if (!confirm('开启全新会话？当前会话 id 将重置。')) return;
  state.conversationId = '';
  localStorage.removeItem('mc_conv_id');
  $('convStatus').textContent = '新会话（未开始）';
  $('messages').innerHTML = '<div class="hint">已开启全新会话。</div>';
});
function renderConvStatus() {
  const cid = state.conversationId;
  $('convStatus').textContent = cid ? '会话: ' + cid.slice(0, 28) + '…' : '新会话';
}
renderConvStatus();

/* ==================== 账号管理 ==================== */
async function loadAccounts() {
  try {
    const res = await api('/api/accounts');
    if (res.status !== 200) return;
    const j = await res.json();
    const list = j.accounts || [];
    const box = $('acctList');
    box.innerHTML = '';
    for (const a of list) {
      const item = document.createElement('div');
      item.className = 'acct-item' + (state.currentAcc === a.id ? ' active' : '');
      const head = document.createElement('div');
      head.className = 'acct-item-head';
      const title = document.createElement('span');
      title.innerHTML = '<strong>' + escapeHtml(a.name) + '</strong> <span class="muted">' + escapeHtml(a.model) + '</span>';
      const greetBtn = document.createElement('button');
      greetBtn.className = 'mini';
      greetBtn.textContent = '打招呼';
      greetBtn.addEventListener('click', e => { e.stopPropagation(); greetAccount(a, greetBtn); });
      const resetBtn = document.createElement('button');
      resetBtn.className = 'mini';
      resetBtn.textContent = '新会话';
      resetBtn.addEventListener('click', e => { e.stopPropagation(); resetAccount(a, resetBtn); });
      head.appendChild(title);
      head.appendChild(resetBtn);
      head.appendChild(greetBtn);
      item.appendChild(head);
      const sub = document.createElement('div');
      sub.className = 'muted small';
      sub.textContent = (a.conversation_id ? '会话 ' + a.conversation_id.slice(0, 18) + '…' : '新会话') +
        ' · ' + (a.history ? a.history.length / 2 : 0) + ' 轮';
      item.appendChild(sub);
      item.addEventListener('click', () => selectAccount(a));
      box.appendChild(item);
    }
  } catch (e) { /* ignore */ }
}

async function greetAccount(a, btn) {
  btn.disabled = true;
  try {
    const res = await api('/api/accounts/' + a.id + '/greet', { method: 'POST' });
    const j = await res.json();
    if (res.ok) {
      flash(btn, '✓ 已建会话');
      if (state.currentAcc === a.id && j.conversation_id) $('acctConv').textContent = 'conv: ' + j.conversation_id;
      loadAccounts();
    } else {
      flash(btn, '✗');
      alert('打招呼失败: ' + ((j.error && j.error.message) || 'HTTP ' + res.status));
    }
  } catch (e) {
    flash(btn, '✗');
    alert('打招呼失败: ' + e.message);
  } finally {
    btn.disabled = false;
  }
}

async function resetAccount(a, btn) {
  if (!confirm('确认新建会话？当前会话历史将清空。')) return;
  btn.disabled = true;
  try {
    const res = await api('/api/accounts/' + a.id + '/reset', { method: 'POST' });
    if (res.ok) {
      flash(btn, '✓ 已重置');
      if (state.currentAcc === a.id) {
        $('acctConv').textContent = '未开始';
        $('accMessages').innerHTML = '<div class="hint">会话已重置为全新会话。</div>';
      }
      loadAccounts();
    } else {
      flash(btn, '✗');
    }
  } catch (e) {
    flash(btn, '✗');
  } finally {
    btn.disabled = false;
  }
}

function selectAccount(a) {
  state.currentAcc = a.id;
  $('acctTitle').textContent = a.name;
  $('acctConv').textContent = a.conversation_id ? 'conv: ' + a.conversation_id : '未开始';
  $('accTemperature').value = a.temperature || 0.7;
  $('accTempVal').textContent = a.temperature || 0.7;
  $('accTopP').value = (a.top_p !== undefined && a.top_p !== null) ? a.top_p : 1.0;
  $('accToppVal').textContent = (a.top_p !== undefined && a.top_p !== null) ? a.top_p : 1.0;
  $('accMaxTokens').value = a.max_tokens || 4096;
  $('accReasoning').value = a.reasoning_effort || 'none';
  $('accSystem').value = a.system_prompt || '';
  const tools = a.tools || ['code_interpreter', 'image_generation', 'web_search'];
  $('accToolCode').checked = tools.indexOf('code_interpreter') !== -1;
  $('accToolImage').checked = tools.indexOf('image_generation') !== -1;
  $('accToolSearch').checked = tools.indexOf('web_search') !== -1;
  const msgs = $('accMessages');
  msgs.innerHTML = '';
  for (const m of (a.history || [])) {
    const role = m.role === 'user' ? 'user' : 'assistant';
    const wrap = document.createElement('div');
    wrap.className = 'msg ' + role;
    const head = document.createElement('div');
    head.className = 'msg-head';
    head.textContent = role === 'user' ? 'YOU' : a.name;
    const body = document.createElement('div');
    body.className = 'msg-body';
    body.textContent = m.content;
    wrap.appendChild(head);
    wrap.appendChild(body);
    msgs.appendChild(wrap);
  }
  msgs.scrollTop = msgs.scrollHeight;
  loadAccounts(); // 刷新高亮
}

$('newAccBtn').addEventListener('click', async () => {
  const name = $('newAccName').value.trim() || ('账号 ' + Date.now().toString().slice(-4));
  const model = $('newAccModel').value;
  const res = await api('/api/accounts', { method: 'POST', body: JSON.stringify({ name, model }) });
  if (res.ok) {
    $('newAccName').value = '';
    const j = await res.json();
    loadAccounts();
    selectAccount(j.account);
  }
});
$('newAccName').addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); $('newAccBtn').click(); }
});

$('batchBtn').addEventListener('click', async () => {
  const count = Math.min(Math.max(parseInt($('batchCount').value, 10) || 1, 1), 100);
  const model = $('batchModel').value;
  const prefix = $('batchPrefix').value.trim() || '批量号';
  const greet = $('batchGreet').checked;
  const btn = $('batchBtn');
  btn.disabled = true;
  $('batchStatus').textContent = '正在批量注册 ' + count + ' 个（并发 3）…';
  try {
    const res = await api('/api/accounts/batch', { method: 'POST', body: JSON.stringify({ count, model, prefix, greet }) });
    const j = await res.json();
    if (res.ok) {
      const okN = (j.created || []).length;
      const errs = (j.errors || []);
      $('batchStatus').textContent = errs.length
        ? '✅ 成功 ' + okN + ' 个，失败 ' + errs.length + ' 个：' + errs.join('；')
        : '✅ 成功 ' + okN + ' 个，全部成功';
      loadAccounts();
    } else {
      $('batchStatus').textContent = '❌ ' + ((j.error && j.error.message) || 'HTTP ' + res.status);
    }
  } catch (e) {
    $('batchStatus').textContent = '❌ ' + e.message;
  } finally {
    btn.disabled = false;
  }
});
$('batchPrefix').addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); $('batchBtn').click(); }
});

function collectAccTools() {
  const arr = [];
  if ($('accToolCode').checked) arr.push('code_interpreter');
  if ($('accToolImage').checked) arr.push('image_generation');
  if ($('accToolSearch').checked) arr.push('web_search');
  return arr;
}

$('accApplyParams').addEventListener('click', async () => {
  if (!state.currentAcc) { alert('先选择账号'); return; }
  const body = {
    temperature: parseFloat($('accTemperature').value),
    top_p: parseFloat($('accTopP').value),
    max_tokens: parseInt($('accMaxTokens').value, 10),
    reasoning_effort: $('accReasoning').value,
    system_prompt: $('accSystem').value,
    tools: collectAccTools(),
  };
  const res = await api('/api/accounts/' + state.currentAcc, { method: 'PUT', body: JSON.stringify(body) });
  if (res.ok) { flash($('accApplyParams'), '已保存'); loadAccounts(); }
});

$('accDelete').addEventListener('click', async () => {
  if (!state.currentAcc) { alert('先选择账号'); return; }
  if (!confirm('确认删除该账号及其会话？')) return;
  const res = await api('/api/accounts/' + state.currentAcc, { method: 'DELETE' });
  if (res.ok) {
    state.currentAcc = null;
    $('acctTitle').textContent = '未选择账号';
    $('acctConv').textContent = '';
    $('accMessages').innerHTML = '<div class="hint">账号已删除。</div>';
    loadAccounts();
  }
});

async function sendAccountMsg() {
  const text = $('accInput').value.trim();
  if (!text || !state.currentAcc) { alert('先选择账号'); return; }
  $('accInput').value = '';
  addMsg('accMessages', 'user', text);
  const botBody = addMsg('accMessages', 'assistant', '…');
  $('accSend').disabled = true;
  try {
    const res = await api('/api/accounts/' + state.currentAcc + '/chat', { method: 'POST', body: JSON.stringify({ message: text }) });
    const j = await res.json();
    if (res.ok) {
      botBody.textContent = j.reply || '（空响应）';
      if (j.conversation_id) $('acctConv').textContent = 'conv: ' + j.conversation_id;
      loadAccounts();
    } else {
      botBody.textContent = '❌ ' + ((j.error && j.error.message) || 'HTTP ' + res.status);
    }
  } catch (e) {
    botBody.textContent = '❌ ' + e.message;
  } finally {
    $('accSend').disabled = false;
  }
}
$('accSend').addEventListener('click', sendAccountMsg);
$('accInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAccountMsg(); }
});

/* ==================== 系统设置 ==================== */
async function loadKeyPool() {
  try {
    const res = await api('/api/settings/keys');
    if (res.status !== 200) return;
    const j = await res.json();
    const snap = j.snapshot;
    if (snap.local_keys) {
      const lkList = $('localKeyList');
      lkList.innerHTML = '';
      for (const lk of (snap.local_keys || [])) {
        const row = document.createElement('div');
        row.className = 'row keyrow';
        const code = document.createElement('code');
        code.className = 'mono';
        code.textContent = lk;
        const del = document.createElement('button');
        del.className = 'mini danger';
        del.textContent = '删';
        del.addEventListener('click', async () => {
          await api('/api/settings/keys', { method: 'DELETE', body: JSON.stringify({ key: lk, type: 'local' }) });
          loadKeyPool();
        });
        row.appendChild(code);
        row.appendChild(del);
        lkList.appendChild(row);
      }
      if (!(snap.local_keys || []).length) lkList.innerHTML = '<span class="muted">—</span>';
      $('localKeyRow2').textContent = (snap.local_keys || []).join('\n') || '—';
    }
    const tb = $('upstreamKeyRows');
    tb.innerHTML = '';
    for (const u of (snap.upstream || [])) {
      const tr = document.createElement('tr');
      const st = document.createElement('td');
      st.className = u.healthy ? 'st-ok' : 'st-bad';
      st.textContent = u.healthy ? '可用' : '冷却';
      tr.appendChild(st);
      tr.insertAdjacentHTML('beforeend',
        '<td class="mono">' + escapeHtml(u.masked_key) + '</td>' +
        '<td>' + escapeHtml(u.source || '') + '</td>' +
        '<td>' + escapeHtml(u.last_error || '') + '</td>');
      const tdDel = document.createElement('td');
      const btn = document.createElement('button');
      btn.className = 'mini danger';
      btn.textContent = '删';
      btn.addEventListener('click', async () => {
        await api('/api/settings/keys', { method: 'DELETE', body: JSON.stringify({ key: u.masked_key }) });
        loadKeyPool();
      });
      tdDel.appendChild(btn);
      tr.appendChild(tdDel);
      tb.appendChild(tr);
    }
  } catch (e) { /* ignore */ }
}

$('addUpstreamKey').addEventListener('click', async () => {
  const key = $('newUpstreamKey').value.trim();
  if (!key) return;
  const res = await api('/api/settings/keys', { method: 'POST', body: JSON.stringify({ key, source: 'manual' }) });
  if (res.ok) {
    $('newUpstreamKey').value = '';
    flash($('addUpstreamKey'), '已添加');
    loadKeyPool();
  } else {
    alert('添加失败');
  }
});
$('newUpstreamKey').addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); $('addUpstreamKey').click(); }
});

/* 本地 API Key（对外出口） */
$('addLocalKey').addEventListener('click', async () => {
  const key = $('newLocalKey').value.trim();
  if (!key) { alert('请输入本地 key'); return; }
  const res = await api('/api/settings/keys', { method: 'POST', body: JSON.stringify({ key, type: 'local' }) });
  if (res.ok) {
    $('newLocalKey').value = '';
    flash($('addLocalKey'), '已添加');
    loadKeyPool();
  } else {
    let msg = 'HTTP ' + res.status;
    try { const j = await res.json(); msg = (j.error && j.error.message) || msg; } catch (e) { /* ignore */ }
    alert('添加失败：' + msg);
  }
});
$('newLocalKey').addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); $('addLocalKey').click(); }
});

/* 代理池 */
async function loadProxies() {
  try {
    const res = await api('/api/proxies');
    if (res.status !== 200) return;
    const j = await res.json();
    const tb = $('proxyRows');
    tb.innerHTML = '';
    for (const p of (j.proxies || [])) {
      const tr = document.createElement('tr');
      const lat = p.latency_ms > 0 ? p.latency_ms + 'ms' : (p.latency_ms === -1 ? '未知' : p.latency_ms + 'ms');
      tr.insertAdjacentHTML('beforeend',
        '<td class="mono">' + escapeHtml(p.addr) + '</td>' +
        '<td>' + escapeHtml(p.type) + '</td>' +
        '<td>' + (p.enabled ? lat : '停用') + '</td>' +
        '<td>' + (p.enabled ? '<span class="st-ok">启用</span>' : '<span class="st-bad">停用</span>') +
        (p.disabled_reason ? ' <span class="muted">' + escapeHtml(p.disabled_reason) + '</span>' : '') + '</td>');
      const tdAct = document.createElement('td');
      const btn = document.createElement('button');
      btn.className = 'mini';
      btn.textContent = p.enabled ? '停用' : '启用';
      btn.addEventListener('click', async () => {
        await api('/api/proxies/' + p.id + '/' + (p.enabled ? 'disable' : 'enable'), { method: 'POST' });
        loadProxies();
      });
      tdAct.appendChild(btn);
      const btnDel = document.createElement('button');
      btnDel.className = 'mini danger';
      btnDel.textContent = '删';
      btnDel.addEventListener('click', async () => {
        await api('/api/proxies', { method: 'DELETE', body: JSON.stringify({ id: p.id }) });
        loadProxies();
      });
      tdAct.appendChild(btnDel);
      tr.appendChild(tdAct);
      tb.appendChild(tr);
    }
  } catch (e) { /* ignore */ }
}

$('addProxy').addEventListener('click', async () => {
  const addr = $('newProxyAddr').value.trim();
  if (!addr) return;
  const type = $('newProxyType').value;
  const res = await api('/api/proxies', { method: 'POST', body: JSON.stringify({ addr, type }) });
  if (res.ok) {
    $('newProxyAddr').value = '';
    flash($('addProxy'), '已添加');
    loadProxies();
  }
});
$('checkProxies').addEventListener('click', async () => {
  $('checkProxies').textContent = '检测中…';
  await api('/api/proxies/check', { method: 'POST' });
  flash($('checkProxies'), '完成');
  loadProxies();
});

/* Key 池弹窗 */
$('showKeys').addEventListener('click', () => { loadKeyPool(); $('keyModal').classList.remove('hidden'); });
$('closeKeys').addEventListener('click', () => $('keyModal').classList.add('hidden'));
$('keyModal').addEventListener('click', e => { if (e.target === $('keyModal')) $('keyModal').classList.add('hidden'); });

setInterval(async () => {
  try {
    const r = await fetch('/healthz');
    setHealth(r.ok, r.ok ? 'online' : 'degraded');
  } catch (e) {
    setHealth(false, 'offline');
  }
}, 15000);

loadConfig();