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
      body += 'Pro 解锁 20 次/时 · 无限追问 · 大限流年深度解读';
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

  // ---- 解读门槛弹窗：登录引导 + 密码入口 ----
  // 产品规则（2026-08-03 King 定）：解读需登录（free/pro）或访问密码；未登录无密码只能排盘
  // 契约：resolve(pw) 用密码重试；resolve(null) 用户选择去注册/取消
  window.promptLoginOrPassword = function (msg) {
    return new Promise(function (resolve) {
      var ov = document.createElement('div');
      ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:400;display:flex;align-items:center;justify-content:center;font-family:Noto Serif SC,serif';
      // 仅存在登录弹窗的页面（紫微交互盘/报告页）显示注册入口；八字页无登录体系则退化为纯密码框
      var canAuth = !!(document.getElementById('authModal') || document.getElementById('rpt-auth-overlay') || document.getElementById('btn-show-auth'));
      ov.innerHTML =
        '<div style="background:var(--paper-card,#fff);border:1px solid var(--line,#ddd);padding:22px 24px;width:320px;max-width:90vw;text-align:center;border-radius:4px">' +
          '<h3 style="font-size:14px;color:var(--ink,#222);margin-bottom:8px">\ud83d\udd10 解读需要登录</h3>' +
          '<p style="font-size:11px;color:var(--ink-soft,#888);line-height:1.6;margin-bottom:12px">' + escapeHtml(msg || '登录后即可免费解读，未登录仅能排盘') + '</p>' +
          (canAuth
            ? '<button id="plp-auth-btn" style="width:100%;padding:9px;font-size:13px;border:1px solid var(--vermillion,#c1432f);background:none;color:var(--vermillion,#c1432f);border-radius:2px;cursor:pointer;font-family:inherit;margin-bottom:8px">注册 / 登录</button><div style="font-size:11px;color:var(--ink-faint,#aaa);margin-bottom:6px">或输入访问密码</div>'
            : '<div style="font-size:11px;color:var(--ink-faint,#aaa);margin-bottom:6px">输入访问密码</div>') +
          '<input id="plp-pw-inp" type="password" placeholder="访问密码" style="width:100%;padding:8px;font-size:13px;border:1px solid var(--line-soft,#eee);border-radius:2px;margin-bottom:8px;background:var(--paper,#fff);color:var(--ink,#222);font-family:inherit;box-sizing:border-box">' +
          '<div style="display:flex;gap:8px">' +
            '<button id="plp-ok" style="flex:1;padding:8px;font-size:13px;background:var(--ink,#222);color:var(--paper,#fff);border:none;border-radius:2px;cursor:pointer;font-family:inherit">确定</button>' +
            '<button id="plp-cancel" style="flex:1;padding:8px;font-size:13px;border:1px solid var(--line-soft,#eee);background:none;color:var(--ink-soft,#888);border-radius:2px;cursor:pointer;font-family:inherit">取消</button>' +
          '</div>' +
        '</div>';
      function done(v) { if (ov.parentNode) ov.parentNode.removeChild(ov); resolve(v); }
      ov.addEventListener('click', function (e) { if (e.target === ov) done(null); });
      ov.querySelector('#plp-ok').onclick = function () {
        var v = (ov.querySelector('#plp-pw-inp').value || '').trim();
        if (!v) { ov.querySelector('#plp-pw-inp').focus(); return; }
        done(v);
      };
      if (canAuth) ov.querySelector('#plp-auth-btn').onclick = function () {
        done(null);
        if (typeof showRptAuth === 'function') { showRptAuth('login'); }
        else if (window._tierOpenAuth) { window._tierOpenAuth(); }
      };
      ov.querySelector('#plp-cancel').onclick = function () { done(null); };
      document.body.appendChild(ov);
      var inp = ov.querySelector('#plp-pw-inp');
      if (inp) setTimeout(function () { inp.focus(); }, 50);
    });
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
