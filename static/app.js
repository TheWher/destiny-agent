// 八字排盘 & 紫微斗数 — 前端交互逻辑
// 提取自 templates/index.html

// ========== DOM 引用 ==========
const $ = id => document.getElementById(id);
const elYear=$('year'),elMonth=$('month'),elDay=$('day'),elHour=$('hour'),elMinute=$('minute');
const elLocation=$('location'),elLongitude=$('longitude'),elUseTrueSolar=$('use-true-solar');
const elLngLat=$('lnglat'),elGeocodeStatus=$('geocode-status'),elSuggestions=$('city-suggestions');
const elBtnGeocode=$('btn-geocode'),elBtnPaipan=$('btn-paipan'),elBtnAnalyze=$('btn-analyze'),elBtnPdf=$('btn-pdf');
const elLoading=$('loading'),elLoadingText=$('loading-text'),elErrorBox=$('error-box');
const elResultSection=$('result-section'),elAnalysisSection=$('analysis-section');
const elAnalysisContent=$('analysis-content'),elAnalysisChat=$('analysis-chat');
const elChatInput=$('chat-input'),elBtnChatSend=$('btn-chat-send'),elBtnAnalysisPdf=$('btn-analysis-pdf');
const elPwOverlay=$('pw-overlay'),elPwInput=$('pw-input'),elPwError=$('pw-error'),elBtnPwConfirm=$('btn-pw-confirm'),elBtnPwCancel=$('btn-pw-cancel');
// ---- 紫微斗数 ----
const elZiweiDrawer=$('ziwei-drawer'),elZiweiOverlay=$('ziwei-drawer-overlay');
const elZiweiDrawerBody=$('ziwei-drawer-body'),elZiweiGrid=$('ziwei-grid');
const elZiweiMutagenLine=$('ziwei-mutagen-line'),elZiweiChartSection=$('ziwei-chart-section');
const elZiweiAnalysisSection=$('ziwei-analysis-section'),elZiweiAnalysisContent=$('ziwei-analysis-content');
const elZiweiLoading=$('ziwei-loading'),elBtnZiweiAnalyze=$('btn-ziwei-analyze');
const elBtnZiweiSwitch=$('btn-ziwei-switch'),elZiweiDrawerFooter=$('ziwei-drawer-footer');

let plateData=null, analysisText=null, analysisInProgress=false, conversationMessages=null, conversationId=null;
// ---- 紫微斗数状态 ----
let ziweiPlateData=null, ziweiAnalysisText=null, ziweiAnalysisInProgress=false;

// ========== 操作栏三态切换 ==========
const elSticky1=$('sticky-state-1'),elSticky2=$('sticky-state-2'),elSticky3=$('sticky-state-3');
const elReviewSection=$('review-section');
function showReviewStep(plate) {
    elSticky1.classList.add('hidden'); elSticky2.classList.remove('hidden'); elSticky3.classList.add('hidden');
    // 填充确认卡片
    const sizhu = plate.pillars || {};
    const gz = [sizhu.year?.gz||'?', sizhu.month?.gz||'?', sizhu.day?.gz||'?', sizhu.hour?.gz||'?'].join(' ');
    $('review-sizhu').textContent = gz;
    const input = plate.input || {};
    const qy = plate.qiyun || {};
    let h = `<div class="review-item"><span class="review-label">日主</span><span class="review-value">${plate.ri_zhu||'?'}</span></div>`;
    h += `<div class="review-item"><span class="review-label">起运</span><span class="review-value">${qy.age||'?'}岁（${qy.direction||'?'}行）</span></div>`;
    h += `<div class="review-item"><span class="review-label">出生日期</span><span class="review-value">${input.birth_datetime||'?'}</span></div>`;
    h += `<div class="review-item"><span class="review-label">地点</span><span class="review-value">${input.location||'?'}</span></div>`;
    h += `<div class="review-item"><span class="review-label">性别</span><span class="review-value">${input.gender||'?'}</span></div>`;
    h += `<div class="review-item"><span class="review-warn">⚠️ 时辰不准全盘皆错——请确认出生时间</span></div>`;
    $('review-grid').innerHTML = h;
    elReviewSection.classList.remove('hidden');
    elReviewSection.scrollIntoView({behavior:'smooth',block:'center'});
}
function showAnalyzingStep() {
    elSticky1.classList.add('hidden'); elSticky2.classList.add('hidden'); elSticky3.classList.remove('hidden');
    elReviewSection.classList.add('hidden');
}
function showDefaultStep() {
    elSticky1.classList.remove('hidden'); elSticky2.classList.add('hidden'); elSticky3.classList.add('hidden');
}
const CONV_KEY='bazi_conversation', CONV_ID_KEY='bazi_conversation_id';
function saveConversation(){ if(conversationMessages){ try { localStorage.setItem(CONV_KEY, JSON.stringify(conversationMessages)); }catch(e){} } if(conversationId){ try { localStorage.setItem(CONV_ID_KEY, conversationId); }catch(e){} } }
function loadConversation(){ try { const m=JSON.parse(localStorage.getItem(CONV_KEY)); if(m&&Array.isArray(m)){ conversationMessages=m; conversationId=localStorage.getItem(CONV_ID_KEY)||null; return true; } }catch(e){} return false; }
function clearConversation(){ conversationMessages=null; conversationId=null; localStorage.removeItem(CONV_KEY); localStorage.removeItem(CONV_ID_KEY); }
// ========== 夜晚模式切换 ==========
function toggleTheme(){const h=document.documentElement;const c=h.getAttribute('data-theme')==='dark'?'light':'dark';h.setAttribute('data-theme',c);localStorage.setItem('bazi_theme',c);updateThemeIcon(c);}
function updateThemeIcon(t){const b=document.getElementById('btn-theme');if(b)b.textContent=t==='dark'?'☀️':'🌙';}
(function(){const t=document.documentElement.getAttribute('data-theme');updateThemeIcon(t||'light');})();
let _pwResolve=null; // Promise resolver for password prompt
let _analysisAbortController=null; // AbortController for cancelling in-flight analysis
let _analysisStartTime=0; // timestamp when analysis started (for timeout detection)
let _stageCarouselTimer=null; // interval timer for lightweight stage carousel
let _feedbackFile=''; // current analysis feedback filename for verification
let _verifyLabels={}; // {predictionIndex: "correct"|"wrong"|"partially_correct"}

// ========== 已知事件管理 ==========
let _knownEvents = []; // [{year, desc}, ...]
const MAX_EVENTS = 3;

function renderEventRows() {
    const list = document.getElementById('known-events-list');
    if (!list) return;
    list.innerHTML = _knownEvents.map((evt, i) =>
        `<div class="event-row">
            <input type="number" class="event-year" placeholder="年份" min="1900" max="2026"
                   value="${evt.year||''}" onchange="updateEvent(${i},'year',this.value)">
            <input type="text" class="event-desc" placeholder="如：考上大学、结婚、创业" maxlength="50"
                   value="${evt.desc||''}" onchange="updateEvent(${i},'desc',this.value)">
            <button class="btn-remove-event" onclick="removeEvent(${i})" title="删除">✕</button>
        </div>`
    ).join('');
    const addBtn = document.getElementById('btn-add-event');
    if (addBtn) addBtn.style.display = _knownEvents.length < MAX_EVENTS ? '' : 'none';
    updateAnalyzeBtn();
    saveForm();
}

function addEvent() {
    if (_knownEvents.length >= MAX_EVENTS) return;
    _knownEvents.push({year:'',desc:''});
    if (_knownEvents.length === 1 && !document.getElementById('known-events-body').classList.contains('hidden')) {
        // already open, just render
    }
    renderEventRows();
}

function removeEvent(i) {
    _knownEvents.splice(i, 1);
    renderEventRows();
}

function updateEvent(i, field, value) {
    if (field === 'year') _knownEvents[i].year = parseInt(value) || '';
    else _knownEvents[i].desc = value;
    saveForm();
}

function getValidEvents() {
    return _knownEvents.filter(e => e.year && String(e.year).length === 4 && e.desc && e.desc.trim());
}

function updateAnalyzeBtn() {
    const btn = document.getElementById('btn-analyze');
    if (!btn) return;
    const hasEvents = getValidEvents().length > 0;
    btn.textContent = hasEvents ? '🔍 验证时辰' : '🧠 深度分析';
}

// Toggle events section
document.addEventListener('DOMContentLoaded', () => {
    const toggleBtn = document.getElementById('btn-toggle-events');
    const body = document.getElementById('known-events-body');
    const arrow = toggleBtn ? toggleBtn.querySelector('.toggle-arrow') : null;
    if (toggleBtn && body && arrow) {
        toggleBtn.addEventListener('click', () => {
            body.classList.toggle('hidden');
            arrow.classList.toggle('open');
            if (!body.classList.contains('hidden') && _knownEvents.length === 0) {
                addEvent(); // default one empty row
            }
        });
    }
    document.getElementById('btn-add-event').addEventListener('click', addEvent);
    updateAnalyzeBtn();
});

// ========== 词条解释库（42术语白话版） ==========
const GLOSSARY = {
'日主':'你本人。八字日柱的天干，整个命盘以它为中心','月令':'出生月份的地支，能量最大，格局的来源。\"八字用神，专求月令\"——《子平真诠》',
'四柱':'年、月、日、时四组干支的合称，每组=天干+地支','调候':'调节寒暖燥湿。夏天出生需要水降温，冬天出生需要火暖身——《穷通宝鉴》的核心方法',
'格局':'从月令出发，判断命局的\"骨架\"是什么类型（正官格、七杀格等），决定了人生大方向',
'旺衰':'日主的力量强弱。旺≠好，弱≠差，关键是看和格局是否搭配',
'用神':'对命局最有益的五行，是整个格局的\"主心骨\"','喜神':'辅助用神的五行，让格局更完美。用神是主力，喜神是副手',
'忌神':'破坏格局的五行，是命局中的负面力量','闲神':'中立的五行，平时不参与斗争，但大运流年来了会\"站队\"——《滴天髓》专辟\"闲神\"章',
'病药':'八字的核心矛盾（病）和解决方案（药）。\"有病方为贵，无伤不是奇\"——《神峰通考》',
'透出':'地支藏的五行在天干上露了头，力量展现出来了。\"地支所藏之干，透出干头，则显其用矣\"——《子平真诠》',
'虚透':'天干上有这个十神但地支没有根——有心无力，有想法没执行力',
'藏而不透':'地支里有但天干上看不到——能力潜伏着，需要大运流年\"叫醒\"它',
'得根':'天干上的十神在地支有老家（本气根），实力扎实','得气':'有根但不稳，比虚透好但不如得根——\"有靠山但不牢\"',
'十神':'以日主为中心定义的五种人际关系：比劫（兄弟姐妹）、食伤（才华子女）、财星（财富配偶）、官杀（事业丈夫）、印星（学业母亲）',
'正官':'正当的约束和名誉。主正职、公务员、规则意识强','七杀':'偏门的权力和压力。主军警、创业、高管、竞争——\"有制为偏官，无制为七杀\"',
'正财':'稳定收入、正当财富、正缘婚姻。工资、实业经营','偏财':'意外之财、投资、副业。来得快去得也快',
'正印':'正当的学识和庇护。主学历、母亲、稳定工作','偏印':'偏门的学问和技术。主冷门专业、玄学、继母',
'食神':'温和的才华和福气。主艺术、美食、享受生活','伤官':'激进的才华和叛逆。主创意、自由职业、挑战权威',
'比肩':'同性的伙伴，合作者。讲义气但可能竞争','劫财':'异性的伙伴，竞争者。主破财、兄弟争产',
'身强':'日主力量充足，能承担财官压力','身弱':'日主力量不足，需要印星和比劫帮忙',
'大运':'每十年一换的运势大方向。起运年龄由出生日到下一个节气的天数决定',
'流年':'每一年的具体运势。大运是季节，流年是天气','刑冲合害':'地支之间的互动关系：冲=冲突变动，合=合作绑定，刑=慢性纠纷，害=暗中破坏',
'拱':'用两个明见的地支\"拱\"出一个看不到的虚神——申辰拱子水，寅戌拱午火。虚神为喜用则有暗中的贵人机缘',
'夹':'天干相同的相邻两柱，中间夹出一个虚缺的地支——子寅夹丑。\"见不见之形，无时不有\"',
'暗合':'两地支藏干之间偷偷相合——子巳暗合（癸戊合）。主暗中助力或隐秘情感纠葛',
'墓库':'辰戌丑未四个地支。旺的时候是仓库（可取用），衰的时候是牢笼（能量锁死）',
'开库':'冲开墓库让能量释放——冲开财库可能发财，冲开官库可能升职',
'星宫同参':'断事要同时看\"星\"（十神=什么人什么事）和\"宫\"（四柱位置=什么阶段什么领域）。只看十神不看宫位等于只认演员不看舞台',
'空亡':'天干配地支多出的两个空位——落空的地支力量减弱。\"逢冲则实，逢合则实\"——《三命通会》',
'伏吟':'大运流年干支和原局某柱一模一样——好事坏事都加倍','反吟':'大运流年干支和原局某柱天克地冲——猛烈变动',
'纳音':'每组干支对应的五行音律属性，如\"乙酉\"纳音为\"泉中水\"',
'胎元命宫身宫':'胎元=受胎月份，命宫=安命之宫，身宫=安身之宫——三个辅助参考点',
'真太阳时':'根据出生地经度校正后的真实太阳时间——东莞(113.75°E)比北京时间晚约25分钟，时辰临近边界时特别重要'
};

// ========== 命例历史管理 ==========
const HISTORY_KEY = 'bazi_history';
function loadHistory(){ try{ return JSON.parse(localStorage.getItem(HISTORY_KEY)||'[]'); }catch(e){ return []; } }
function saveHistory(list){ localStorage.setItem(HISTORY_KEY, JSON.stringify(list)); }

async function askName(defVal, title){
  return new Promise(resolve => {
    const ov = document.createElement('div');
    ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;display:flex;align-items:center;justify-content:center;font-family:Noto Serif SC,serif';
    ov.innerHTML = '<div style="background:#faf6ec;border:1px solid #c4bdb0;padding:20px;width:340px;text-align:center;border-radius:4px"><p style="font-size:13px;color:#2b2825;margin-bottom:10px">'+title+'</p><input id="ask-name-input" value="'+defVal+'" style="width:90%;padding:8px;font-size:.9em;border:1px solid #c4bdb0;border-radius:2px;margin-bottom:10px;background:#f5f1e8;color:#2b2825;font-family:inherit"><div style="display:flex;gap:8px"><button id="ani-cancel" style="flex:1;padding:6px;border:1px solid #c4bdb0;background:#f5f1e8;color:#2b2825;cursor:pointer;border-radius:2px;font-family:inherit">取消</button><button id="ani-ok" style="flex:1;padding:6px;background:#2b2825;color:#f5f1e8;border:none;cursor:pointer;border-radius:2px;font-family:inherit">确定</button></div></div>';
    document.body.appendChild(ov);
    const inp = ov.querySelector('#ask-name-input'); inp.focus(); inp.select();
    ov.querySelector('#ani-ok').onclick = () => { ov.remove(); resolve(inp.value); };
    ov.querySelector('#ani-cancel').onclick = () => { ov.remove(); resolve(null); };
    inp.onkeydown = e => { if(e.key==='Enter') ov.querySelector('#ani-ok').click(); };
  });
}
function addToHistory(plate, analysis){
    const h = loadHistory();
    const input = plate.input || {};
    const autoLabel = `${input.gender||'?'}·${plate.ri_zhu||'?'}日主·${input.birth_datetime||'?'}`;
    const key = autoLabel;
    const existing = h.findIndex(e => e.label === key || e._autoLabel === key);
    // 已有分析条目则保留旧名字，仅更新数据
    const oldName = existing >= 0 ? h[existing].name : '';
    const entry = {id:Date.now(), name: oldName, _autoLabel: key, gender:input.gender, birth:input.birth_datetime, rizhu:plate.ri_zhu, sizhu:plate.sizhu, plate, analysis, conversationMessages: conversationMessages ? conversationMessages.filter(m=>m.role!=='system') : undefined, time:new Date().toLocaleString()};
    if(existing >= 0){ h[existing] = entry; } else { h.unshift(entry); }
    if(h.length > 20) h.length = 20;
    saveHistory(h); renderHistory();
    // 新命例弹出命名提示
    if(!oldName){
        setTimeout(async ()=>{ const name = await askName(autoLabel,'为此命例起个名字'); if(name){ entry.name = name.trim(); saveHistory(h); renderHistory(); } }, 300);
    }
}
function deleteHistory(id){ saveHistory(loadHistory().filter(e=>e.id!==id)); renderHistory(); }
function renameHistory(id){
    const h = loadHistory(); const e = h.find(e=>e.id===id); if(!e) return;
    askName(e.name||e._autoLabel||'命例','重命名').then(name => { if(name){ e.name = name.trim(); saveHistory(h); renderHistory(); } });
}
function restoreHistory(id){
    const e = loadHistory().find(e=>e.id===id); if(!e) return;
    plateData = e.plate; analysisText = e.analysis;
    if(e.analysis) {
        if (e.conversationMessages && Array.isArray(e.conversationMessages)) {
            conversationMessages = [{role:'system',content:''}, ...e.conversationMessages]; saveConversation();
        } else {
            conversationMessages = [{role:'system',content:''},{role:'user',content:''},{role:'assistant',content:e.analysis}];saveConversation();
        }
    }
    elResultSection.classList.remove('hidden'); renderResult(e.plate);
    if(e.analysis){ elAnalysisSection.classList.remove('hidden'); elAnalysisContent.innerHTML=formatMarkdown(e.analysis); injectGlossary(elAnalysisContent); elAnalysisChat.classList.remove('hidden'); }
    else elAnalysisSection.classList.add('hidden');
    elBtnAnalyze.disabled = false; elBtnPdf.disabled = false; elBtnZiweiSwitch.disabled = false;
    $('app-main').scrollIntoView({behavior:'smooth',block:'start'});
}

function renderHistory(){
    const el = $('history-list'); if(!el) return;
    const h = loadHistory();
    $('history-count').textContent = h.length;
    el.innerHTML = h.length ? h.map(e=>{
        const displayName = e.name || e._autoLabel || e.label || '未知命例';
        return `<div class="history-item" onclick="restoreHistory(${e.id})">
            <span class="history-label">${displayName}</span>
            <span class="history-time">${e.time}</span>
            <button class="history-rename" onclick="event.stopPropagation();renameHistory(${e.id})" title="重命名">✎</button>
            <button class="history-del" onclick="event.stopPropagation();deleteHistory(${e.id})" title="删除">×</button>
        </div>`;
    }).join('') : '<div class="history-empty">暂无历史命例，排盘分析后自动保存</div>';
}

// ========== 快捷输入 ==========
$('quick-input').addEventListener('input', function(){
    const v = this.value.replace(/\D/g,'');
    if(v.length>=8){
        elYear.value=v.substring(0,4);elMonth.value=v.substring(4,6);elDay.value=v.substring(6,8);
        elHour.value=v.length>=10?v.substring(8,10):'0';elMinute.value=v.length>=12?v.substring(10,12):'0';
    }
});
$('quick-input').addEventListener('keydown', function(e){ if(e.key==='Enter'){ elBtnPaipan.click(); } });

// ========== 自动填充当前时间 ==========
function autoFillNow() {
    const n = new Date();
    if (!elYear.value) elYear.value = n.getFullYear();
    if (!elMonth.value) elMonth.value = n.getMonth() + 1;
    if (!elDay.value) elDay.value = n.getDate();
    if (!elHour.value) elHour.value = n.getHours();
    if (!elMinute.value) elMinute.value = n.getMinutes();
}

// ========== 密码管理（sessionStorage，关浏览器即失效） ==========
function getPassword() {
    return sessionStorage.getItem('bazi_pw') || '';
}
function setPassword(pw) {
    sessionStorage.setItem('bazi_pw', pw);
}
function clearPassword() {
    sessionStorage.removeItem('bazi_pw');
}

// 返回 Promise，resolve=密码字符串，用户取消时 resolve=null
function promptPassword(reason = '') {
    return new Promise(resolve => {
        // 如果已有缓存密码，直接返回
        const cached = getPassword();
        if (cached) { resolve(cached); return; }

        if (elPwError) elPwError.textContent = reason || '';
        if (elPwInput) elPwInput.value = '';
        elPwOverlay.classList.remove('hidden');
        elPwInput.focus();
        _pwResolve = resolve;
    });
}

function confirmPassword() {
    const pw = elPwInput.value.trim();
    if (!pw) { elPwError.textContent = '请输入密码'; return; }
    setPassword(pw);
    elPwOverlay.classList.add('hidden');
    if (_pwResolve) { _pwResolve(pw); _pwResolve = null; }
}

function cancelPassword() {
    elPwOverlay.classList.add('hidden');
    if (_pwResolve) { _pwResolve(null); _pwResolve = null; }
}

if (elBtnPwConfirm) elBtnPwConfirm.addEventListener('click', confirmPassword);
if (elBtnPwCancel) elBtnPwCancel.addEventListener('click', cancelPassword);
if (elPwInput) elPwInput.addEventListener('keydown', e => { if (e.key === 'Enter') confirmPassword(); if (e.key === 'Escape') cancelPassword(); });

// ========== 分析待处理状态（切标签页/关页面后恢复） ==========
function savePendingAnalysis() {
    if (!plateData) return;
    // 保留已有的 retry 计数（如果有）
    const existing = loadPendingAnalysis();
    localStorage.setItem('bazi_analysis_pending', JSON.stringify({
        plate: plateData,
        retries: existing ? existing.retries : 0,
        startedAt: existing ? existing.startedAt : Date.now(),
        requestId: existing ? existing.requestId : (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36)),
        conversationId: existing ? existing.conversationId : conversationId
    }));
}
function loadPendingAnalysis() {
    try {
        const d = JSON.parse(localStorage.getItem('bazi_analysis_pending'));
        if (!d || !d.plate) return null;
        // 30 分钟过期
        if (Date.now() - d.startedAt > 30 * 60 * 1000) {
            localStorage.removeItem('bazi_analysis_pending');
            return null;
        }
        // 恢复 conversationId
        if (d.conversationId && !conversationId) conversationId = d.conversationId;
        return d;
    } catch(e) { return null; }
}
function clearPendingAnalysis() {
    localStorage.removeItem('bazi_analysis_pending');
}

// ========== localStorage 持久化 ==========
function saveForm() {
    const data = {year:elYear.value,month:elMonth.value,day:elDay.value,hour:elHour.value,minute:elMinute.value,location:elLocation.value,longitude:elLongitude.value,gender:document.querySelector('input[name="gender"]:checked').value,calendar:document.querySelector('input[name="calendar"]:checked').value,useTrueSolar:elUseTrueSolar.checked,knownEvents:_knownEvents};
    localStorage.setItem('bazi_form', JSON.stringify(data));
}
function loadForm() {
    try {
        const d = JSON.parse(localStorage.getItem('bazi_form'));
        if (d) { elYear.value=d.year;elMonth.value=d.month;elDay.value=d.day;elHour.value=d.hour;elMinute.value=d.minute;elLocation.value=d.location||'';elLongitude.value=d.longitude||'120'; document.querySelector('input[name="gender"][value="'+(d.gender||'男')+'"]').checked=true; document.querySelector('input[name="calendar"][value="'+(d.calendar||'solar')+'"]').checked=true; elUseTrueSolar.checked=d.useTrueSolar!==false; if(d.knownEvents&&Array.isArray(d.knownEvents)){_knownEvents=d.knownEvents;renderEventRows();} }
    } catch(e) {}
}
[elYear,elMonth,elDay,elHour,elMinute,elLocation,elLongitude].forEach(el => el.addEventListener('change', saveForm));
// 时辰边界提醒
[elHour,elMinute].forEach(el => el.addEventListener('change', checkShichenBoundary));
function checkShichenBoundary() {
    const h = parseInt(elHour.value), m = parseInt(elMinute.value) || 0;
    if (isNaN(h)) return;
    const totalMin = h * 60 + m;
    // 时辰边界（子0, 丑2, 寅4, 卯6, 辰8, 巳10, 午12, 未14, 申16, 酉18, 戌20, 亥22）×60
    const boundaries = [0, 120, 240, 360, 480, 600, 720, 840, 960, 1080, 1200, 1320];
    const near = boundaries.some(b => Math.abs(totalMin - b) <= 15 || Math.abs(totalMin - b - 1440) <= 15);
    const warning = $('shichen-warning');
    if (warning) warning.style.display = near ? '' : 'none';
}
elUseTrueSolar.addEventListener('change', () => { elLngLat.style.display = elUseTrueSolar.checked ? '' : 'none'; saveForm(); });
document.querySelectorAll('input[name="gender"],input[name="calendar"]').forEach(el => el.addEventListener('change', saveForm));

// ========== 输入验证 ==========
function validateInput() {
    const y=parseInt(elYear.value),m=parseInt(elMonth.value),d=parseInt(elDay.value),h=parseInt(elHour.value),mi=parseInt(elMinute.value)||0;
    if (!y||!m||!d||isNaN(h)) return '请完整填写出生日期';
    if (y<1900||y>2100) return '年份范围 1900-2100';
    if (m<1||m>12) return '月份范围 1-12';
    const daysInMonth = new Date(y, m, 0).getDate();
    if (d<1||d>daysInMonth) return `${y}年${m}月只有 ${daysInMonth} 天，输入了 ${d} 日`;
    if (h<0||h>23) return '小时范围 0-23';
    if (mi<0||mi>59) return '分钟范围 0-59';
    // 未来日期提醒
    const inputDate = new Date(y, m-1, d, h, mi);
    if (inputDate > new Date()) return '出生日期不能是未来时间';
    return null;
}

// ========== 逐字段行内验证 ==========
function createFieldError(group) {
    let el = group.querySelector('.field-error-msg');
    if (!el) { el = document.createElement('span'); el.className = 'field-error-msg'; group.appendChild(el); }
    return el;
}
function validateField(fieldId) {
    const el = document.getElementById(fieldId); if (!el) return true;
    const group = el.closest('.form-group'); if (!group) return true;
    const errEl = createFieldError(group);
    const val = el.value.toString().trim(); let err = null;
    const y = parseInt(document.getElementById('year').value) || 0;
    const m = parseInt(document.getElementById('month').value) || 0;

    switch (fieldId) {
        case 'year': { const n = parseInt(val); if (!val) err = '请输入出生年份'; else if (isNaN(n) || n < 1900 || n > 2100) err = '年份范围 1900-2100'; break; }
        case 'month': { const n = parseInt(val); if (!val) err = '请输入月份'; else if (isNaN(n) || n < 1 || n > 12) err = '月份范围 1-12'; break; }
        case 'day': { const n = parseInt(val); if (!val) err = '请输入日期'; else if (y && m) { const dim = new Date(y, m, 0).getDate(); if (n < 1 || n > dim) err = `${y}年${m}月只有${dim}天`; } break; }
        case 'hour': { const n = parseInt(val); if (isNaN(n)) err = '请输入小时'; else if (n < 0 || n > 23) err = '小时范围 0-23'; break; }
        case 'minute': { const n = parseInt(val) || 0; if (n < 0 || n > 59) err = '分钟范围 0-59'; break; }
        case 'location': if (!val) err = '请输入出生地点'; break;
    }
    if (err) { group.classList.add('error'); errEl.textContent = err; return false; }
    else { group.classList.remove('error'); errEl.textContent = ''; return true; }
}
['year','month','day','hour','minute','location'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('blur', () => validateField(id));
});

// ========== 古籍引用 Tooltip 加载 ==========
async function loadClassicalRefs() {
    try {
        const r = await fetch('/api/glossary/references');
        const d = await r.json();
        const refs = d.references || [];
        document.querySelectorAll('label').forEach(label => {
            const text = label.textContent.trim();
            const match = refs.find(ref => text.includes(ref.field) || ref.field.includes(text));
            if (match) {
                const tip = document.createElement('span');
                tip.className = 'form-tooltip';
                tip.innerHTML = `📜<span class="tooltip-text">「${match.quote}」<span class="tooltip-source">——《${match.source}》</span><br>${match.note||''}</span>`;
                label.appendChild(tip);
            }
        });
    } catch(e) { /* 渐进增强，加载失败不影响表单 */ }
}
document.addEventListener('DOMContentLoaded', loadClassicalRefs);

// ========== 真太阳时校正（客户端） ==========
function getSolarAdjustedTime(hour, minute, lng) {
    // 北京时间基准经度 120°E，每差 1° 校正 4 分钟
    const correction = (parseFloat(lng) - 120) * 4; // 分钟
    const totalMinutes = hour * 60 + minute + correction;
    return {
        correction_minutes: Math.round(correction),
        adjusted_hour: totalMinutes / 60,
        adjusted_time: `${Math.floor(((totalMinutes%1440)+1440)%1440/60).toString().padStart(2,'0')}:${Math.round(((totalMinutes%1440)+1440)%1440%60).toString().padStart(2,'0')}`
    };
}

// ========== 城市自动补全 ==========
let suggestTimer=null, suggestIndex=-1;
elLocation.addEventListener('input', () => { clearTimeout(suggestTimer); const q=elLocation.value.trim(); if(q.length<1){elSuggestions.classList.add('hidden');return;} suggestTimer=setTimeout(()=>fetchSuggestions(q),200); });
elLocation.addEventListener('keydown', e => {
    const items=elSuggestions.querySelectorAll('.city-suggestion-item');
    if(e.key==='ArrowDown'){e.preventDefault();suggestIndex=Math.min(suggestIndex+1,items.length-1);updateActive(items);}
    else if(e.key==='ArrowUp'){e.preventDefault();suggestIndex=Math.max(suggestIndex-1,0);updateActive(items);}
    else if(e.key==='Enter'&&suggestIndex>=0&&items.length>0){e.preventDefault();items[suggestIndex].click();}
    else if(e.key==='Escape'){elSuggestions.classList.add('hidden');suggestIndex=-1;}
});
elLocation.addEventListener('blur', () => setTimeout(()=>elSuggestions.classList.add('hidden'),150));
function updateActive(items){items.forEach((item,i)=>item.classList.toggle('active',i===suggestIndex));}
async function fetchSuggestions(q){
    try{const r=await fetch('/api/cities?q='+encodeURIComponent(q));const d=await r.json();if(!d.results||!d.results.length){elSuggestions.classList.add('hidden');return;}suggestIndex=-1;elSuggestions.innerHTML=d.results.map((r,i)=>`<div class="city-suggestion-item" data-lon="${r.lon}" data-name="${r.display_name}"><span class="city-name">${r.display_name}</span><span class="city-info">${r.lon.toFixed(2)}°E</span></div>`).join('');elSuggestions.classList.remove('hidden');elSuggestions.querySelectorAll('.city-suggestion-item').forEach(item=>{item.addEventListener('mousedown',e=>{e.preventDefault();selectCity({lon:parseFloat(item.dataset.lon),display_name:item.dataset.name});});});}catch(e){}}
function selectCity(city){elLocation.value=city.display_name;elLongitude.value=city.lon.toFixed(2);elSuggestions.classList.add('hidden');elGeocodeStatus.innerHTML=`<span class="geocode-ok">✅ 已定位：${city.display_name}</span><span class="geocode-coords">经度 ${city.lon.toFixed(2)}°E</span>`;elGeocodeStatus.classList.remove('hidden');saveForm();}

elBtnGeocode.addEventListener('click', async () => {
    const loc=elLocation.value.trim(); if(!loc) return showError('请输入出生地点');
    elBtnGeocode.disabled=true; hideError();
    try{const r=await fetch('/api/geocode?q='+encodeURIComponent(loc));const d=await r.json();if(d.error){showError(d.error);return;}if(!d.results||!d.results.length){showError('未找到该地点');return;}selectCity({lon:d.results[0].lon,display_name:d.results[0].display_name});if(d.results.length>1){let h=elGeocodeStatus.innerHTML;h+='<div class="geocode-alt">其他候选：';d.results.slice(1).forEach((a,i)=>{h+=`<a href="#" class="alt-link" data-lon="${a.lon}" data-name="${a.display_name}">[${i+1}] ${a.display_name}</a> `;});h+='</div>';elGeocodeStatus.innerHTML=h;elGeocodeStatus.querySelectorAll('.alt-link').forEach(l=>{l.addEventListener('click',e=>{e.preventDefault();selectCity({lon:parseFloat(l.dataset.lon),display_name:l.dataset.name});});});}}catch(e){showError('网络错误');}finally{elBtnGeocode.disabled=false;}
});

// ========== 排盘 ==========
elBtnPaipan.addEventListener('click', async () => {
    const err = validateInput(); if (err) return showError(err);
    hideError(); showLoading('计算中...'); elBtnPaipan.disabled=true; elBtnPdf.disabled=true; elBtnAnalyze.disabled=true;
    const isLunar = document.querySelector('input[name="calendar"]:checked').value === 'lunar';
    const gender = document.querySelector('input[name="gender"]:checked').value;
    let lng = parseFloat(elLongitude.value)||120; let solarCorrection = 0;
    if (elUseTrueSolar.checked) { solarCorrection = (lng-120)*4; }

    try {
        const body = {
            year:parseInt(elYear.value),month:parseInt(elMonth.value),day:parseInt(elDay.value),
            hour:parseInt(elHour.value),minute:parseInt(elMinute.value)||0,
            gender,longitude:lng,location:elLocation.value.trim()||'未知',
            is_lunar:isLunar,solar_correction:solarCorrection
        };
        const r = await fetch('/api/paipan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        const d = await r.json();
        if (d.error) { showError(d.error); return; }
        plateData=d; analysisText=null; clearConversation();
        localStorage.removeItem('bazi_analysis'); localStorage.removeItem('bazi_plate');
        saveForm();
        renderResult(d); elResultSection.classList.remove('hidden');
        elBtnPdf.disabled=false; elBtnAnalyze.disabled=false; elBtnZiweiSwitch.disabled=false;
        elAnalysisSection.classList.add('hidden'); elAnalysisContent.innerHTML=''; elAnalysisChat.classList.add('hidden');
        addToHistory(d, null);
        showReviewStep(d);
        elResultSection.scrollIntoView({behavior:'smooth'});
    } catch(e) { showError('网络错误或服务未启动'); }
    finally { hideLoading(); elBtnPaipan.disabled=false; }
});

// ========== 渲染 ==========
function renderResult(data) {
    const info=data.input,solar=data.solar,lunar=data.lunar,qy=data.qiyun,pillars=data.pillars;
    let solarInfo = solar.applied 
        ? `已启用 · 经度 ${info.longitude}° · 校正 ${solar.correction_minutes>0?'+':''}${solar.correction_minutes}分钟，约 ${solar.adjusted_hour.toFixed(1)} 时` 
        : `未启用真太阳时校正`;
    const solarEl = $('solar-correction');
    if (solarEl) { solarEl.style.display = ''; solarEl.innerHTML = `<span style="color:var(--champagne)">🌏</span> ${solarInfo}`; }
    $('basic-info').innerHTML = `
        <div><span class="info-label">公历</span><span class="info-value">${info.birth_datetime}</span></div>
        <div><span class="info-label">农历</span><span class="info-value">${lunar.year}年${lunar.month}月${lunar.day}日${lunar.is_leap?'（闰月）':''}</span></div>
        <div><span class="info-label">时辰</span><span class="info-value">${data.shichen}</span></div>
        <div><span class="info-label">性别</span><span class="info-value">${info.gender}</span></div>
        <div><span class="info-label">出生地</span><span class="info-value">${info.location}（${info.longitude}°E）</span></div>
        <div><span class="info-label">真太阳时</span><span class="info-value">${solarInfo}</span></div>
        <div><span class="info-label">日主</span><span class="info-value">${data.ri_zhu}（${data.year_type}）</span></div>`;
    const orders=['year','month','day','hour'],colNames=['年柱','月柱','日柱','时柱'];
    const ganRow=['<td class="row-label">干支</td>'],tianRow=['<td class="row-label">天干</td>'],zhiRow=['<td class="row-label">地支</td>'];
    const ssRow=['<td class="row-label">十神</td>'],nyRow=['<td class="row-label">纳音</td>'],csRow=['<td class="row-label">十二长生</td>'],cgRow=['<td class="row-label">藏干</td>'];
    orders.forEach(p=>{const d=pillars[p],c=p==='day'?' class="day-zhu"':'';ganRow.push(`<td${c}>${d.gz}<span class="gz-sub">${d.gan}${d.zhi}</span></td>`);tianRow.push(`<td${c}>${d.gan}</td>`);zhiRow.push(`<td${c}>${d.zhi}</td>`);ssRow.push(`<td${c}>${d.shishen}</td>`);nyRow.push(`<td${c}>${d.nayin}</td>`);csRow.push(`<td${c}>${d.changsheng}</td>`);cgRow.push(`<td${c}>${d.canggan.map(c=>c.gan).join(' · ')}</td>`);});
    $('row-ganzhi').innerHTML=ganRow.join('');$('row-tiangan').innerHTML=tianRow.join('');$('row-dizhi').innerHTML=zhiRow.join('');
    $('row-shishen').innerHTML=ssRow.join('');$('row-nayin').innerHTML=nyRow.join('');$('row-changsheng').innerHTML=csRow.join('');$('row-canggan').innerHTML=cgRow.join('');
    const kong=data.kongwang,kongDesc=orders.filter(p=>kong.pillars[p]).map(p=>colNames[orders.indexOf(p)]+'支'+pillars[p].zhi).join('、')||'无';
    $('qiyun-info').innerHTML=`<div><span class="info-label">起运年龄</span><span class="info-value">${qy.age} 岁（虚岁 ${qy.age_xu}）</span></div><div><span class="info-label">交运年份</span><span class="info-value">约 ${qy.year} 年</span></div><div><span class="info-label">大运方向</span><span class="info-value">${qy.direction}（距节气 ${qy.diff_days} 天）</span></div><div><span class="info-label">空亡</span><span class="info-value">${kong.kong1}${kong.kong2}（${kongDesc}）</span></div><div><span class="info-label">胎元</span><span class="info-value">${data.taiyuan}</span></div><div><span class="info-label">命宫 / 身宫</span><span class="info-value">${data.minggong} / ${data.shengong}</span></div>`;
    $('dayun-tbody').innerHTML=data.dayun.map(d=>`<tr><td>第 ${d.step} 步</td><td class="dayun-gz">${d.gz}</td><td>${d.start_age} - ${d.end_age} 岁</td><td>${d.start_year} - ${d.end_year} 年</td></tr>`).join('');

    // 神煞速览
    const ss = data.shensha || {};
    const shenshaHtml = Object.values(ss).map(s => {
        if (!s.value) return '';
        const inStr = s.in_pillars && s.in_pillars.length>0 ? ` ⭐入${s.in_pillars.join('、')}` : '';
        const srcStr = s.source ? `<span class="info-label" style="font-size:0.7em;color:#bbb;font-weight:400">（${s.source}）</span>` : '';
        return `<div><span class="info-label" title="${s.info}">${s.desc}</span><span class="info-value" title="${s.info}">${s.value}${inStr}</span>${srcStr}</div>`;
    }).filter(Boolean).join('');
    $('shensha-info').innerHTML = shenshaHtml || '<div><span class="info-label">暂未加载</span></div>';

    // 渲染图表
    renderCharts(data);
}

// ========== SVG 图表（服务端生成，零 CDN 依赖） ==========
async function renderCharts(data) {
    const pillars = data.pillars, dayun = data.dayun;

    // 五行分布计算
    const wuxingCount = {'木':0,'火':0,'土':0,'金':0,'水':0};
    const ganWuXing = {'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水'};
    const zhiWuXing = {'子':'水','丑':'土','寅':'木','卯':'木','辰':'土','巳':'火','午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'};
    ['year','month','day','hour'].forEach(p => {
        const d = pillars[p];
        wuxingCount[ganWuXing[d.gan]] = (wuxingCount[ganWuXing[d.gan]]||0) + 1;
        wuxingCount[zhiWuXing[d.zhi]] = (wuxingCount[zhiWuXing[d.zhi]]||0) + 1;
    });

    // 加载服务端 SVG 图表
    const wxDom = document.getElementById('chart-wuxing');
    const csDom = document.getElementById('chart-changsheng');
    try {
        if (wxDom) {
            const r = await fetch('/api/chart/wuxing', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({wuxing:wuxingCount})});
            if (r.ok) wxDom.innerHTML = await r.text();
        }
        if (csDom) {
            const r = await fetch('/api/chart/changsheng', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pillars:data.pillars,ri_zhu:data.ri_zhu})});
            if (r.ok) csDom.innerHTML = await r.text();
        }
        // 大运环形图
        const drDom = document.getElementById('chart-dayun-ring');
        if (drDom) {
            // 计算当前年龄
            const birthYr = parseInt(elYear.value) || 2005;
            const now = new Date();
            let currentAge = now.getFullYear() - birthYr;
            if (now.getMonth() < parseInt(elMonth.value)-1 || (now.getMonth() === parseInt(elMonth.value)-1 && now.getDate() < parseInt(elDay.value))) {
                currentAge -= 1;
            }
            const r = await fetch('/api/chart/dayun-ring', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({dayun:data.dayun,ri_gan:data.ri_zhu,current_age:currentAge})});
            if (r.ok) drDom.innerHTML = await r.text();
        }
    } catch(e) { console.warn('Chart load failed:', e); }
    renderShengkeChart(data);
    document.getElementById('charts-section').classList.remove('hidden');
}

// ========== 干支关系图 SVG ==========
function renderShengkeChart(data){
    const el = document.getElementById('chart-shengke');
    if(!el||!data||!data.pillars) return;

    const V = 960;
    const cx = V/2;
    const tag = (n,a,i) => `<${n} ${Object.entries(a).map(([k,v])=>`${k}="${v}"`).join(' ')}>${i||''}</${n}>`;
    const wxColor = {'甲':'#2e7d32','乙':'#388e3c','丙':'#c62828','丁':'#d32f2f','戊':'#e65100','己':'#ef6c00','庚':'#b8860b','辛':'#c7940a','壬':'#1565c0','癸':'#1976d2',
                      '子':'#1565c0','丑':'#8d6e63','寅':'#2e7d32','卯':'#388e3c','辰':'#a1887f','巳':'#c62828','午':'#d32f2f','未':'#8d6e63','申':'#b8860b','酉':'#c7940a','戌':'#a1887f','亥':'#1976d2'};

    const cols = ['year','month','day','hour'];
    const labels = ['年柱','月柱','日柱','时柱'];
    const gans = cols.map(c=>data.pillars[c]?.gan||'');
    const zhis = cols.map(c=>data.pillars[c]?.zhi||'');
    const colW = 190, startX = cx - colW*1.5;
    const ganY = 170, zhiY = 245, H = 560;

    let parts = [];

    // ===== 顶区：天干相克 =====
    const ganKe = {'甲':'戊庚','乙':'己辛','丙':'庚壬','丁':'辛癸','戊':'壬甲','己':'癸乙','庚':'甲丙','辛':'乙丁','壬':'丙戊','癸':'丁己'};
    const ganRels = [];
    for(let i=0;i<4;i++) for(let j=i+1;j<4;j++){ if((ganKe[gans[i]]||'').includes(gans[j])) ganRels.push({i,j,dist:Math.abs(j-i)}); }
    ganRels.sort((a,b)=>b.dist-a.dist); // 长线在上
    const topRels = ganRels.reduce((acc,r,i)=>{ const y=30+i*44; acc.push({x1:startX+r.i*colW,x2:startX+r.j*colW,y,text:gans[r.i]+'克'+gans[r.j]}); return acc; },[]);
    const topBase = topRels.length>0 ? topRels[topRels.length-1].y+6 : 0;

    topRels.forEach(r=>{
        parts.push(tag('circle',{cx:r.x1,cy:r.y,r:16,fill:'#fff',stroke:'#ccc','stroke-width':1.5}));
        parts.push(tag('text',{x:r.x1,y:r.y,fill:'#333','font-size':'13','font-weight':'bold','text-anchor':'middle','dominant-baseline':'central'},gans[ganRels.find(gr=>startX+gr.i*colW===r.x1)?.i]));
        parts.push(tag('circle',{cx:r.x2,cy:r.y,r:16,fill:'#fff',stroke:'#ccc','stroke-width':1.5}));
        parts.push(tag('text',{x:r.x2,y:r.y,fill:'#333','font-size':'13','font-weight':'bold','text-anchor':'middle','dominant-baseline':'central'},gans[ganRels.find(gr=>startX+gr.j*colW===r.x2)?.j]));
        parts.push(tag('line',{x1:r.x1+16,y1:r.y,x2:r.x2-16,y2:r.y,stroke:'#bbb','stroke-width':1}));
        parts.push(tag('text',{x:(r.x1+r.x2)/2,y:r.y-12,fill:'#e53935','font-size':'10','text-anchor':'middle'},'克'));
    });

    // ===== 中区：四柱主体 =====
    const gkD = {'甲':'申酉','乙':'申酉','丙':'子亥','丁':'子亥','戊':'寅卯','己':'寅卯','庚':'巳午','辛':'巳午','壬':'丑未辰戌','癸':'丑未辰戌'};
    const dkG = {'子':'丙丁','丑':'甲乙','寅':'戊己','卯':'戊己','辰':'壬癸','巳':'庚辛','午':'庚辛','未':'壬癸','申':'甲乙','酉':'甲乙','戌':'丙丁','亥':'丙丁'};

    cols.forEach((_,i)=>{
        const x = startX + i*colW, gan = gans[i], zhi = zhis[i];
        // 标题
        parts.push(tag('text',{x,y:ganY-50,fill:'#aaa','font-size':'12','text-anchor':'middle'},labels[i]));
        // 天干
        parts.push(tag('text',{x,y:ganY,fill:wxColor[gan],'font-size':'26','font-weight':'bold','text-anchor':'middle','dominant-baseline':'central'},gan));
        // 地支
        parts.push(tag('text',{x,y:zhiY,fill:wxColor[zhi],'font-size':'24','font-weight':'bold','text-anchor':'middle','dominant-baseline':'central'},zhi));
        // 盖头/截脚
        const jj = (gkD[gan]||'').includes(zhi);
        const gt = (dkG[zhi]||'').includes(gan);
        if(jj||gt) parts.push(tag('text',{x,y:zhiY+22,fill:'#a1887f','font-size':'10','text-anchor':'middle'},jj?'截脚':'盖头'));
    });

    // ===== 底区：地支合冲刑害 =====
    const liuhe={'子':'丑','丑':'子','寅':'亥','亥':'寅','卯':'戌','戌':'卯','辰':'酉','酉':'辰','巳':'申','申':'巳','午':'未','未':'午'};
    const liuchong={'子':'午','午':'子','丑':'未','未':'丑','寅':'申','申':'寅','卯':'酉','酉':'卯','辰':'戌','戌':'辰','巳':'亥','亥':'巳'};
    const xianghai={'子':'未','未':'子','丑':'午','午':'丑','寅':'巳','巳':'寅','卯':'辰','辰':'卯','申':'亥','亥':'申','酉':'戌','戌':'酉'};
    const sanhe=[{s:['申','子','辰'],n:'水'},{s:['亥','卯','未'],n:'木'},{s:['寅','午','戌'],n:'火'},{s:['巳','酉','丑'],n:'金'}];
    const anhe=[{s:['子','巳'],n:'暗合'},{s:['寅','丑'],n:'暗合'},{s:['卯','申'],n:'暗合'},{s:['午','亥'],n:'暗合'}];
    const zhiRels = [];
    for(let i=0;i<4;i++) for(let j=i+1;j<4;j++){
        const a=zhis[i], b=zhis[j];
        const rel = {i,j,dist:Math.abs(j-i),text:'',color:'#999'};
        if(a===b) rel.text=a+a+'自刑';
        else if(liuhe[a]===b) rel.text=a+b+'六合';
        else if(liuchong[a]===b) rel.text=a+b+'六冲';
        else if(xianghai[a]===b) rel.text=a+b+'相害';
        else { for(const sh of sanhe){ if(sh.s.includes(a)&&sh.s.includes(b)){ rel.text=a+b+'半合'+sh.n+'局'; break; } } }
        if(!rel.text){ for(const ah of anhe){ if(ah.s.includes(a)&&ah.s.includes(b)){ rel.text=a+b+'暗合'; break; } } }
        if(!rel.text) continue; // 无关系则跳过
        zhiRels.push(rel);
    }
    zhiRels.sort((a,b)=>b.dist-a.dist); // 长线在上

    const botBase = 300;
    zhiRels.forEach((r,ri)=>{
        const y = botBase + ri*42;
        const x1 = startX+r.i*colW, x2 = startX+r.j*colW;
        parts.push(tag('circle',{cx:x1,cy:y,r:16,fill:'#fff',stroke:'#ccc','stroke-width':1.5}));
        parts.push(tag('text',{x:x1,y,fill:'#333','font-size':'13','font-weight':'bold','text-anchor':'middle','dominant-baseline':'central'},zhis[r.i]));
        parts.push(tag('circle',{cx:x2,cy:y,r:16,fill:'#fff',stroke:'#ccc','stroke-width':1.5}));
        parts.push(tag('text',{x:x2,y,fill:'#333','font-size':'13','font-weight':'bold','text-anchor':'middle','dominant-baseline':'central'},zhis[r.j]));
        parts.push(tag('line',{x1:x1+16,y1:y,x2:x2-16,y2:y,stroke:'#bbb','stroke-width':1}));
        parts.push(tag('text',{x:(x1+x2)/2,y:y-12,fill:'#888','font-size':'10','text-anchor':'middle'},r.text));
    });

    el.innerHTML = tag('svg',{viewBox:`0 0 ${V} ${H}`,xmlns:'http://www.w3.org/2000/svg',style:'width:100%;display:block;margin:0 auto;'},parts.join(''));
}

// ========== 工具函数 ==========
function showLoading(t, useSkeleton=false){
    if(useSkeleton){
        $('skeleton-loading').classList.remove('hidden');
        $('result-section').classList.add('hidden');
        $('charts-section').classList.add('hidden');
        $('analysis-section').classList.add('hidden');
    }
    elLoadingText.textContent=t;elLoading.classList.remove('hidden');elErrorBox.classList.add('hidden');
}
function hideLoading(){_stopStageCarousel(true);elLoading.classList.add('hidden');$('skeleton-loading').classList.add('hidden');$('progress-bar').style.display='none';}
function showSkeleton(){ $('skeleton-loading').classList.remove('hidden'); }
function hideSkeleton(){ $('skeleton-loading').classList.add('hidden'); }
function showError(m){ toast(m, 'error'); hideLoading(); }
function hideError(){ $('toast-overlay').classList.add('hidden'); elErrorBox.classList.add('hidden'); }

// ========== 分析进度条 ==========
const PROGRESS_PHASES = [
    {id:'verify',label:'验盘'},{id:'tiaohou',label:'调候'},{id:'geju',label:'格局'},
    {id:'wangsan',label:'旺衰'},{id:'bingyao',label:'病药'},{id:'liutong',label:'流通'},
    {id:'shishen',label:'十神'},{id:'chonghe',label:'刑冲'},{id:'dayun',label:'大运'},
    {id:'cross',label:'交叉'},{id:'career',label:'事业'},{id:'marriage',label:'婚姻'},
    {id:'health',label:'健康'},{id:'selfcheck',label:'自检'}
];

function initProgressBar() {
    const stepsEl = $('progress-steps');
    const phaseEl = $('progress-phase');
    let html = '';
    PROGRESS_PHASES.forEach((p, i) => {
        html += `<span class="progress-step" data-step="${i}"><span class="step-num">${i+1}</span><span class="step-label">${p.label}</span></span>`;
    });
    stepsEl.innerHTML = html;
    phaseEl.textContent = '';
    $('progress-fill').style.width = '0%';
}

function updateProgress(phaseIndex) {
    const steps = document.querySelectorAll('.progress-step');
    const phaseEl = $('progress-phase');
    const fillEl = $('progress-fill');
    const pct = Math.round((phaseIndex + 1) / PROGRESS_PHASES.length * 100);
    fillEl.style.width = pct + '%';
    steps.forEach((s, i) => {
        s.classList.remove('active', 'completed');
        if (i < phaseIndex) s.classList.add('completed');
        else if (i === phaseIndex) s.classList.add('active');
    });
    if (phaseIndex < PROGRESS_PHASES.length) {
        phaseEl.textContent = PROGRESS_PHASES[phaseIndex].label + ' 分析中...';
    }
}

const STAGE_CAROUSEL = [
    {id:'tiaohou',label:'调候'},{id:'geju',label:'格局'},{id:'wangsan',label:'旺衰'},
    {id:'bingyao',label:'病药'},{id:'shensha',label:'神煞'},{id:'dayun',label:'大运'},
    {id:'threechannel',label:'三通道'},{id:'zonghe',label:'综合'},{id:'yanpan',label:'验盘'}
];

function _startStageCarousel() {
    if (_stageCarouselTimer) return;
    const stepsEl = $('progress-steps');
    let html = '';
    STAGE_CAROUSEL.forEach((p, i) => {
        html += `<span class="progress-step" data-step="${i}"><span class="step-num">${i+1}</span><span class="step-label">${p.label}</span></span>`;
    });
    stepsEl.innerHTML = html;
    const phaseEl = $('progress-phase');
    phaseEl.textContent = '';
    $('progress-fill').style.width = '0%';
    let idx = 0;
    const total = STAGE_CAROUSEL.length;
    _updateCarouselStep(0);
    _stageCarouselTimer = setInterval(() => {
        idx++;
        if (idx >= total) idx = 0;
        _updateCarouselStep(idx);
    }, 2000);
}
function _updateCarouselStep(phaseIndex) {
    const steps = document.querySelectorAll('.progress-step');
    const phaseEl = $('progress-phase');
    const fillEl = $('progress-fill');
    const pct = Math.round((phaseIndex + 1) / STAGE_CAROUSEL.length * 100);
    fillEl.style.width = pct + '%';
    steps.forEach((s, i) => {
        s.classList.remove('active', 'completed');
        if (i < phaseIndex) s.classList.add('completed');
        else if (i === phaseIndex) s.classList.add('active');
    });
    if (phaseIndex < STAGE_CAROUSEL.length) {
        phaseEl.textContent = STAGE_CAROUSEL[phaseIndex].label + ' 分析中...';
    }
}
function _stopStageCarousel(flashComplete) {
    if (_stageCarouselTimer) { clearInterval(_stageCarouselTimer); _stageCarouselTimer = null; }
    if (flashComplete) {
        const steps = $('progress-steps').querySelectorAll('.progress-step');
        steps.forEach(s => { s.classList.remove('active'); s.classList.add('completed'); });
        $('progress-fill').style.width = '100%';
        const phaseEl = $('progress-phase');
        if (phaseEl) phaseEl.textContent = '分析完成 ✓';
    }
}
function showProgress() {
    initProgressBar();
    $('progress-bar').style.display = '';
    elLoadingText.style.display = 'none';
    elLoading.classList.remove('hidden');
    var s = document.querySelector('#loading .spinner');
    if (s) s.style.display = 'none';
}

// ========== 全局 Toast（屏幕正中，点击确认关闭） ==========
function toast(msg, type='info') {
    const icons = { error: '❌', info: '💡', success: '✅', warn: '⚠️' };
    $('toast-icon').textContent = icons[type] || icons.info;
    $('toast-msg').textContent = msg;
    $('toast-overlay').classList.remove('hidden');
    $('toast-dismiss').focus();
}
$('toast-dismiss').addEventListener('click', () => $('toast-overlay').classList.add('hidden'));
$('toast-overlay').addEventListener('click', e => { if(e.target === $('toast-overlay')) $('toast-overlay').classList.add('hidden'); });
// 密码错误也走 toast
const _origCheckPw = showError;
showError = function(m) {
    if (m && m.includes('密码')) { toast(m, 'warn'); hideLoading(); }
    else { elErrorBox.textContent='❌ '+m; elErrorBox.classList.remove('hidden'); hideLoading(); }
};
function formatMarkdown(text){
    let h=text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    h=h.replace(/^#### (.+)$/gm,'<h5>$1</h5>');h=h.replace(/^### (.+)$/gm,'<h4>$1</h4>');h=h.replace(/^## (.+)$/gm,'<h3>$1</h3>');h=h.replace(/^# (.+)$/gm,'<h2>$1</h2>');
    h=h.replace(/\*\*\*(.+?)\*\*\*/g,'<strong><em>$1</em></strong>');h=h.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');h=h.replace(/\*(.+?)\*/g,'<em>$1</em>');
    h=h.replace(/^- (.+)$/gm,'<li>$1</li>');h=h.replace(/^---+$/gm,'<hr>');
    let blocks=h.split(/\n\n+/);return blocks.map(b=>{b=b.trim();if(!b)return'';if(/^<(h[2-5]|li|hr|table)/.test(b))return b;b=b.replace(/\n/g,'<br>');return'<p>'+b+'</p>';}).join('\n');
}

// 注入词条 tooltip（在 DOM 挂载后调用）
function injectGlossary(container){
    const terms = Object.keys(GLOSSARY).sort((a,b)=>b.length-a.length); // 长词优先
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    const replacements = [];
    while(walker.nextNode()){
        const node = walker.currentNode;
        if(node.parentElement.classList.contains('glossary-term')) continue;
        let text = node.textContent;
        let changed = false;
        for(const term of terms){
            const idx = text.indexOf(term);
            if(idx === -1) continue;
            changed = true;
            const span = document.createElement('span');
            span.className = 'glossary-term';
            span.textContent = term;
            span.title = GLOSSARY[term];
            span.setAttribute('data-tip', GLOSSARY[term]);
            const before = text.substring(0, idx);
            const after = text.substring(idx + term.length);
            const beforeNode = document.createTextNode(before);
            node.parentNode.insertBefore(beforeNode, node);
            node.parentNode.insertBefore(span, node);
            node.textContent = after;
            text = after;
        }
    }
}

// ========== 深度分析（含断线重试、页面恢复） ==========
async function doAnalyze(isRetry = false) {
    if(!plateData) return;
    hideError();

    // 从 pending 状态恢复时，plateData 可能已被设置
    const pending = loadPendingAnalysis();
    if (isRetry && pending) {
        plateData = pending.plate;
        // 渲染命盘（如果还没渲染）
        if (elResultSection.classList.contains('hidden')) {
            renderResult(plateData);
            elResultSection.classList.remove('hidden');
            elBtnPdf.disabled = false; elBtnZiweiSwitch.disabled = false;
        }
    }

    const pendingBefore = loadPendingAnalysis();
    const retryCount = (pendingBefore ? pendingBefore.retries : 0);

    if (retryCount >= 3) {
        showError('已重试 3 次仍未成功，请稍后再试或检查网络连接');
        clearPendingAnalysis();
        return;
    }

    // 指数退避延迟
    if (isRetry && retryCount > 0) {
        const delays = [5000, 15000, 30000]; // 5s, 15s, 30s
        const delay = delays[Math.min(retryCount - 1, delays.length - 1)];
        showLoading(`分析中断，${Math.round(delay/1000)}秒后自动重试（第 ${retryCount} 次）...`);
        await new Promise(r => setTimeout(r, delay));
    }

    // 解读门槛：无缓存密码时弹窗（登录引导 + 密码入口），已输过则直接复用
    let pw = sessionStorage.getItem('bazi_pw') || '';
    if (!pw) {
      pw = await promptLoginOrPassword(isRetry ? '重试需要重新登录或输入访问密码' : '');
      if (pw === null) {
        elBtnAnalyze.disabled = false;
        analysisInProgress = false; showDefaultStep();
        return;
      }
      if (pw) sessionStorage.setItem('bazi_pw', pw);
    }

    showLoading(isRetry ? '正在重新连接 Agent...' : (getValidEvents().length > 0 ? '正在验证时辰...' : '正在验盘——反推过往事件验证时辰（约需 30 秒）...'));
    showProgress();
    _startStageCarousel();
    if (!isRetry) toast(getValidEvents().length > 0 ? '验证已开始\nAgent 正在核查你提供的事件与命盘是否吻合' : '验盘分析已开始\nAgent 正在反推过往事件验证时辰（约需 30 秒）', 'info');
    showSkeleton(); showAnalyzingStep();
    analysisInProgress = true;
    _analysisStartTime = Date.now();
    elBtnAnalyze.disabled = true;
    elAnalysisSection.classList.add('hidden');
    $('liunian-section').classList.add('hidden'); _liunianData = null;

    try {
        // 保存待处理状态（切标签页/关页面后可恢复）
        savePendingAnalysis();

        // 生成对话 ID（整个对话期间不变）
        if (!conversationId) { conversationId = 'conv_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2,8); try { localStorage.setItem(CONV_ID_KEY, conversationId); }catch(e){} }

        // 创建 AbortController（用于超时取消）
        _analysisAbortController = new AbortController();
        // 8 分钟超时
        const timeoutId = setTimeout(() => { if (_analysisAbortController) _analysisAbortController.abort(); }, 8 * 60 * 1000);

        const r = await fetch('/api/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({plate: plateData, password: pw, conversation_id: conversationId, known_events: getValidEvents()}),
            signal: _analysisAbortController.signal
        });
        clearTimeout(timeoutId);
        _analysisAbortController = null;

        const d = await r.json();
        if (!d.success) {
            if (d.need_password) {
                clearPendingAnalysis();
                const p = await promptLoginOrPassword(d.error);
                if (!p) { elBtnAnalyze.disabled = false; analysisInProgress = false; showDefaultStep(); return; }
                sessionStorage.setItem('bazi_pw', p);
                return doAnalyze(true); // 带密码重试
            }
            clearPendingAnalysis();
            if (d.rate_limited) { showUpgradeToast(d.error, d.tier); hideLoading(); elBtnAnalyze.disabled = false; analysisInProgress = false; showDefaultStep(); return; }
            showError(d.error || '分析失败');
            return;
        }

        // 成功：清除待处理状态，保存结果
        clearPendingAnalysis();
        hideSkeleton();
        analysisText = d.analysis;
        _feedbackFile = d.feedback_file || '';
        if (d.messages) { conversationMessages = d.messages; saveConversation(); elAnalysisChat.classList.remove('hidden'); }
        localStorage.setItem('bazi_plate', JSON.stringify(plateData));
        localStorage.setItem('bazi_analysis', analysisText);
        elAnalysisContent.innerHTML = formatMarkdown(analysisText);
        injectGlossary(elAnalysisContent);
        addToHistory(plateData, analysisText);
        elAnalysisSection.classList.remove('hidden');
        elBtnAnalysisPdf.disabled = false;
        // 用神卡片
        if (d.yongshen) {
            renderYongshenCard(d.yongshen);
            try { localStorage.setItem('bazi_yongshen', JSON.stringify(d.yongshen)); } catch(e) {}
        }
        // 加载流年数据
        loadLiunian(plateData);
        $('app-main').scrollIntoView({behavior:'smooth',block:'start'});

        // 提取验盘预测并渲染验证面板
        if (d.messages && d.messages.length >= 3) {
            const asstMsg = d.messages[d.messages.length - 1].content;
            const preds = extractVerificationPredictions(asstMsg);
            if (preds.length > 0) {
                _verifyLabels = {};
                renderVerificationPanel(preds);
            }
        }

        // 如果是缓存命中，显示提示
        if (d.cached) {
            const cacheNote = document.createElement('div');
            cacheNote.className = 'cache-note';
            cacheNote.textContent = '⚡ 命中服务端缓存，瞬间返回（无需重新调用 AI）';
            cacheNote.style.cssText = 'color:#d4a843;font-size:0.8em;margin-bottom:12px;text-align:center';
            elAnalysisContent.insertBefore(cacheNote, elAnalysisContent.firstChild);
        }

        // 粒子庆祝
        setTimeout(() => {
            const rect = elAnalysisSection.getBoundingClientRect();
            particleBurst(rect.left + rect.width/2, rect.top + 100);
        }, 400);

    } catch (e) {
        // AbortError = 主动取消或超时，不清除 pending（可以重试）
        if (e.name === 'AbortError') {
            hideLoading();
            elBtnAnalyze.disabled = false;
            analysisInProgress = false; showDefaultStep();
            _analysisAbortController = null;
            // 自动标记重试
            const p = loadPendingAnalysis();
            if (p && p.retries < 3) {
                p.retries++;
                localStorage.setItem('bazi_analysis_pending', JSON.stringify(p));
                showLoading('连接中断，即将自动重试...');
                setTimeout(() => doAnalyze(true), 2000);
            } else {
                showError('分析请求超时（8分钟），请刷新页面后重试');
                clearPendingAnalysis();
            }
            return;
        }

        // TypeError / NetworkError = 网络中断，可重试
        if (e.name === 'TypeError' || e.message.includes('NetworkError') || e.message.includes('Failed to fetch')) {
            hideLoading();
            elBtnAnalyze.disabled = false;
            analysisInProgress = false; showDefaultStep();
            _analysisAbortController = null;
            const p = loadPendingAnalysis();
            if (p && p.retries < 3) {
                p.retries++;
                localStorage.setItem('bazi_analysis_pending', JSON.stringify(p));
                showLoading('网络中断，即将自动重试...');
                setTimeout(() => doAnalyze(true), 3000);
            } else {
                showError('网络连接失败，请检查网络后刷新页面重试');
                clearPendingAnalysis();
            }
            return;
        }

        clearPendingAnalysis();
        showError('网络错误或分析超时，请重试');
    } finally {
        hideLoading();
        hideSkeleton();
        elBtnAnalyze.disabled = false;
        analysisInProgress = false; showDefaultStep();
        _analysisAbortController = null;
    }
}
elBtnAnalyze.addEventListener('click', () => doAnalyze(false));
// 确认排盘步骤：两个"确认"按钮都触发分析
$('btn-review-confirm')?.addEventListener('click', () => { showAnalyzingStep(); doAnalyze(false); });
$('btn-review-confirm-2')?.addEventListener('click', () => { showAnalyzingStep(); doAnalyze(false); });
// 返回修改：隐藏确认步骤，回到表单
$('btn-review-back')?.addEventListener('click', () => { elReviewSection.classList.add('hidden'); showDefaultStep(); });
$('btn-review-back-2')?.addEventListener('click', () => { elReviewSection.classList.add('hidden'); showDefaultStep(); });
// 取消分析
$('btn-cancel-analysis')?.addEventListener('click', () => {
    if (_analysisAbortController) _analysisAbortController.abort();
    analysisInProgress = false; showDefaultStep(); hideLoading();
    elBtnAnalyze.disabled = false;
});

// ========== 验盘反馈 ==========

/** 从 Agent 验盘输出中提取预测条目 */
function extractVerificationPredictions(assistantText) {
    const preds = [];
    const text = assistantText;
    const chineseNum = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10};

    // 主格式：### 第N件：title（Agent 实际输出格式，2026-06-24）
    // 示例：### 第一件：学历 & 高考（2023 年, 18 岁）
    const sectionPattern = /###\s*第([一二三四五六七八九十\d]+)件[：:]\s*([^\n]+)\n([\s\S]+?)(?=\n###\s*第[一二三四五六七八九十\d]+件[：:]|\n---\s*\n>|$)/g;
    let m;
    while ((m = sectionPattern.exec(text)) !== null) {
        const title = m[2].trim().replace(/\*+/g, '').substring(0, 80);
        let body = m[3].trim();
        // 去掉末尾的 --- 分隔线
        body = body.replace(/\n*---\s*$/, '').trim();
        // 优先取"预测特征"段，兜底取全部
        const predMatch = body.match(/预测特征[：:][\s\S]*/);
        if (predMatch) {
            body = predMatch[0];
        }
        // 去掉末尾的提问句（**→ ...？**）
        body = body.replace(/\*\*→[\s\S]*$/, '').trim();
        // 去掉 blockquote 标记，合并换行
        body = body.replace(/^>\s*/gm, '').replace(/\n+/g, ' ').substring(0, 800);
        if (body.length > 15 && !/流年全扫描|排盘确认|验盘前/.test(title + body)) {
            preds.push({index: preds.length, title: title, body: body});
        }
    }

    // 兜底1：**【A级验证】标题** / **【B级验证】标题** 等结构化格式
    if (preds.length === 0) {
        const verificationBlock = /\*\*【([^】]+)】\s*(.+?)\*\*\s*\n+(.+?)(?=\n\*\*【|$)/gs;
        while ((m = verificationBlock.exec(text)) !== null) {
            const title = m[2].trim();
            const body = m[3].trim().substring(0, 800).replace(/\n+/g, ' ');
            if (body.length > 15 && !/流年全扫描|排盘确认|验盘前/.test(title + body)) {
                preds.push({index: preds.length, title: title, body: body});
            }
        }
    }

    // 兜底2：**预测①：...** / **预测一：...** 等旧格式
    if (preds.length === 0) {
        const circledNum = {'①':1,'②':2,'③':3,'④':4,'⑤':5,'⑥':6,'⑦':7,'⑧':8,'⑨':9,'⑩':10};
        const oldPattern = /\*\*预测([①②③④⑤⑥⑦⑧⑨⑩一二三四五六七八九十\d]+)[：:]\*\*\s*(.+?)(?=\*\*预测[①②③④⑤⑥⑦⑧⑨⑩一二三四五六七八九十\d]+[：:]|$)/gs;
        while ((m = oldPattern.exec(text)) !== null) {
            const numStr = m[1].trim();
            const idx = circledNum[numStr] || chineseNum[numStr] || parseInt(numStr) || (preds.length + 1);
            let body = m[2].trim().substring(0, 800).replace(/\*\*/g, '').replace(/\n+/g, ' ').trim();
            if (body.length > 10 && !/流年全扫描|排盘确认/.test(body)) {
                preds.push({index: preds.length, title: '验证项' + idx, body: body});
            }
        }
    }

    // 兜底3：从验盘段落到下一章节之间，按 ### 标题分块
    if (preds.length === 0) {
        const verifySection = text.match(/验盘[：:\—\-]+.*?\n([\s\S]+?)(?=\n##\s|\n#\s|$)/);
        if (verifySection) {
            const blocks = verifySection[1].split(/\n###\s+/).filter(b => b.trim().length > 30 && !/^>/.test(b.trim()));
            blocks.forEach((b, i) => {
                const lines = b.trim().split('\n');
                let title = lines[0].replace(/\*\*/g, '').replace(/^#+\s*/, '').substring(0, 40);
                preds.push({index: i, title: title, body: b.replace(/\n+/g, ' ').substring(0, 800)});
            });
        }
    }

    return preds.slice(0, 5);
}

/** 渲染验盘反馈面板 */
function renderVerificationPanel(predictions) {
    const panel = $('verify-panel');
    const container = $('verify-predictions');
    container.innerHTML = '';

    predictions.forEach((pred, i) => {
        const div = document.createElement('div');
        div.className = 'verify-prediction';
        div.innerHTML = `
            <div class="verify-pred-header">
                <span class="verify-pred-num">#${i + 1}</span>
                <span class="verify-pred-title">${escapeHtml(pred.title)}</span>
            </div>
            <div class="verify-pred-body">${escapeHtml(pred.body)}</div>
            <div class="verify-pred-btns" data-idx="${pred.index}">
                <button class="verify-btn verify-yes" data-label="correct" onclick="setVerifyLabel(${pred.index}, 'correct', this)">✓ 准确</button>
                <button class="verify-btn verify-maybe" data-label="partially_correct" onclick="setVerifyLabel(${pred.index}, 'partially_correct', this)">⚠ 部分准确</button>
                <button class="verify-btn verify-no" data-label="wrong" onclick="setVerifyLabel(${pred.index}, 'wrong', this)">✗ 不对</button>
            </div>
            <textarea class="verify-note" id="verify-note-${pred.index}" placeholder="补充说明（可选）：实际情况是..." rows="1"></textarea>
        `;
        container.appendChild(div);
    });

    panel.classList.remove('hidden');
    $('app-main').style.paddingBottom = '220px';
    $('verify-status').textContent = '';
    $('btn-verify-submit').disabled = false;
}

/** 设置单条预测的标签 */
function setVerifyLabel(idx, label, btnEl) {
    _verifyLabels[idx] = label;
    // 高亮选中按钮
    const btns = btnEl.parentElement.querySelectorAll('.verify-btn');
    btns.forEach(b => b.classList.remove('selected'));
    btnEl.classList.add('selected');
}

/** 提交验盘反馈 */
async function submitVerification() {
    if (!_feedbackFile) {
        $('verify-status').textContent = '⚠ 缺少反馈文件名，无法提交';
        return;
    }
    const preds = [];
    for (const [idx, label] of Object.entries(_verifyLabels)) {
        const noteEl = document.getElementById('verify-note-' + idx);
        preds.push({
            index: parseInt(idx),
            label: label,
            user_note: noteEl ? noteEl.value.trim() : '',
        });
    }
    if (preds.length === 0) {
        $('verify-status').textContent = '⚠ 请至少对一条预测进行确认';
        return;
    }

    $('btn-verify-submit').disabled = true;
    $('verify-status').textContent = '提交中...';

    try {
        const r = await fetch('/api/verify', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({feedback_file: _feedbackFile, predictions: preds}),
        });
        const d = await r.json();
        if (d.success) {
            const s = d.summary;
            $('verify-status').innerHTML = `✅ 反馈已保存！准确 ${s.correct}/${s.total}，命中率 ${Math.round(s.hit_rate * 100)}%`;
            // 禁用所有按钮
            document.querySelectorAll('.verify-btn').forEach(b => b.disabled = true);
            document.querySelectorAll('.verify-note').forEach(t => t.disabled = true);
            $('btn-verify-submit').disabled = true;
            // 2秒后自动隐藏面板
            setTimeout(() => {$('verify-panel').classList.add('hidden');$('app-main').style.paddingBottom=''}, 2000);
        } else {
            $('verify-status').textContent = '❌ ' + (d.error || '提交失败');
            $('btn-verify-submit').disabled = false;
        }
    } catch (e) {
        $('verify-status').textContent = '❌ 网络错误';
        $('btn-verify-submit').disabled = false;
    }
}
$('btn-verify-submit').addEventListener('click', submitVerification);

function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

// ========== 续接对话（SSE 流式进度） ==========
elBtnChatSend.addEventListener('click', async () => {
    const reply=elChatInput.value.trim();if(!reply||!conversationMessages)return;elBtnChatSend.disabled=true;elChatInput.disabled=true;showLoading('准备分析...');analysisInProgress=true;
    savePendingAnalysis();
    let lastError = '';
    for (let attempt=0;attempt<2;attempt++) {
        if (attempt>0) showLoading(`第 ${attempt+1} 次重试中...`);
        const ctrl = new AbortController();
        const timeoutId = setTimeout(() => ctrl.abort(), 10*60*1000);
        try {
            const pw = getPassword();
            const r = await fetch('/api/analyze/stream/continue',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:conversationMessages,reply:reply, password:pw, conversation_id: conversationId}), signal: ctrl.signal});
            clearTimeout(timeoutId);
            if (!r.ok) {
                const d = await r.json().catch(()=>({}));
                if (d.need_password) {
                    clearPendingAnalysis();
                    const p = await promptLoginOrPassword(d.error);
                    if (!p) { hideLoading(); elBtnChatSend.disabled=false; elChatInput.disabled=false; analysisInProgress=false; return; }
                    sessionStorage.setItem('bazi_pw', p);
                    continue; // 带密码重试
                }
                if (d.rate_limited) { showUpgradeToast(d.error, d.tier); hideLoading(); elBtnChatSend.disabled=false; elChatInput.disabled=false; analysisInProgress=false; return; }
                lastError = d.error||`HTTP ${r.status}`;
                if (attempt===0) { await new Promise(r=>setTimeout(r,3000)); continue; }
                showError(lastError); clearPendingAnalysis(); hideLoading(); elBtnChatSend.disabled=false; elChatInput.disabled=false; analysisInProgress=false; return;
            }
            // 读取 SSE 流
            const reader = r.body.getReader(); const decoder = new TextDecoder(); let buf = '', resultData = null;
            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                buf += decoder.decode(value, {stream: true});
                const parts = buf.split('\n\n'); buf = parts.pop();
                for (const part of parts) {
                    let evtData = '';
                    for (const line of part.split('\n')) {
                        if (line.startsWith('data: ')) { evtData = line.slice(6); break; }
                    }
                    if (!evtData) continue;
                    try { const p = JSON.parse(evtData);
                        if (p.event === 'progress') {
                            if (!$('progress-bar').style.display || $('progress-bar').style.display === 'none') showProgress();
                            updateProgress(p.phase_index - 1);
                            _stopStageCarousel(false);
                            elLoadingText.style.display = 'none';
                        }
                        else if (p.event === 'result') { resultData = p; }
                    } catch(e) {}
                }
                if (resultData) break;
            }
            reader.cancel();
            if (!resultData || !resultData.success) {
                lastError = (resultData&&resultData.error)||'续接失败';
                if (attempt===0) { await new Promise(r=>setTimeout(r,3000)); continue; }
                showError(lastError); clearPendingAnalysis(); hideLoading(); elBtnChatSend.disabled=false; elChatInput.disabled=false; analysisInProgress=false; return;
            }
            // 成功
            clearPendingAnalysis();
            conversationMessages.push({role:'user',content:reply});conversationMessages.push({role:'assistant',content:resultData.analysis});saveConversation();
            analysisText = (analysisText||'') + '\n\n---\n\n**💬 ' + reply + '**\n\n' + resultData.analysis;
            localStorage.setItem('bazi_analysis', analysisText);
            const replyDiv = document.createElement('div'); replyDiv.className='chat-reply'; replyDiv.innerHTML = formatMarkdown(resultData.analysis); injectGlossary(replyDiv);
            elAnalysisContent.append(document.createElement('hr'), replyDiv);
            elChatInput.value='';elAnalysisContent.scrollIntoView({behavior:'smooth',block:'end'});
            hideLoading();elBtnChatSend.disabled=false;elChatInput.disabled=false;analysisInProgress=false;return;
        } catch(e) {
            clearTimeout(timeoutId);
            lastError = e.name==='AbortError' ? '分析超时（超过10分钟），请重试或简化问题' : (e.message||'网络错误');
            if (attempt===0) { await new Promise(r=>setTimeout(r,3000)); continue; }
            clearPendingAnalysis();
            showError(lastError);
        }
    }
    hideLoading();elBtnChatSend.disabled=false;elChatInput.disabled=false;analysisInProgress=false;
});

// ========== 打印报告 ==========
elBtnPdf.addEventListener('click',()=>{localStorage.setItem('bazi_plate',JSON.stringify(plateData));localStorage.setItem('bazi_analysis',analysisText||'');window.open('/report','_blank');});
elBtnAnalysisPdf.addEventListener('click',()=>{if(!plateData||!analysisText)return;window.open('/report','_blank');});

// ========== 页面关闭提醒 ==========
window.addEventListener('beforeunload', e => {
    if (analysisInProgress) {
        // 分析中关闭页面：保存 pending 状态（已由 doAnalyze 保存过，这里做二次确认）
        savePendingAnalysis();
        e.preventDefault();
        e.returnValue = '分析正在进行中，关闭页面将丢失结果。确定离开吗？（重新打开页面可自动恢复）';
        return e.returnValue;
    }
});

// ========== 标签页可见性变化检测 ==========
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && analysisInProgress) {
        // 回到标签页，检查是否已超时（超过 8 分钟没响应 → 可能已断线）
        const elapsed = Date.now() - _analysisStartTime;
        if (elapsed > 8 * 60 * 1000 && _analysisAbortController) {
            // 超时，主动取消并发起重试
            _analysisAbortController.abort();
            _analysisAbortController = null;
            const p = loadPendingAnalysis();
            if (p && p.retries < 3) {
                p.retries++;
                localStorage.setItem('bazi_analysis_pending', JSON.stringify(p));
                analysisInProgress = false; showDefaultStep();
                elBtnAnalyze.disabled = false;
                hideLoading();
                showLoading('检测到分析超时，即将自动重试...');
                setTimeout(() => doAnalyze(true), 2000);
            }
        }
    }
});

// ========== 恢复分析（页面加载时） ==========
(function restoreAnalysis(){
    // 1) 优先恢复已完成的完整分析
    const saved = localStorage.getItem('bazi_analysis'), savedPlate = localStorage.getItem('bazi_plate');
    if (saved && savedPlate) {
        try {
            const sd = JSON.parse(savedPlate), inp = sd.input;
            if (inp && inp.birth_datetime && inp.birth_datetime.startsWith(`${elYear.value}-${String(elMonth.value).padStart(2, '0')}-${String(elDay.value).padStart(2, '0')} ${String(elHour.value).padStart(2, '0')}`) && inp.gender === document.querySelector('input[name="gender"]:checked').value) {
                plateData = sd; analysisText = saved;
                renderResult(plateData);
                elResultSection.classList.remove('hidden');
                elBtnPdf.disabled = false; elBtnZiweiSwitch.disabled = false; elBtnAnalyze.disabled = false;
                elAnalysisContent.innerHTML = formatMarkdown(analysisText);
                injectGlossary(elAnalysisContent);
                elAnalysisSection.classList.remove('hidden');
                elBtnAnalysisPdf.disabled = false;
                // 恢复流年
                loadLiunian(plateData);
                // 恢复用神
                try { const ys = JSON.parse(localStorage.getItem('bazi_yongshen')); if (ys) renderYongshenCard(ys); } catch(e) {}
                // 恢复对话上下文（analysisText 已含全部聊天，只需恢复 messages 用于续接）
                if (loadConversation()) {
                    elAnalysisChat.classList.remove('hidden');
                }
            } else {
                localStorage.removeItem('bazi_analysis');
                localStorage.removeItem('bazi_plate');
                clearConversation();
            }
        } catch(e) {}
    }

    // 2) 检查是否有中断的待处理分析
    const pending = loadPendingAnalysis();
    if (pending && !saved) {
        // 恢复 plateData 并触发自动重试
        plateData = pending.plate;
        renderResult(plateData);
        elResultSection.classList.remove('hidden');
        elBtnPdf.disabled = false; elBtnZiweiSwitch.disabled = false; elBtnAnalyze.disabled = false;
        document.getElementById('charts-section').classList.remove('hidden');
        // 标记为已完成恢复，等用户回来后再触发分析
        if (pending.retries < 3) {
            // 延迟一下再重试，让页面先渲染
            setTimeout(() => {
                showLoading('检测到上次分析中断，正在自动恢复...');
                doAnalyze(true);
            }, 1000);
        } else {
            showError('上次分析已失败 3 次，请手动重新开始');
            clearPendingAnalysis();
        }
    }
})();

// ========== 网络信息 ==========
(async function loadNetworkInfo(){try{const r=await fetch('/api/network-info');const info=await r.json();const urls=[`<a href="${info.access_url}" target="_blank">${info.access_url}</a>`];if(info.lan_urls&&info.lan_urls.length>0){urls.push('<span style="font-size:0.75em;color:#aaa">局域网：</span>');info.lan_urls.forEach(url=>urls.push(`<a href="${url}" target="_blank">${url}</a>`));}$('access-urls').innerHTML=urls.join('<br>');if(info.lan_urls&&info.lan_urls.length>0){const qrUrl='/api/qrcode?url='+encodeURIComponent(info.lan_urls[0]);$('access-qr').innerHTML=`<img src="${qrUrl}" alt="扫码访问" class="qr-img">`;$('access-hint').innerHTML='⚠️ 手机和电脑需连接<strong>同一 WiFi</strong>才能访问局域网地址';}else{$('access-qr').innerHTML='';$('access-hint').innerHTML='🌐 已部署到公网，任何人可直接访问';}}catch(e){$('access-urls').innerHTML=window.location.origin;$('access-hint').innerHTML='';}})();

// ========== 清空表单 ==========
$('btn-clear').addEventListener('click', () => {
    [elYear,elMonth,elDay,elHour,elMinute,elLocation,elLongitude].forEach(el => el.value = '');
    elLongitude.value = '120';
    elUseTrueSolar.checked = false; elLngLat.style.display = 'none';
    elGeocodeStatus.classList.add('hidden'); elSuggestions.classList.add('hidden');
    plateData = null; analysisText = null; clearConversation(); _liunianData = null;
    elResultSection.classList.add('hidden'); elAnalysisSection.classList.add('hidden');
    document.getElementById('charts-section').classList.add('hidden');
    $('liunian-section').classList.add('hidden');
    const yc = $('yongshen-card'); if (yc) yc.style.display = 'none';
    elBtnPdf.disabled = true; elBtnAnalyze.disabled = true; elBtnAnalysisPdf.disabled = true; elBtnZiweiSwitch.disabled = true;
    localStorage.removeItem('bazi_form'); localStorage.removeItem('bazi_analysis'); localStorage.removeItem('bazi_plate'); localStorage.removeItem('bazi_yongshen');
    clearPendingAnalysis();
    hideError(); autoFillNow();
});

// ========== 八字学堂 ==========
function renderXuetang(){
    const catOrder = ['基础','调候','格局','旺衰','病药','十神','地支','大运','神煞'];
    const catTerms = {
        '基础': ['日主','月令','四柱','真太阳时','纳音','胎元命宫身宫'],
        '调候': ['调候'],
        '格局': ['格局','用神','喜神','忌神','闲神','成格','破格'],
        '旺衰': ['旺衰','身强','身弱','得令','得根','得气','得地','得势'],
        '病药': ['病药'],
        '十神': ['十神','正官','七杀','正财','偏财','正印','偏印','食神','伤官','比肩','劫财','透出','虚透','藏而不透'],
        '地支': ['刑冲合害','拱','夹','暗合','墓库','开库','星宫同参','截脚','盖头'],
        '大运': ['大运','流年','引动','伏吟','反吟','空亡'],
        '神煞': ['天乙贵人','文昌','桃花','驿马','羊刃','华盖']
    };
    // 扩展词条内容：含出处
    const extra = {
        '天乙贵人': '主贵人提携、逢凶化吉。\"甲戊庚牛羊，乙己鼠猴乡\"——以日干/年干查神煞',
        '文昌': '主学业文采、考试运。文昌入命者学习能力强',
        '桃花': '主异性缘、人缘、社交魅力。子午卯酉为四桃花',
        '驿马': '主奔波、迁徙、出国、变动。寅申巳亥为四驿马',
        '羊刃': '主刚强暴烈、竞争意识。\"羊刃重重又见禄，富贵荣华享不足\"——过旺则反噬',
        '华盖': '主孤高清高、才情、宗教玄学缘分。\"华盖逢空，偏宜僧道\"',
        '纳音': '每组干支对应的五行音律属性——如乙酉纳音\"泉中水\"。共30组纳音',
        '胎元命宫身宫': '胎元=受胎月份（月柱天干+1，地支+3）；命宫=安命之宫；身宫=安身之宫。三者辅助参考',
        '真太阳时': '根据出生地经度校正后的真实太阳时间。东莞(113.75°E)比北京时间晚约25分钟，时辰临近边界时校正可能换时柱',
    };
    const cats = {}; catOrder.forEach(c => cats[c] = []);
    Object.entries(GLOSSARY).forEach(([term, desc]) => {
        let found = false;
        for(const [cat, terms] of Object.entries(catTerms)){
            if(terms.includes(term)){ cats[cat].push({term, desc: extra[term] ? desc + '。' + extra[term] : desc}); found = true; break; }
        }
        if(!found) cats['基础'].push({term, desc}); // fallback
    });
    let html = '';
    catOrder.forEach(cat => {
        if(!cats[cat].length) return;
        html += `<div class="xuetang-cat"><h4 class="xuetang-cat-title">${cat}</h4><div class="xuetang-terms">`;
        cats[cat].forEach(({term,desc}) => {
             html += `<div class="xuetang-term"><span class="glossary-term" style="font-weight:700;margin-right:4px;">${term}</span><span class="xuetang-desc">${desc}</span></div>`;
        });
        html += '</div></div>';
    });
    $('xuetang-grid').innerHTML = html;
}

// ========== 紫微斗数抽屉 ==========
function openZiweiDrawer() {
    if (!plateData) { toast('请先排盘'); return; }
    if (ziweiAnalysisInProgress) return;

    // 复用主表单出生参数
    const y = elYear.value, m = elMonth.value, d = elDay.value, h = elHour.value;
    const min = elMinute.value || '0';
    const gender = document.querySelector('input[name="gender"]:checked')?.value || '男';
    const lng = elLongitude.value || '120';
    const loc = elLocation.value || '';
    const calendar = document.querySelector('input[name="calendar"]:checked')?.value || 'solar';
    const isLunar = calendar === 'lunar';

    if (!y || !m || !d || !h) { toast('请先填写完整出生信息'); return; }

    elZiweiOverlay.classList.remove('hidden');
    elZiweiDrawer.classList.add('open');
    elZiweiChartSection.classList.add('hidden');
    elZiweiAnalysisSection.classList.add('hidden');
    elZiweiLoading.classList.remove('hidden');
    elBtnZiweiAnalyze.disabled = true;
    ziweiPlateData = null; ziweiAnalysisText = null;

    fetch('/api/ziwei/paipan', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({year:parseInt(y),month:parseInt(m),day:parseInt(d),
            hour:parseInt(h),minute:parseInt(min),gender,longitude:parseFloat(lng),
            location:loc,is_lunar:isLunar})
    }).then(r=>r.json()).then(data=>{
        if (data.error) { toast('紫微排盘失败: '+data.error); elZiweiLoading.classList.add('hidden'); return; }
        ziweiPlateData = data;
        localStorage.setItem('ziwei_plate', JSON.stringify(data));
        renderZiweiChart(data);
        elZiweiLoading.classList.add('hidden');
        elZiweiChartSection.classList.remove('hidden');
        elBtnZiweiAnalyze.disabled = false;
    }).catch(e=>{ toast('网络错误: '+e.message); elZiweiLoading.classList.add('hidden'); });
}

function closeZiweiDrawer() {
    elZiweiDrawer.classList.remove('open');
    setTimeout(()=>{ elZiweiOverlay.classList.add('hidden'); }, 350);
}

function renderZiweiChart(data) {
    const palaces = data.palaces || [];
    if (palaces.length !== 12) { elZiweiGrid.innerHTML = '<p style="color:red">宫位数不对</p>'; return; }

    // 计算当前年龄 → 定位当前大限宫
    const birthStr = data.input?.birth_datetime || '';
    const birthYear = parseInt(birthStr) || 0;
    const currentYear = new Date().getFullYear();
    const approxAge = birthYear ? currentYear - birthYear : -1;

    let currentDecadalIdx = -1;
    if (approxAge >= 0) {
        for (const pal of palaces) {
            const range = pal.decadal_range || '';
            const m = range.match(/(\d+)-(\d+)/);
            if (m) {
                const lo = parseInt(m[1]), hi = parseInt(m[2]);
                if (approxAge >= lo && approxAge <= hi) { currentDecadalIdx = pal.index; break; }
            }
        }
    }

    // 4x4 grid: 12 outer cells + center
    let html = '';
    for (let row = 1; row <= 4; row++) {
        for (let col = 1; col <= 4; col++) {
            // Center area
            if (row >= 2 && row <= 3 && col >= 2 && col <= 3) {
                if (row === 2 && col === 2) {
                    const wuxingEmoji = {'水二局':'🌊','木三局':'🌳','金四局':'⛰️','土五局':'🏔️','火六局':'🔥'};
                    html += `<div class="ziwei-center">
                        <div class="center-icon">🔮</div>
                        <div class="center-title">紫微斗数</div>
                        <div class="center-row">${wuxingEmoji[data.five_elements_class]||'📐'} <strong>${data.five_elements_class||'?'}</strong></div>
                        <div class="center-row">命宫 <strong>${data.soul_palace||'?'}</strong> · 身宫 <strong>${data.body_palace||'?'}</strong></div>
                        <div class="center-row">生年四化 <strong>${(data.year_mutagens||[]).length}</strong> 条</div>
                    </div>`;
                }
                continue;
            }
            // Find palace at this grid position
            const pal = palaces.find(p => p.grid_row === row && p.grid_col === col);
            if (!pal) { html += '<div class="ziwei-cell empty-cell"></div>'; continue; }

            const isCurrent = pal.index === currentDecadalIdx;
            let cellClass = 'ziwei-cell';
            if (pal.is_empty) cellClass += ' empty-cell';
            if (isCurrent) cellClass += ' current-decadal';

            // Tags
            let tags = '';
            if (pal.tags?.includes('命宫')) tags += '<span class="cell-tag tag-ming">命</span>';
            if (pal.tags?.includes('身宫')) tags += '<span class="cell-tag tag-shen">身</span>';

            // Build star rows with brightness + mutagen
            let starHtml = '';
            const majorStars = pal.major_stars || [];
            for (const s of majorStars) {
                const name = typeof s === 'string' ? s : s.name;
                const typeCls = (typeof s === 'object' && s.css) ? s.css.replace('star-','') : 'major';
                let row = `<span class="star-name ${typeCls}">${name}</span>`;
                if (typeof s === 'object' && s.brightness) {
                    row += `<span class="star-brightness ${s.brightness_css||''}">${s.brightness}</span>`;
                }
                if (typeof s === 'object' && s.mutagen) {
                    row += `<span class="star-mutagen ${s.mutagen_css||''}">${s.mutagen_mark||s.mutagen}</span>`;
                }
                starHtml += `<div class="star-row">${row}</div>`;
            }
            if (!starHtml) starHtml = '<div class="star-row" style="color:var(--text-muted);font-size:.8em">' + (pal.is_empty ? '空宫' : '—') + '</div>';

            // Minor stars
            let minorHtml = '';
            const minorStars = pal.minor_stars || [];
            if (minorStars.length) {
                const names = minorStars.map(s => typeof s === 'string' ? s : s.name).slice(0, 4);
                minorHtml = `<div class="cell-minor">${names.join(' ')}</div>`;
            }

            // Decadal hint
            const decadalHint = pal.decadal_range ? `<div class="cell-decadal">${isCurrent ? '▸ 当前' : ''} ${pal.decadal_range}岁</div>` : '';

            html += `<div class="${cellClass}">
                ${tags}
                <div class="cell-name">${pal.name}</div>
                <div class="cell-dizhi">${pal.dizhi||''}</div>
                <div class="cell-stars">${starHtml}</div>
                ${minorHtml}
                ${decadalHint}
            </div>`;
        }
    }
    elZiweiGrid.innerHTML = html;

    // 生年四化 badges
    const mutagens = data.year_mutagens || [];
    if (mutagens.length) {
        const muCls = {'化禄':'mu-lu','化权':'mu-quan','化科':'mu-ke','化忌':'mu-ji'};
        const marks = {'化禄':'◈','化权':'▲','化科':'◎','化忌':'✕'};
        elZiweiMutagenLine.innerHTML = mutagens.map(m =>
            `<span class="mutagen-badge ${muCls[m.mutagen]||''}">${marks[m.mutagen]||''} ${m.star}${m.mutagen}<span style="font-weight:400;margin-left:3px">${m.palace}</span></span>`
        ).join('');
    } else {
        elZiweiMutagenLine.innerHTML = '';
    }
}

async function doZiweiAnalyze() {
    if (!ziweiPlateData || ziweiAnalysisInProgress) return;
    ziweiAnalysisInProgress = true;
    elBtnZiweiAnalyze.disabled = true;
    elBtnZiweiAnalyze.textContent = '⏳ 分析中...';
    elZiweiAnalysisContent.innerHTML = '<p style="text-align:center;color:var(--text-muted)">AI 正在解读你的紫微命盘...</p>';
    elZiweiAnalysisSection.classList.remove('hidden');

    const pw = sessionStorage.getItem('bazi_pw') || '';

    try {
        const r = await fetch('/api/ziwei/analyze', {
            method:'POST', headers:Object.assign({'Content-Type':'application/json'}, typeof authHeaders === 'function' ? authHeaders() : {}),
            body: JSON.stringify({plate:ziweiPlateData, password:pw})
        });
        const d = await r.json();
        if (d.need_password) {
            const p = await promptLoginOrPassword(d.error);
            if (!p) { elBtnZiweiAnalyze.disabled=false; elBtnZiweiAnalyze.textContent='🧠 开始解读'; ziweiAnalysisInProgress=false; return; }
            sessionStorage.setItem('bazi_pw', p);
            return doZiweiAnalyze(); // retry
        }
        if (!d.success) {
            if (d.rate_limited) { showUpgradeToast(d.error, d.tier); ziweiAnalysisInProgress = false; elBtnZiweiAnalyze.disabled = false; elBtnZiweiAnalyze.textContent = '🧠 开始解读'; return; }
            elZiweiAnalysisContent.innerHTML = `<p style="color:red">分析失败: ${d.error||'未知错误'}</p>`;
            ziweiAnalysisInProgress = false;
            elBtnZiweiAnalyze.disabled = false;
            elBtnZiweiAnalyze.textContent = '🔄 重试';
            return;
        }
        ziweiAnalysisText = d.analysis;
        localStorage.setItem('ziwei_analysis', d.analysis);
        elZiweiAnalysisContent.innerHTML = formatMarkdown(d.analysis);
        injectGlossaryZiwei(elZiweiAnalysisContent);
        elZiweiDrawerFooter.classList.add('hidden');  // hide button after success
    } catch(e) {
        elZiweiAnalysisContent.innerHTML = `<p style="color:red">网络错误: ${e.message}</p>`;
        ziweiAnalysisInProgress = false;
        elBtnZiweiAnalyze.disabled = false;
        elBtnZiweiAnalyze.textContent = '🔄 重试';
    }
    ziweiAnalysisInProgress = false;
}

// ---- 紫微斗数词条高亮 ----
const ZIWEI_GLOSSARY = {
    '命宫':'命盘的核心宫位，代表先天禀赋、性格底色、人生大方向',
    '身宫':'后天发展重心，30岁后影响力逐渐超过命宫',
    '三方四正':'本宫+对宫+左右三合宫，判断星曜力量的关键',
    '四化':'化禄(机遇/财富流)、化权(掌控力/竞争)、化科(名声/贵人)、化忌(业力/课题)',
    '空宫':'宫内无主星，借对宫星曜来参考解读。空宫不代表不好，反而是可塑性强的表现',
    '大限':'每十年一换的运势周期，由本命盘各宫的大限干支决定起止年龄',
    '紫微':'帝王星，主贵气、领导力。入命者有掌控欲和管理天赋',
    '天机':'智谋星，主聪明、善变、策划。思维敏捷，适合脑力工作',
    '太阳':'光明星，主热情、公益、名望。庙旺则光芒四射，落陷则心力不足',
    '武曲':'财星，主果断、刚毅、理财。执行力强，适合金融/军警',
    '天同':'福星，主温和、享受、人缘。性格温顺但要防缺乏进取心',
    '廉贞':'囚星/次桃花，主执着、才艺、刚烈。重情义但易纠结',
    '天府':'库星，主稳重、包容、管理。有组织力，是优秀的二把手',
    '太阴':'富星/母星，主细腻、内敛、美感。情感丰富，适合文艺创作',
    '贪狼':'桃花星/欲望星，主交际、才艺、贪念。多才多艺但要有制',
    '巨门':'暗星，主口才、是非、研究。宜深耕专业或以口为业',
    '天相':'印星，主服务、协调、忠诚。天生好帮手',
    '天梁':'荫星，主正直、慈悲、长寿。有侠义心肠',
    '七杀':'将星，主魄力、开拓、刚猛。适合创业/军警/外科',
    '破军':'耗星，主变革、破坏、创新。天生折腾，不适合安稳工作',
    '化禄':'四化之一，代表机遇、财富流入、顺利。所在宫位有先天好运',
    '化权':'四化之一，代表掌控力、竞争、权威。所在宫位有主导能力',
    '化科':'四化之一，代表名声、贵人、学识。所在宫位有口碑和贵人',
    '化忌':'四化之一，代表业力、课题、执着。所在宫位是人生核心课题',
};

function injectGlossaryZiwei(container) {
    if (!container) return;
    const terms = Object.keys(ZIWEI_GLOSSARY).sort((a,b)=>b.length-a.length);
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    const replacements = [];
    while (walker.nextNode()) {
        const node = walker.currentNode;
        if (node.parentElement?.closest?.('.glossary-term,.cell-stars,.cell-minor,.cell-name,.cell-dizhi')) continue;
        let text = node.textContent;
        let changed = false;
        for (const term of terms) {
            const idx = text.indexOf(term);
            if (idx !== -1) {
                const span = document.createElement('span');
                span.className = 'glossary-term';
                span.title = ZIWEI_GLOSSARY[term];
                span.setAttribute('data-tip', ZIWEI_GLOSSARY[term]);
                span.textContent = term;
                replacements.push({node, idx, term, span});
                changed = true;
                break; // one replacement per node
            }
        }
    }
    for (const {node, idx, term, span} of replacements) {
        const before = node.textContent.slice(0, idx);
        const after = node.textContent.slice(idx + term.length);
        const parent = node.parentNode;
        const beforeNode = document.createTextNode(before);
        const afterNode = document.createTextNode(after);
        parent.insertBefore(beforeNode, node);
        parent.insertBefore(span, beforeNode.nextSibling);
        parent.insertBefore(afterNode, span.nextSibling);
        parent.removeChild(node);
    }
}

// ---- 紫微斗数初始化 ----
elBtnZiweiAnalyze.addEventListener('click', doZiweiAnalyze);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeZiweiDrawer(); });

// ========== 初始化 ==========
loadForm(); autoFillNow(); renderHistory(); renderXuetang();
document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')elBtnPaipan.click();});
$('btn-clear-history').addEventListener('click', ()=>{ saveHistory([]); renderHistory(); });
$('history-count').textContent = loadHistory().length;

// ========== 滚动揭示（IntersectionObserver，受 Species in Pieces 启发）==========
function setupScrollReveal() {
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'revealIn 0.6s cubic-bezier(0.22,0.61,0.36,1) forwards';
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -30px 0px' });

    // 观察分析区的 h2/h3/blockquote
    const els = document.querySelectorAll('#analysis-content h2, #analysis-content h3, #analysis-content blockquote');
    els.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        observer.observe(el);
    });
}
// 每次分析渲染后调用
const _origRenderMarkdown = formatMarkdown;
formatMarkdown = function(text) {
    const html = _origRenderMarkdown(text);
    setTimeout(setupScrollReveal, 200);  // DOM 渲染后再绑定
    return html;
};

// ========== 粒子庆祝（分析完成时）==========
function particleBurst(x, y) {
    const colors = ['#d4a843','#f5e6a3','#c8a835','#e8c870','#f0d878','#fff','#8b6914'];
    const count = 60;
    const frag = document.createDocumentFragment();

    for (let i = 0; i < count; i++) {
        const p = document.createElement('div');
        const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.4;
        const velocity = 80 + Math.random() * 160;
        const size = 3 + Math.random() * 6;
        const color = colors[Math.floor(Math.random() * colors.length)];

        p.style.cssText = `
            position:fixed;left:${x}px;top:${y}px;width:${size}px;height:${size}px;
            background:${color};border-radius:${Math.random()>0.5?'50%':'2px'};
            pointer-events:none;z-index:9999;
            --dx:${Math.cos(angle)*velocity}px;--dy:${Math.sin(angle)*velocity-50}px;
            animation:particleFly ${0.6+Math.random()*0.8}s ease-out forwards;
            animation-delay:${Math.random()*0.15}s;
        `;
        frag.appendChild(p);
    }
    document.body.appendChild(frag);
    // 动画结束后清理
    setTimeout(() => {
        document.querySelectorAll('[style*="particleFly"]').forEach(el => el.remove());
    }, 1500);
}

// ========== 按钮点击波纹 ==========
document.addEventListener('click', e => {
    const btn = e.target.closest('.btn');
    if (!btn || btn.disabled) return;
    const ripple = document.createElement('span');
    ripple.className = 'btn-ripple';
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
    ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
    btn.appendChild(ripple);
    ripple.addEventListener('animationend', () => ripple.remove());
});

// ========== 流年运程 ==========
let _liunianData = null;
let _liunianIndex = 0;
const SIGNAL_LABELS = {A:'强冲刑',B:'中等',C:'轻微',D:'平顺'};

// ========== 用神喜忌卡片 ==========
const WUXING_EMOJI = {木:'🌳',火:'🔥',土:'⛰️',金:'⚜️',水:'💧'};
function renderYongshenCard(yongshen) {
    if (!yongshen || !yongshen.yong) return;
    const card = $('yongshen-card');
    const content = $('yongshen-content');
    if (!card || !content) return;

    const yong = yongshen.yong || '?';
    const xi = yongshen.xi || [];
    const ji = yongshen.ji || [];
    const xian = yongshen.xian || [];
    const reasoning = yongshen.reasoning || '';

    let html = '<div class="yongshen-main">';
    html += '<div class="yongshen-wx '+yong+'">'+yong+'</div>';
    html += '<div class="yongshen-label"><span class="label-tag">核心用神</span><br><span class="label-val">'+yong+'</span></div>';
    html += '</div>';

    if (xi.length > 0) {
        html += '<div class="yongshen-tags">';
        html += '<span style="font-size:0.72em;color:var(--text-muted);margin-right:4px">喜：</span>';
        xi.forEach(wx => { html += '<span class="yongshen-tag xi">'+wx+'</span>'; });
        html += '</div>';
    }
    if (ji.length > 0) {
        html += '<div class="yongshen-tags">';
        html += '<span style="font-size:0.72em;color:var(--text-muted);margin-right:4px">忌：</span>';
        ji.forEach(wx => { html += '<span class="yongshen-tag ji">'+wx+'</span>'; });
        html += '</div>';
    }
    if (xian.length > 0) {
        html += '<div class="yongshen-tags">';
        html += '<span style="font-size:0.72em;color:var(--text-muted);margin-right:4px">闲：</span>';
        xian.forEach(wx => { html += '<span class="yongshen-tag xian">'+wx+'</span>'; });
        html += '</div>';
    }
    if (reasoning) {
        html += '<div class="yongshen-reasoning">'+reasoning+'</div>';
    }

    content.innerHTML = html;
    card.style.display = '';
}

async function loadLiunian(plateData) {
    try {
        const r = await fetch('/api/liunian', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plate:plateData})});
        const d = await r.json();
        if (!d.success) return;
        _liunianData = d;
        // 跳到当前年份
        const now = new Date().getFullYear();
        _liunianIndex = d.years.findIndex(y => y.year === now);
        if (_liunianIndex < 0) _liunianIndex = Math.max(0, d.years.findIndex(y => y.year > now) - 1);
        if (_liunianIndex < 0) _liunianIndex = 0;
        renderLiunianTimeline();
        renderLiunianSignals();
        showLiunianYear(_liunianIndex);
        $('liunian-section').classList.remove('hidden');
        // 滚动到流年区域
        setTimeout(() => { $('liunian-section').scrollIntoView({behavior:'smooth',block:'center'}); }, 300);
    } catch(e) { console.error('liunian fetch fail', e); }
}

function showLiunianYear(idx) {
    if (!_liunianData || idx < 0 || idx >= _liunianData.years.length) return;
    _liunianIndex = idx;
    const y = _liunianData.years[idx];
    $('liunian-year').textContent = y.year;
    $('liunian-gz').textContent = y.gz;
    // 信号标签
    const sigEl = $('liunian-signal');
    sigEl.textContent = SIGNAL_LABELS[y.signal_level] || y.signal_level;
    sigEl.className = 'liunian-signal level-' + y.signal_level;
    // 元信息
    $('liunian-meta').innerHTML = '<span>纳音：'+y.nayin+'</span><span>十神：'+y.shishen+'</span><span>大运：'+y.dayun_gz+'（第'+y.dayun_step+'步）</span><span>年龄：'+y.age+'岁</span>';
    // 关系标签
    let relHtml = '';
    if (y.relations.length === 0) relHtml = '<span class="liunian-rel-tag">无特殊关系</span>';
    else y.relations.forEach(r => {
        const hasChong = r.relations.some(x => x.indexOf('冲')>=0 || x.indexOf('刑')>=0);
        const hasHe = r.relations.some(x => x.indexOf('合')>=0);
        let cls = 'liunian-rel-tag';
        if (hasChong) cls += ' has-chong';
        else if (hasHe) cls += ' has-he';
        relHtml += '<span class="'+cls+'">'+r.pillar+'('+r.pillar_zhi+') '+r.relations.join('·')+'</span>';
    });
    $('liunian-relations').innerHTML = relHtml;
    // 更新时间线 active，并滚动到可见
    const dots = document.querySelectorAll('.liunian-timeline-dot');
    dots.forEach((d,i) => d.classList.toggle('active', i === idx));
    const activeDot = document.querySelector('.liunian-timeline-dot.active');
    if (activeDot) activeDot.scrollIntoView({behavior:'smooth',block:'nearest',inline:'center'});
}

function renderLiunianTimeline() {
    if (!_liunianData) return;
    const tl = $('liunian-timeline');
    // 十年分组
    const years = _liunianData.years;
    const decadeStart = Math.floor(years[0].year / 10) * 10;
    let html = '';
    let currentDecade = -1;
    for (let i = 0; i < years.length; i++) {
        const y = years[i];
        const dec = Math.floor(y.year / 10) * 10;
        if (dec !== currentDecade) {
            currentDecade = dec;
            html += '<span class="liunian-decade-label">'+dec+'s</span>';
        }
        const title = y.year+' '+y.gz+' | '+y.shishen+' | '+(SIGNAL_LABELS[y.signal_level]||'平');
        html += '<span class="liunian-timeline-dot level-'+y.signal_level+(i===_liunianIndex?' active':'')+'" title="'+title+'" data-idx="'+i+'" onclick="showLiunianYear('+i+')"></span>';
    }
    tl.innerHTML = html;
    // 滚动到当前 active dot
    setTimeout(() => {
        const active = tl.querySelector('.liunian-timeline-dot.active');
        if (active) active.scrollIntoView({behavior:'smooth',block:'nearest',inline:'center'});
    }, 100);
}

function renderLiunianSignals() {
    if (!_liunianData) return;
    const el = $('liunian-signal-grid');
    if (!el) return;
    // 筛选 A/B 信号年份
    const signals = _liunianData.years.filter(y => y.signal_level === 'A' || y.signal_level === 'B');
    if (signals.length === 0) {
        el.innerHTML = '<div style="color:var(--text-muted);font-size:0.82em;text-align:center;padding:12px">此大运范围内无强信号年份</div>';
        return;
    }
    // 只显示前20个
    const display = signals.slice(0, 20);
    let html = '';
    display.forEach(y => {
        const relText = y.relations.map(r => r.pillar+r.relations.join('')).join(' ');
        const cls = y.signal_level === 'A' ? 'signal-card strong' : 'signal-card medium';
        html += '<div class="'+cls+'" onclick="showLiunianYear('+_liunianData.years.indexOf(y)+')" title="'+relText+'">';
        html += '<span class="signal-year">'+y.year+'</span>';
        html += '<span class="signal-gz">'+y.gz+'</span>';
        html += '<span class="signal-label">'+SIGNAL_LABELS[y.signal_level]+'</span>';
        html += '<span class="signal-age">'+y.age+'岁</span>';
        html += '</div>';
    });
    el.innerHTML = html;
}

// 按钮事件
document.addEventListener('DOMContentLoaded', () => {
    $('btn-liunian-prev').addEventListener('click', () => { if (_liunianIndex > 0) showLiunianYear(_liunianIndex-1); });
    $('btn-liunian-next').addEventListener('click', () => { if (_liunianData && _liunianIndex < _liunianData.years.length-1) showLiunianYear(_liunianIndex+1); });
    $('btn-liunian-jump').addEventListener('click', () => {
        if (!_liunianData) return;
        const now = new Date().getFullYear();
        const idx = _liunianData.years.findIndex(y => y.year === now);
        if (idx >= 0) showLiunianYear(idx);
    });
    // 键盘导航：流年区域上左右方向键切换年份
    document.addEventListener('keydown', e => {
        if (!_liunianData) return;
        const section = $('liunian-section');
        if (!section || section.classList.contains('hidden')) return;
        // 检查焦点是否在输入框内，那时不拦截方向键
        if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) return;
        if (e.key === 'ArrowLeft') { e.preventDefault(); if (_liunianIndex > 0) showLiunianYear(_liunianIndex-1); }
        else if (e.key === 'ArrowRight') { e.preventDefault(); if (_liunianData && _liunianIndex < _liunianData.years.length-1) showLiunianYear(_liunianIndex+1); }
    });
});
