// 付费层级前端工具 — 限流提醒 + 升级引导
// 各页面通过 <script src="/static/tier.js"></script> 引入

(function () {
  'use strict';

  // ---- 升级提示 UI ----
  function showUpgradeToast(msg, tier) {
    const existing = document.getElementById('tier-upgrade-toast');
    if (existing) existing.remove();

    const isFree = tier === 'free';
    const div = document.createElement('div');
    div.id = 'tier-upgrade-toast';
    div.style.cssText = [
      'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:9999',
      'background:var(--bg-card,#1a1a2e);color:var(--text,#e0d8c8)',
      'border:1px solid var(--border,#d4a843)',
      'border-radius:8px;padding:14px 20px;font-size:13px',
      'font-family:inherit;max-width:420px;text-align:center',
      'box-shadow:0 4px 24px rgba(0,0,0,.3)',
      'animation:tierFadeIn .3s ease',
    ].join(';');

    let body = '<div style="margin-bottom:4px">' + escapeHtml(msg) + '</div>';
    if (isFree) {
      body += '<div style="color:var(--ink-faint,#999);font-size:11px;margin-bottom:10px">';
      body += 'Pro 解锁 20 次/时 · 无限追问 · 大限流年解读即将上线';
      body += '</div>';
      body += '<button id="tier-upgrade-btn" style="';
      body += 'background:linear-gradient(135deg,#d4a843,#b8860b);color:#fff;border:none;';
      body += 'padding:6px 16px;border-radius:4px;cursor:pointer;font-size:12px;font-family:inherit';
      body += '" onclick="window._tierOpenAuth()">✨ 升级 Pro</button>';
    }
    div.innerHTML = body;

    // auto-dismiss
    const close = document.createElement('span');
    close.textContent = ' ✕';
    close.style.cssText = 'position:absolute;top:6px;right:10px;cursor:pointer;font-size:14px;opacity:.6';
    close.onclick = function () { div.remove(); };
    div.appendChild(close);

    document.body.appendChild(div);

    // 15s 自动消失
    setTimeout(function () { if (div.parentNode) div.remove(); }, 15000);
  }

  // ---- 打开登录/注册弹窗 ----
  window._tierOpenAuth = function () {
    const el = document.getElementById('authModal');
    if (el) {
      el.style.display = 'flex';
      return;
    }
    // fallback: 滚动到登录区域
    const authBtn = document.getElementById('btn-show-auth');
    if (authBtn) authBtn.click();
  };

  // ---- HTTP 错误处理 ----
  // 在 fetch 响应的 catch 或 !r.ok 分支中调用
  window.handleApiError = async function (response) {
    try {
      const d = await response.clone().json();
      if (d.rate_limited) {
        showUpgradeToast(d.error || '请求频繁，请稍后再试', d.tier);
        return true; // 已处理
      }
    } catch (e) { /* not JSON */ }
    return false;
  };

  window.showUpgradeToast = showUpgradeToast;

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  // ---- 注入动画 ----
  var style = document.createElement('style');
  style.textContent = '@keyframes tierFadeIn{from{opacity:0;transform:translateX(-50%) translateY(12px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}';
  document.head.appendChild(style);
})();
