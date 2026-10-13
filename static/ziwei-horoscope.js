// ziwei-horoscope.js — 流年钻取共享层（ziwei.html / ziwei-report.html 双页同构抽取，2026-09-09）
// 干支一律引擎注入（/horoscope 响应 year_grid / yearly_gan / yearly_zhi / today_day_zhi），禁前端自算。
// 依赖页面全局（跨 <script> 词法绑定，调用期已初始化）：plateData / horoscopeData / horoGridTy / scope / toggleScope。
// 各页通过 <script src="/static/ziwei-horoscope.js?v={{ static_ver }}"> 引入，本文件不得引用页面专属 DOM。

function $horo(id){ return document.getElementById(id); }

async function fetchHoroscope(year){
  const ss = $horo('scope-status');
  if(ss && ss.classList.contains('show')){
    const ld = document.createElement('span');
    ld.id = 'horo-loading';
    ld.textContent = '流曜加载中...';
    ld.style.cssText = 'font-size:10px;opacity:.65;margin:0 6px;animation:blink 1s infinite';
    ss.appendChild(ld);
  }
  try{
    const inp = (typeof plateData !== 'undefined' && plateData && plateData.input) || {};
    const birthDt = inp.birth_datetime || '';
    const parts = birthDt.match(/(\d{4})-(\d{2})-(\d{2})\s(\d{1,2}):(\d{2})/);
    if(!parts){ $horo('horo-loading')?.remove(); return; }
    // grid_start = 当前输入年所在 12 年窗口，保证 year_grid 与展示窗一致
    const ty0 = parseInt($horo('horo-year')?.value) || new Date().getFullYear();
    const body = {
      year: parseInt(parts[1]), month: parseInt(parts[2]), day: parseInt(parts[3]),
      hour: parseInt(parts[4]), gender: inp.gender || '男',
      target_year: year, is_lunar: inp.is_lunar || false,
      grid_start: ty0 - (ty0 % 12)
    };
    const r = await fetch('/api/ziwei/horoscope', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    if(r.ok){ horoscopeData = await r.json(); horoGridTy = ty0; }
  }catch(e){ horoscopeData = null; }
  $horo('horo-loading')?.remove();
}

async function renderFlowYears(){
  const ty = parseInt($horo('horo-year')?.value) || new Date().getFullYear();
  // 年/月干支一律消费引擎注入值（铁律禁前端自算）；无盘数据先出年份壳，注入到达后回填
  if(plateData && plateData.input && (!horoscopeData || horoGridTy !== ty)){
    await fetchHoroscope(ty);
  }
  const gmap = {};
  ((horoscopeData && horoscopeData.year_grid) || []).forEach(g => { gmap[g.year] = g; });
  const yg = $horo('drill-year-grid');
  if(!yg) return;
  yg.innerHTML = '';
  for(let i=0; i<12; i++){
    const y = ty - (ty % 12) + i;
    const hit = gmap[y];
    const gz = hit ? hit.gz : '—';
    const br = hit ? hit.zhi : '';
    const div = document.createElement('div');
    div.className = 'drill-cell';
    if(y === ty) div.classList.add('active');
    div.innerHTML = '<div class="dc-gz">'+gz+'</div><div class="dc-sub">'+y+'年</div>';
    div.onclick = () => toggleScope('yearly', { year: y, gz, br });
    yg.appendChild(div);
  }
  const hi = horoscopeData;
  // 流年支索引/流月干：引擎注入（yearly_zhi/yearly_gan），缺失降级为无支标签
  const yearIdx = (hi && hi.yearly_zhi) ? ZHI_ARR.indexOf(hi.yearly_zhi) : -1;
  const dj = (hi && hi.monthly_palace_index >= 0 && hi.monthly_palace_index < 12)
    ? hi.monthly_palace_index
    : yearIdx;
  const mg = $horo('drill-month-grid');
  if(!mg) return;
  mg.innerHTML = '';
  const ygan = (hi && hi.yearly_gan) ? hi.yearly_gan : '';
  for(let m=1; m<=12; m++){
    const div = document.createElement('div');
    div.className = 'drill-cell';
    if(dj >= 0){
      const idx = (dj + m - 1) % 12;
      const br = ZHI_ARR[idx];
      const mgz = ygan ? (ygan + br) : br;
      div.innerHTML = '<div class="dc-gz">'+m+'月 '+br+'</div><div class="dc-sub">'+br+'宫</div>';
      div.onclick = () => toggleScope('monthly', { month: m, br, gz: mgz });
    } else {
      div.innerHTML = '<div class="dc-gz">'+m+'月</div><div class="dc-sub">—</div>';
      div.onclick = () => toggleScope('monthly', { month: m, br: '', gz: '' });
    }
    mg.appendChild(div);
  }
  if(scope && !scope.yearly){ const e=$horo('fpv-year'); if(e) e.textContent='—'; }
  if(scope && !scope.monthly){ const e=$horo('fpv-month'); if(e) e.textContent='—'; }
}
