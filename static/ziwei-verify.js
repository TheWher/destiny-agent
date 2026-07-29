// 紫微斗数验盘系统
// 全局状态
let reportPw = sessionStorage.getItem('ziwei_pw') || '';
let verificationData = null;
let verifiedEvents = null;

// 渲染验盘确认面板
function renderVerification(analysisText) {
  const area = document.getElementById('analysis-text');
  if (!area) return;
  const lines = analysisText.split('\n');
  const items = [];
  let inVer = false;
  for (const line of lines) {
    if (line.includes('命盘验证') || line.includes('验盘') || line.includes('验盘环节')) { inVer = true; continue; }
    if (line.includes('验盘完毕')) break;
    if (!inVer) continue;
    const m = line.match(/(\d{4})\s*年.*?[：:]\s*(.+)/);
    if (m) {
      items.push({ year: m[1], desc: m[2].trim().substring(0, 100), label: 'pending' });
    }
  }
  verificationData = { predictions: items, rawText: analysisText };
  if (items.length === 0) {
    area.innerHTML = formatText(analysisText);
    return;
  }
  let html = '<div class="verify-panel"><h3>验盘确认</h3>';
  html += '<p style="font-size:12px;color:var(--ink-soft);margin:0 0 12px">';
  html += 'Agent 根据命盘信号推断了以下事件。请逐条确认，帮助 Agent 校准判断。</p>';
  items.forEach(function(item, i) {
    html += '<div class="verify-item" id="vi-' + i + '" style="border:1px solid var(--line-soft);padding:10px;margin-bottom:8px;border-radius:4px;display:flex;align-items:flex-start;gap:8px">';
    html += '<div style="flex:1"><strong>' + item.year + '年</strong><br>';
    html += '<span style="font-size:13px;color:var(--ink-soft)">' + escapeHtml(item.desc) + '</span></div>';
    html += '<div style="display:flex;gap:4px;flex-shrink:0">';
    html += '<button onclick="verifyMark(' + i + ',\'correct\')" style="padding:4px 10px;font-size:12px;border:1px solid var(--jade);background:transparent;color:var(--jade);cursor:pointer;border-radius:2px;font-family:inherit">正确</button>';
    html += '<button onclick="verifyMark(' + i + ',\'wrong\')" style="padding:4px 10px;font-size:12px;border:1px solid var(--vermillion);background:transparent;color:var(--vermillion);cursor:pointer;border-radius:2px;font-family:inherit">错误</button>';
    html += '<button onclick="verifyMark(' + i + ',\'partial\')" style="padding:4px 10px;font-size:12px;border:1px solid var(--ink-soft);background:transparent;color:var(--ink-soft);cursor:pointer;border-radius:2px;font-family:inherit">部分对</button>';
    html += '</div></div>';
  });
  html += '<div style="display:flex;gap:8px;margin-top:12px">';
  html += '<button onclick="verifyConfirm()" id="btn-verify-confirm" style="flex:1;padding:10px;background:var(--ink);color:var(--paper);border:none;cursor:pointer;border-radius:4px;font-family:inherit;font-size:14px">确认并正式解读</button>';
  html += '<button onclick="verifySkip()" style="padding:10px 16px;border:1px solid var(--line-soft);background:var(--paper);color:var(--ink);cursor:pointer;border-radius:4px;font-family:inherit;font-size:13px">跳过验盘</button>';
  html += '</div></div>';
  area.innerHTML = html;
  area.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function verifyMark(index, label) {
  var el = document.getElementById('vi-' + index);
  if (!el || !verificationData) return;
  verificationData.predictions[index].label = label;
  if (label === 'correct') {
    el.querySelector('strong').style.color = 'var(--jade)';
    // 移除错误原因选择器
    var er = el.querySelector('.error-reason-row');
    if (er) er.style.display = 'none';
  } else {
    if (label === 'wrong') el.querySelector('strong').style.color = 'var(--vermillion)';
    else el.querySelector('strong').style.color = 'var(--ink-soft)';
    // 显示错误原因下拉
    var er = el.querySelector('.error-reason-row');
    if (!er) {
      er = document.createElement('div');
      er.className = 'error-reason-row';
      er.style.cssText = 'margin-top:6px;font-size:12px';
      er.innerHTML = '<span style="color:var(--ink-soft)">错误原因：</span>' +
        '<select class="err-reason-sel" style="font-size:11px;padding:2px 4px;border:1px solid var(--line-soft);border-radius:2px;background:var(--paper);color:var(--ink);font-family:inherit;margin-left:4px">' +
        '<option value="">选择原因</option>' +
        '<option value="time_shift">时间偏移(&gt;3年)</option>' +
        '<option value="type_confusion">事件类型混淆</option>' +
        '<option value="intensity_wrong">强度过高/过低</option>' +
        '<option value="signal_invalid">信号不存在/错读</option>' +
        '<option value="user_memory">用户记忆偏差</option>' +
        '<option value="other">其他</option>' +
        '</select>';
      el.appendChild(er);
    }
    er.style.display = 'block';
  }
}

function verifySkip() {
  verifiedEvents = null;
  verificationData = null;
  startAnalysisFull();
}

async function verifyConfirm() {
  if (!verificationData || !plateData) return;
  var btn = document.getElementById('btn-verify-confirm');
  if (btn) { btn.disabled = true; btn.textContent = '提交中...'; }
  verifiedEvents = [];
  var feedbackPredictions = [];
  verificationData.predictions.forEach(function(p) {
    var label = p.label === 'correct' ? 'correct' : p.label === 'wrong' ? 'wrong' : (p.label || 'pending');
    verifiedEvents.push({ year: p.year, desc: p.desc, label: label });
    // 构建反馈数据（含错误原因）
    var fb = { year: p.year, desc: p.desc, user_label: label };
    if (p.label !== 'correct') {
      // 从 DOM 中读取错误原因
      var el = document.getElementById('vi-' + verificationData.predictions.indexOf(p));
      if (el) {
        var sel = el.querySelector('.err-reason-sel');
        fb.error_reason = sel ? sel.value : '';
      }
    }
    feedbackPredictions.push(fb);
  });

  // 异步保存反馈（不阻塞流程）
  var source = 'verification_triggered';
  fetch('/api/ziwei/verify', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: (typeof sid !== 'undefined' ? sid : ''),
      plate: plateData,
      predictions: feedbackPredictions,
      source: source
    })
  }).catch(function(){});

  startAnalysisFull();
}

// 验证通过后，发起正式完整分析（流式）
async function startAnalysisFull() {
  var area = document.getElementById('analysis-text');
  if (!area) return;
  area.innerHTML = '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:200px;gap:12px;padding:40px 20px">' +
    '<div id="loading-orb-full"></div>' +
    '<div style="font-size:16px;font-weight:700;color:var(--ink)">正在深度解读</div>' +
    '<div style="font-size:12px;color:var(--ink-soft);width:300px;line-height:1.7;text-align:center">已校准验盘事件，正在生成完整分析<br>约需 2~4 分钟</div></div>';
  setTimeout(function(){ var el=document.getElementById("loading-orb-full"); if(el) createThinkingOrb({state:"working",size:64,container:el}); },100);
  try {
    var body = { plate: plateData, password: reportPw || '' };
    if (verifiedEvents) { body.verified_events = verifiedEvents; }
    var r = await fetch('/api/ziwei/analyze/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) { area.innerHTML = '<span style="color:var(--vermillion)">请求失败</span>'; return; }
    var reader = r.body.getReader();
    var decoder = new TextDecoder();
    var buf = '', rawText = '', firstToken = true;
    while (true) {
      var result = await reader.read();
      if (result.done) break;
      buf += decoder.decode(result.value, { stream: true });
      var parts = buf.split('\n\n'); buf = parts.pop();
      for (var p of parts) {
        var partLines = p.split('\n');
        for (var pl of partLines) {
          if (!pl.startsWith('data: ')) continue;
          try {
            var evt = JSON.parse(pl.slice(6));
            if (evt.type === 'content_block_delta' && evt.delta && evt.delta.text) {
              rawText += evt.delta.text;
              if (firstToken) { firstToken = false; area.innerHTML = ''; }
              area.innerText = rawText;
            }
          } catch (e) { }
        }
      }
    }
    reader.cancel();
    if (rawText) {
      area.innerHTML = formatText(rawText);
      area.scrollIntoView({ behavior: 'smooth', block: 'start' });
      await fetch('/api/ziwei/sessions/' + sid, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [{ role: 'assistant', content: rawText }] })
      });
    }
  } catch (e) {
    area.innerHTML = '<span style="color:var(--vermillion)">连接中断: ' + e.message + '</span>';
  }
}

// 会话列表加载（供报告页使用）
async function loadSessionList() {
  try {
    var r = await fetch('/api/ziwei/sessions');
    var list = await r.json();
    var sel = document.getElementById('session-switcher');
    if (!sel) return;
    sel.innerHTML = '<option value="">历史会话 (' + list.length + ')</option>';
    list.forEach(function(s) {
      var date = (s.created_at || '').slice(0, 10);
      var summary = s.plate_summary || '';
      var opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = (date ? date + ' ' : '') + summary.slice(0, 24);
      if (s.id === sid) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch (e) { }
}

function switchSession() {
  var sel = document.getElementById('session-switcher');
  if (sel.value && sel.value !== sid) {
    window.location.href = '/ziwei/report/' + sel.value;
  }
}

async function renameCurrentSession() {
  if (!sid) return;
  var old = '';
  try {
    var r = await fetch('/api/ziwei/sessions/' + sid);
    var s = await r.json();
    old = s.title || s.plate_summary || '';
  } catch (e) { }
  var nw = prompt('重命名会话：', old);
  if (!nw || nw === old) return;
  try {
    await fetch('/api/ziwei/sessions/' + sid, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: nw })
    });
    // 只更新当前选中项文字，不全量重建
    var sel = document.getElementById('session-switcher');
    if (sel && sel.selectedIndex >= 0) {
      var opt = sel.options[sel.selectedIndex];
      var date = (opt.textContent || '').split(' ')[0];
      opt.textContent = date + ' ' + nw.slice(0, 24);
    }
    toast('已重命名');
  } catch (e) { alert('重命名失败'); }
}

async function deleteCurrentSession() {
  if (!sid) return;
  if (!confirm('确定删除当前命盘会话？')) return;
  try {
    await fetch('/api/ziwei/sessions/' + sid, { method: 'DELETE' });
    toast('已删除，即将返回');
    setTimeout(function() { window.location.href = '/ziwei'; }, 600);
  } catch (e) { alert('删除失败'); }
}

function toast(msg) {
  var d = document.createElement('div');
  d.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:var(--ink);color:var(--paper);padding:8px 20px;border-radius:4px;font-size:13px;z-index:999;font-family:inherit;opacity:0;transition:opacity .3s';
  d.textContent = msg;
  document.body.appendChild(d);
  requestAnimationFrame(function() { d.style.opacity = '1'; });
  setTimeout(function() { d.style.opacity = '0'; setTimeout(function() { d.remove(); }, 300); }, 1500);
}

function copyReportLink() {
  var url = window.location.href;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(function() { toast('链接已复制'); });
  } else {
    var ta = document.createElement('textarea');
    ta.value = url; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
    toast('链接已复制');
  }
}
