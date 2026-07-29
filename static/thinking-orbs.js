// thinking-orbs vanilla JS 移植
// 来源: https://github.com/Jakubantalik/thinking-orbs (MIT)
// 适配 Destiny_agent 的水墨宣纸风 + data-theme 暗色主题

(function() {
  'use strict';

  /**
   * 创建一个 thinking orb 动画实例
   * @param {Object} options
   * @param {string} options.state - 'working' | 'searching' | 'solving' | 'listening'
   * @param {number} options.size - 像素大小，默认 64
   * @param {string} options.theme - 'auto' | 'dark' | 'light'，默认 'auto'
   * @param {HTMLElement} options.container - 父容器，默认 document.body
   */
  window.createThinkingOrb = function(options) {
    options = options || {};
    var state = options.state || 'working';
    var size = options.size || 64;
    var theme = options.theme || 'auto';
    var container = options.container || document.body;

    var canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    canvas.style.display = 'block';
    canvas.setAttribute('role', 'img');
    var labels = {
      working: '分析中…', searching: '搜索中…',
      solving: '推理中…', listening: '听取中…'
    };
    canvas.setAttribute('aria-label', labels[state] || '加载中…');
    container.appendChild(canvas);

    var ctx = canvas.getContext('2d');
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var W = size;
    var cx = W / 2, cy = W / 2;
    var dots = state === 'searching' ? 24 : 18;
    var dotRadius = size > 40 ? 2 : 1.2;
    var animId = null;
    var t = 0;
    var paused = false;
    var reducedMotion = false;
    var speedMultiplier = options.speed || 1;

    // 主题颜色
    function getColors() {
      var isDark = false;
      if (theme === 'dark') isDark = true;
      else if (theme === 'light') isDark = false;
      else {
        var html = document.documentElement;
        isDark = html.getAttribute('data-theme') === 'dark';
      }
      return {
        ink: isDark ? 'rgba(224,216,207,0.8)' : 'rgba(43,40,37,0.8)',
        inkDim: isDark ? 'rgba(224,216,207,0.15)' : 'rgba(43,40,37,0.15)',
        bg: 'transparent'
      };
    }

    // reduced motion
    var motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    reducedMotion = motionQuery.matches;
    motionQuery.addEventListener('change', function(e) {
      reducedMotion = e.matches;
    });

    function drawWorking(c, t, r) {
      var cols = getColors();
      for (var i = 0; i < dots; i++) {
        var angle = (i / dots) * Math.PI * 2 + t * 0.8;
        var orbitR = r * (0.35 + (i % 3) * 0.22);
        var ox = cx + Math.cos(angle) * orbitR;
        var oy = cy + Math.sin(angle * 1.3) * orbitR * 0.7;
        var alpha = 0.2 + 0.6 * (Math.sin(t * 2 + i * 0.5) * 0.5 + 0.5);
        c.beginPath();
        c.arc(ox, oy, dotRadius, 0, Math.PI * 2);
        c.fillStyle = cols.ink.replace('0.8', alpha.toFixed(2));
        c.fill();
      }
    }

    function drawSearching(c, t, r) {
      var cols = getColors();
      // 背景虚线球体
      for (var i = 0; i < dots; i++) {
        var phi = Math.acos(1 - 2 * (i + 0.5) / dots);
        var theta = Math.PI * (1 + Math.sqrt(5)) * i;
        var sx = cx + Math.sin(phi) * Math.cos(theta) * r * 0.35;
        var sy = cy + Math.sin(phi) * Math.sin(theta) * r * 0.35;
        c.beginPath();
        c.arc(sx, sy, dotRadius * 0.6, 0, Math.PI * 2);
        c.fillStyle = cols.inkDim;
        c.fill();
      }
      // 扫描经线（3 条，间隔 120°，速度提高）
      for (var beam = 0; beam < 3; beam++) {
        var scanAngle = (t * 3.0 + beam * Math.PI * 2 / 3) % (Math.PI * 2);
        for (var j = 0; j < 8; j++) {
          var phi2 = Math.acos(1 - 2 * (j + 0.5) / 8);
          var sx2 = cx + Math.sin(phi2) * Math.cos(scanAngle) * r * 0.38;
          var sy2 = cy + Math.sin(phi2) * Math.sin(scanAngle) * r * 0.38;
          c.beginPath();
          c.arc(sx2, sy2, dotRadius * 0.9, 0, Math.PI * 2);
          c.fillStyle = cols.ink;
          c.fill();
        }
      }
    }

    function drawSolving(c, t, r) {
      var cols = getColors();
      // 三段圆弧，交错移动
      for (var band = 0; band < 3; band++) {
        var bandAngle = t * (0.5 + band * 0.3) + band * Math.PI * 2 / 3;
        for (var i = 0; i < dots / 3; i++) {
          var frac = i / (dots / 3);
          var angle = bandAngle + frac * Math.PI * 1.2;
          var ringR = r * (0.3 + band * 0.18);
          var bx = cx + Math.cos(angle) * ringR;
          var by = cy + Math.sin(angle) * ringR;
          var alpha = 0.3 + 0.5 * (1 - Math.abs(frac - 0.5) * 2);
          c.beginPath();
          c.arc(bx, by, dotRadius, 0, Math.PI * 2);
          c.fillStyle = cols.ink.replace('0.8', alpha.toFixed(2));
          c.fill();
        }
      }
    }

    function drawListening(c, t, r) {
      var cols = getColors();
      // 波形穿过环
      for (var ring = 0; ring < 3; ring++) {
        var ringR = r * (0.25 + ring * 0.18);
        var waveOffset = t * 0.6 + ring * 0.8;
        for (var i = 0; i < dots / 3; i++) {
          var frac = i / (dots / 3);
          var angle = frac * Math.PI * 2;
          var amp = 0.2 + 0.5 * Math.abs(Math.sin(angle * 3 + waveOffset));
          var actualR = ringR * (1 - amp * 0.4);
          var lx = cx + Math.cos(angle) * actualR;
          var ly = cy + Math.sin(angle) * actualR;
          c.beginPath();
          c.arc(lx, ly, dotRadius, 0, Math.PI * 2);
          c.fillStyle = cols.ink.replace('0.8', (0.2 + amp * 0.6).toFixed(2));
          c.fill();
        }
      }
    }

    var drawFns = {
      working: drawWorking,
      searching: drawSearching,
      solving: drawSolving,
      listening: drawListening
    };

    function frame(ts) {
      if (!paused) {
        t += reducedMotion ? 0 : 0.035 * speedMultiplier;
      }
      drawFrame(t);
      animId = requestAnimationFrame(frame);
    }

    function drawFrame(time) {
      var r = W * 0.42;
      ctx.clearRect(0, 0, W, W);
      var fn = drawFns[state] || drawWorking;
      fn(ctx, time, r);
    }

    canvas.start = function() {
      paused = false;
      drawFrame(0);  // 立即画一帧，避免空白
      if (!animId) animId = requestAnimationFrame(frame);
    };

    canvas.stop = function() {
      paused = true;
      if (animId) { cancelAnimationFrame(animId); animId = null; }
    };

    canvas.changeState = function(newState) {
      if (drawFns[newState]) state = newState;
      canvas.setAttribute('aria-label', labels[state] || '加载中…');
    };

    canvas.start();

    return canvas;
  };
})();
