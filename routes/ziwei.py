import io
import json
import os
import socket
import sys
import time as _time
import hashlib
import re
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request, send_file, Response, redirect
import requests

from bazi_calculator import paipan, get_shishen
from ziwei_calculator import ziwei_paipan, plate_to_dict as ziwei_plate_to_dict, get_horoscope
from utils.auth import check_password, check_rate_limit, check_conv_rate_limit, check_global_ip_limit, WEB_PASSWORD, ADMIN_TOKEN
from utils.tier import resolve_user_from_request, get_rate_limit, TIER_FREE
from utils.cache import _make_cache_key, _cache_get, _make_ziwei_cache_key, _cache_set
from utils.feedback import save_feedback_log

ziwei_bp = Blueprint("ziwei", __name__, url_prefix="/api/ziwei")

# ============================================================
# 紫微辅助函数
# ============================================================

_bazi_analysis_cache = {}

_ziwei_sessions = {}  # {session_id: {id, title, messages, plate_data, plate_summary, created_at}}

_SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')



def _compute_bazi_ref(plate_dict: dict) -> dict | None:
    """从紫微 plate_dict 提取生辰，排完整八字参考信息用于交叉验证"""
    input_info = plate_dict.get("input", {})
    birth_dt_str = input_info.get("birth_datetime", "")
    gender = input_info.get("gender", "")
    if not birth_dt_str or gender not in ("男", "女"):
        return None
    import re
    m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})", birth_dt_str)
    if not m:
        return None
    try:
        from bazi_calculator import paipan, get_shishen
        y, mo, d, h, mi = int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5])
        bp = paipan(y, mo, d, h, mi, gender=gender, apply_solar_correction=False)
        bp.compute()
        day_gan = bp.sizhu["day"]["gan"]
        _WX_G = {"甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土","庚":"金","辛":"金","壬":"水","癸":"水"}
        _WX_Z = {"子":"水","丑":"土","寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土","申":"金","酉":"金","戌":"土","亥":"水"}
        ss = getattr(bp, "shishen", {})
        pillars = []
        for key, label in [("year","年柱"),("month","月柱"),("day","日柱"),("hour","时柱")]:
            p = bp.sizhu[key]
            pillars.append({
                "label": label, "gz": p["gz"], "gan": p["gan"], "zhi": p["zhi"],
                "gan_wx": _WX_G.get(p["gan"],"?"), "zhi_wx": _WX_Z.get(p["zhi"],"?"),
                "shishen": ss.get(key, "")
            })
        wx_count = {"木":0,"火":0,"土":0,"金":0,"水":0}
        for p in pillars:
            wx_count[p["gan_wx"]] += 1
            wx_count[p["zhi_wx"]] += 1
        dayun_list = []
        if getattr(bp, "dayun", []):
            for i, du in enumerate(bp.dayun[:8]):
                dayun_list.append(f"{du['gz']}（{du['start_age']:.0f}-{du['end_age']:.0f}岁）")
        qiyun = getattr(bp, "qiyun", {})
        qiyun_age = getattr(qiyun, "qiyun_age", 0) if hasattr(qiyun, "qiyun_age") else qiyun.get("qiyun_age", 0)
        qiyun_str = f"{qiyun_age:.1f}岁起运（{qiyun.get('direction','')}）" if qiyun else ""
        result = {
            "rizhu": bp.sizhu["day"]["gz"],
            "ri_gan": day_gan,
            "ri_gan_wuxing": _WX_G.get(day_gan, "?"),
            "pillars": pillars,
            "wuxing": wx_count,
            "qiyun": qiyun_str,
            "dayun": dayun_list,
        }
        sizhu_key = " ".join(p["gz"] for p in pillars)
        if sizhu_key not in _bazi_analysis_cache:
            try:
                from analysis_service import _load_system_prompt as _load_bazi_sp, _call_api
                sp = _load_bazi_sp()
                pil_info = "\n".join(f"{p['label']} {p['gz']} {p['shishen']} {p['gan_wx']}/{p['zhi_wx']}" for p in pillars)
                wx_info = " ".join(f"{k}:{v}" for k,v in wx_count.items())
                qy_full = f"{qiyun_str}，大运：{' → '.join(dayun_list[:4])}"
                ba_user = f"""请对以下八字按梁湘润体系完成调候→格局→旺衰→病药分析，输出：

## 格局

## 旺衰

## 喜用神

## 调候

## 一句话综述

四柱：
{pil_info}

五行统计：{wx_info}
{qy_full}

注意：这是交叉验证用途的预分析，不需要验盘。"""
                a_res = _call_api(sp, [{"role":"user","content":ba_user}],
                    max_tokens=4096, temperature=0.3, timeout=120)
                if a_res.get("success") and a_res.get("text"):
                    _bazi_analysis_cache[sizhu_key] = a_res["text"]
            except Exception:
                pass
        if sizhu_key in _bazi_analysis_cache:
            result["bazi_analysis"] = _bazi_analysis_cache[sizhu_key]
        return result
    except Exception as e:
        import logging
        logging.warning("bazi_ref generation failed: %s", e)
        return None




def _load_sessions_from_disk():
    """从磁盘恢复会话"""
    try:
        if not os.path.exists(_SESSIONS_DIR):
            os.makedirs(_SESSIONS_DIR)
            return
        for fn in os.listdir(_SESSIONS_DIR):
            if fn.endswith('.json'):
                sid = fn[:-5]
                try:
                    with open(os.path.join(_SESSIONS_DIR, fn), 'r', encoding='utf-8') as f:
                        _ziwei_sessions[sid] = json.load(f)
                except Exception:
                    pass
        print(f"[启动] 已恢复 {len(_ziwei_sessions)} 个紫微会话")
    except Exception as e:
        print(f"[启动] 恢复会话失败: {e}")



def _save_session_to_disk(sid):
    """保存单个会话到磁盘"""
    try:
        if not os.path.exists(_SESSIONS_DIR):
            os.makedirs(_SESSIONS_DIR)
        fp = os.path.join(_SESSIONS_DIR, f'{sid}.json')
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(_ziwei_sessions[sid], f, ensure_ascii=False)
    except Exception as e:
        print(f"[会话] 保存失败 {sid}: {e}")

# 会话由 create_app() 统一恢复，此处不重复调用


def _render_feedback_html(report: dict) -> str:
    """将聚合报告渲染为简单 HTML"""
    ts = report.get("generated_at", "")
    total = report.get("total_samples", 0)
    overall = report.get("overall_accuracy", 0)
    by_signal = report.get("by_signal", {})
    by_domain = report.get("by_domain", {})
    common_errors = report.get("common_errors", [])
    fp_rate = report.get("false_positive_rate", 0)
    fn_rate = report.get("false_negative_rate", 0)
    prev = report.get("previous_report", {})



@ziwei_bp.route("/paipan", methods=["POST"])
def api_ziwei_paipan():
    """紫微斗数排盘计算"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    required = ["year", "month", "day", "hour", "gender"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"缺少参数: {field}"}), 400

    try:
        year = int(data["year"])
        month = int(data["month"])
        day = int(data["day"])
        hour = int(data["hour"])
        minute = int(data.get("minute", 0))
        gender = data["gender"]
        is_lunar = data.get("is_lunar", False)

        if gender not in ("男", "女"):
            return jsonify({"error": "性别必须为 '男' 或 '女'"}), 400
        if not (1 <= month <= 12):
            return jsonify({"error": "月份范围 1-12"}), 400
        if not (1 <= day <= 31):
            return jsonify({"error": "日期范围 1-31"}), 400
        if not (0 <= hour <= 23):
            return jsonify({"error": "小时范围 0-23"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "参数格式错误"}), 400

    try:
        # 农历转公历
        if is_lunar:
            try:
                from zhdate import ZhDate
                lunar = ZhDate(year, month, day)
                solar = lunar.to_datetime()
                year, month, day = solar.year, solar.month, solar.day
            except Exception:
                pass  # 转不了就用原值（iztro-py 内部有 lunar 支持，这里先尝试）

        plate_data = ziwei_paipan(year, month, day, hour, minute, gender,
                                  is_lunar=False)  # 已转为公历
        input_info = {
            "birth_datetime": f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
            "gender": gender,
            "location": data.get("location", ""),
            "longitude": float(data.get("longitude", 120)),
        }
        result = ziwei_plate_to_dict(plate_data, input_info)
        result['patterns'] = plate_data.get('patterns', [])  # 格局判读
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"紫微排盘计算失败: {str(e)}"}), 500

@ziwei_bp.route("/horoscope", methods=["POST"])
def api_ziwei_horoscope():
    """紫微斗数流年盘"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    try:
        year = int(data["year"])
        month = int(data["month"])
        day = int(data["day"])
        hour = int(data["hour"])
        gender = data["gender"]
        target_year = int(data.get("target_year", 2025))
        is_lunar = data.get("is_lunar", False)
    except (ValueError, TypeError, KeyError) as e:
        return jsonify({"error": f"参数错误: {e}"}), 400

    try:
        result = get_horoscope(year, month, day, hour, gender, target_year, is_lunar)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"流年计算失败: {str(e)}"}), 500

@ziwei_bp.route("/analyze/yearly", methods=["POST"])
def api_ziwei_analyze_yearly():
    """紫微斗数流年聚焦解读 — 本命+大限+流年三层叠盘分析"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    ip = request.remote_addr or 'unknown'
    pw_err = check_password(ip, data)
    if pw_err:
        return jsonify({"error": pw_err, "need_password": True}), 403

    try:
        year = int(data["year"])
        month = int(data["month"])
        day = int(data["day"])
        hour = int(data["hour"])
        gender = data["gender"]
        target_year = int(data.get("target_year", 2025))
        is_lunar = data.get("is_lunar", False)
    except (ValueError, TypeError, KeyError) as e:
        return jsonify({"error": f"参数错误: {e}"}), 400

    user_id, tier = resolve_user_from_request(request)
    limit = get_rate_limit(tier, "ziwei_read") or 3
    if limit and not check_rate_limit(f"{ip}:ziwei_read", max_requests=limit, window_minutes=60, user_id=user_id):
        msg = (f"免费版每小时 {limit} 次。"
               f"<a href='#' onclick='document.getElementById(\"authModal\").style.display=\"flex\";return false'>升级 Pro</a> 解锁 20 次/时") if tier == "free" else "请求过于频繁，请稍后再试"
        return jsonify({"error": msg, "rate_limited": True, "tier": tier, "redirect_auth": tier == "free"}), 429

    # Pro 专属门槛：大限流年深度解读
    if tier == "free":
        return jsonify({
            "error": "大限流年深度解读是 Pro 专属功能，升级后解锁",
            "pro_required": True, "tier": tier,
        }), 403

    try:
        # 本命盘
        plate_data = ziwei_paipan(year, month, day, hour, 0, gender, is_lunar)
        plate_dict = ziwei_plate_to_dict(plate_data, {
            "birth_datetime": f"{year}-{month:02d}-{day:02d} {hour:02d}:00",
            "gender": gender,
        })

        # 流年盘
        horo = get_horoscope(year, month, day, hour, gender, target_year, is_lunar)

        # 构造聚焦prompt
        from analysis_service import _load_ziwei_system_prompt
        system_prompt = _load_ziwei_system_prompt()

        # 本命摘要（只取关键宫：命宫/夫妻/财帛/官禄/迁移/福德）
        key_palaces = ['命宮', '夫妻', '財帛', '官祿', '遷移', '福德']
        natal_summary = []
        for p in plate_dict.get('palaces', []):
            if p['name'] in key_palaces:
                stars = '、'.join(s['name'] if isinstance(s, dict) else s for s in p.get('major_stars', [])) or '空宫'
                muts = '、'.join(f"{m['star']}{m['mutagen']}" for m in p.get('mutagens', []))
                natal_summary.append(f"{p['name']}({p['dizhi']}): {stars}" + (f" [{muts}]" if muts else ""))

        # 生年四化
        ym = plate_dict.get('year_mutagens', [])
        sihua_str = ' · '.join(f"{m['star']}{m['mutagen']}({m['palace']})" for m in ym)

        # 格局
        patterns = plate_dict.get('patterns', [])
        pattern_str = ' · '.join(p['name'] for p in patterns) if patterns else '无特殊格局'

        # ── 大限十年全景 + 流年三年（Pro 深度注入，引擎已算好禁止自行推算） ──
        GAN_SIHUA = {
            '甲': {'化禄': '廉贞', '化权': '破军', '化科': '武曲', '化忌': '太阳'},
            '乙': {'化禄': '天机', '化权': '天梁', '化科': '紫微', '化忌': '太阴'},
            '丙': {'化禄': '天同', '化权': '天机', '化科': '文昌', '化忌': '廉贞'},
            '丁': {'化禄': '太阴', '化权': '天同', '化科': '天机', '化忌': '巨门'},
            '戊': {'化禄': '贪狼', '化权': '太阴', '化科': '右弼', '化忌': '天机'},
            '己': {'化禄': '武曲', '化权': '贪狼', '化科': '天梁', '化忌': '文曲'},
            '庚': {'化禄': '太阳', '化权': '武曲', '化科': '太阴', '化忌': '天同'},
            '辛': {'化禄': '巨门', '化权': '太阳', '化科': '文曲', '化忌': '文昌'},
            '壬': {'化禄': '天梁', '化权': '紫微', '化科': '左辅', '化忌': '武曲'},
            '癸': {'化禄': '破军', '化权': '巨门', '化科': '太阴', '化忌': '贪狼'},
        }
        GAN = '甲乙丙丁戊己庚辛壬癸'
        ZHI = '子丑寅卯辰巳午未申酉戌亥'
        import datetime as _dt
        now_year = _dt.date.today().year
        birth_str = plate_dict.get('input', {}).get('birth_datetime', '')
        birth_year = int(birth_str[:4]) if birth_str and birth_str[:4].isdigit() else 0
        current_age = now_year - birth_year if birth_year else 0

        decadal_rows = []
        current_dec = None
        for pal in plate_dict.get('palaces', []):
            dz = pal.get('decadal_dizhi', '')
            gan = dz[0] if dz and len(dz) >= 1 else ''
            fly = GAN_SIHUA.get(gan, {})
            decadal_rows.append(f"| {pal['name']} | {dz or '—'} | {fly.get('化禄','—')} | {fly.get('化权','—')} | {fly.get('化科','—')} | {fly.get('化忌','—')} |")
            dr = pal.get('decadal_range', '')
            if dr and '-' in dr and current_age > 0:
                try:
                    lo, hi = dr.split('-')
                    if int(lo) <= current_age <= int(hi):
                        current_dec = pal
                except ValueError:
                    pass
        decadal_extra = ''
        if current_dec:
            cd_dz = current_dec.get('decadal_dizhi', '?')
            cd_fly = GAN_SIHUA.get(cd_dz[0], {}) if cd_dz else {}
            decadal_extra = (f"当前 {current_age} 岁，正行 **{current_dec['name']}** 大限（{current_dec.get('decadal_range','')}），"
                             f"大限四化：{'、'.join(f'{mu}→{star}' for mu, star in cd_fly.items())}")
            for mu, star in cd_fly.items():
                for pal in plate_dict.get('palaces', []):
                    hit = False
                    for s in pal.get('major_stars', []) + pal.get('minor_stars', []):
                        sn = s['name'] if isinstance(s, dict) else s
                        if sn == star:
                            decadal_extra += f"；{mu} {star} 在 {pal['name']} 宫"
                            hit = True
                            break
                    if hit:
                        break

        liunian_rows = []
        for offset, label in [(-1, f'{now_year-1}年'), (0, f'{now_year}年（当前）'), (1, f'{now_year+1}年')]:
            yg = GAN[(now_year + offset - 4) % 10]
            yz = ZHI[(now_year + offset - 4) % 12]
            yf = GAN_SIHUA.get(yg, {})
            liunian_rows.append(f"| {label} | {yg}{yz} | {'、'.join(f'{mu}→{star}' for mu, star in yf.items())} |")

        # 流年聚焦
        liuyao = horo.get('liuyao', {})
        liuyao_str = ' · '.join(f"{k}→{v}" for k, v in liuyao.items()) if liuyao else '无'

        user_msg = f"""请进行紫微斗数流年聚焦解读。结合本命盘、大限盘和流年盘三层信息，重点分析{target_year}年的运势。

## 本命盘关键宫位
{chr(10).join(natal_summary)}

## 生年四化
{sihua_str}

## 格局
{pattern_str}

## 当前大限
干支: {horo['decadal_gz']}
落宫: {horo['decadal_palace']}

## 大限十年全景（深度）
| 宫位 | 大限干支 | 化禄 | 化权 | 化科 | 化忌 |
|------|----------|------|------|------|------|
{chr(10).join(decadal_rows)}
{decadal_extra}

## 流年三年
| 年份 | 干支 | 流年四化 |
|------|------|----------|
{chr(10).join(liunian_rows)}

## {target_year}年流年
干支: {horo['yearly_gz']}
流年落宫: {horo['yearly_palace']}
流年四化: {'、'.join(horo['yearly_mutagens']) if horo['yearly_mutagens'] else '无'}
流曜分布: {liuyao_str}

## 解读要求
1. 先分析当前大限的主题（本命盘落宫+大限四化叠加效应）
2. 再聚焦{target_year}年流年重点（流年落宫+流年四化+流曜）
3. 指出今年需要重点关注的领域（哪些本命宫被激活）
4. 语气亲切有主见，控制在300字以内
5. 给出1-2条具体建议"""

        from analysis_service import _call_api
        result = _call_api(system_prompt, [{"role": "user", "content": user_msg}],
                          max_tokens=8192, temperature=0.5, timeout=90)

        if result["success"]:
            return jsonify({
                "success": True,
                "analysis": result["text"],
                "model": result.get("model", ""),
                "usage": result.get("usage", {}),
            })
        else:
            return jsonify({"success": False, "error": result["error"]}), 500

    except Exception as e:
        return jsonify({"error": f"流年分析失败: {str(e)}"}), 500

@ziwei_bp.route("/analyze", methods=["POST"])
def api_ziwei_analyze():
    """紫微斗数 Agent 深度分析"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    ip = request.remote_addr or 'unknown'
    pw_err = check_password(ip, data)
    if pw_err:
        return jsonify({"error": pw_err, "need_password": True}), 403

    if "plate" not in data:
        return jsonify({"error": "缺少参数: plate"}), 400

    plate_dict = data["plate"]
    bazi_ref = _compute_bazi_ref(plate_dict)

    # 验盘模式
    import datetime as _dt
    known_events = data.get("known_events", None)
    verified_events = data.get("verified_events", None)
    if known_events or data.get("verification_mode"):
        plate_dict["_verification_mode"] = True
        plate_dict["_current_year"] = _dt.date.today().year
        plate_dict["_current_age"] = plate_dict["_current_year"] - int(plate_dict.get("birth_year", 0))
        if known_events:
            plate_dict["_known_events"] = known_events
        if verified_events:
            plate_dict["_verified_events"] = verified_events

    # 缓存检查
    cache_key = _make_ziwei_cache_key(plate_dict)
    cached = _cache_get(cache_key)
    if cached:
        return jsonify({**cached, "cached": True})

    user_id2, tier2 = resolve_user_from_request(request)
    limit2 = get_rate_limit(tier2, "ziwei_read") or 3
    if limit2 and not check_rate_limit(f"{ip}:ziwei_read", max_requests=limit2, window_minutes=60, user_id=user_id2):
        msg = (f"免费版每小时 {limit2} 次。"
               f"<a href='#' onclick='document.getElementById(\"authModal\").style.display=\"flex\";return false'>升级 Pro</a> 解锁 20 次/时") if tier2 == "free" else "请求过于频繁，请稍后再试"
        return jsonify({"error": msg, "rate_limited": True, "tier": tier2, "redirect_auth": tier2 == "free"}), 429

    try:
        from analysis_service import analyze_ziwei
        result = analyze_ziwei(plate_dict, timeout=600, bazi_ref=bazi_ref)
    except Exception as e:
        return jsonify({"success": False, "error": f"分析异常: {str(e)}"}), 500

    if result["success"]:
        response_data = {
            "success": True,
            "analysis": result["analysis"],
            "model": result.get("model", ""),
            "usage": result.get("usage", {}),
        }
        if result.get("verification"):
            response_data["verification"] = result["verification"]
        if cache_key:
            _cache_set(cache_key, response_data)
        return jsonify(response_data)
    else:
        return jsonify({"success": False, "error": result["error"]}), 500

@ziwei_bp.route("/analyze/stream", methods=["POST"])
def api_ziwei_analyze_stream():
    """紫微斗数 SSE 流式解读"""
    try: data = request.get_json(force=True)
    except Exception: return jsonify({"error": "请求数据格式错误"}), 400

    ip = request.remote_addr or 'unknown'
    pw_err = check_password(ip, data)
    if pw_err: return jsonify({"error": pw_err, "need_password": True}), 403

    if "plate" not in data: return jsonify({"error": "缺少 plate"}), 400
    plate_dict = data["plate"]
    bazi_ref = _compute_bazi_ref(plate_dict)

    user_id3, tier3 = resolve_user_from_request(request)
    limit3 = get_rate_limit(tier3, "ziwei_read") or 3
    if limit3 and not check_rate_limit(f"{ip}:ziwei_read", max_requests=limit3, window_minutes=60, user_id=user_id3):
        msg = (f"免费版每小时 {limit3} 次。"
               f"升级 Pro 解锁 20 次/时") if tier3 == "free" else "请求过于频繁（{limit3}次/时）"
        return jsonify({"error": msg, "rate_limited": True, "tier": tier3, "redirect_auth": tier3 == "free"}), 429

    from flask import Response
    from analysis_service import _load_ziwei_system_prompt, _build_ziwei_user_message, _call_api_stream

    def generate():
        sp = _load_ziwei_system_prompt()
        um = _build_ziwei_user_message(plate_dict, bazi_ref=bazi_ref)
        full_parts = []
        for chunk in _call_api_stream(sp, [{"role": "user", "content": um}], 32768, 0.7, 600):
            full_parts.append(chunk)
            yield chunk
        # 流结束：机器校验（加强审查层）— 提取解读文本中的盘面引用 vs 引擎盘面
        try:
            text = ''
            for c in full_parts:
                if c.startswith('data: '):
                    try:
                        evt = json.loads(c[6:].strip())
                        if evt.get('type') == 'content_block_delta' and evt.get('delta', {}).get('text'):
                            text += evt['delta']['text']
                    except Exception:
                        pass
            from services.ziwei_analysis import verify_interpretation_against_plate
            verdict = verify_interpretation_against_plate(text, plate_dict)
            if verdict.get('issues') or verdict.get('unverified'):
                yield 'data: ' + json.dumps({'type': 'interpretation_issues', 'verdict': verdict}, ensure_ascii=False) + '\n\n'
                # 条件性 Reviewer（2026-08-04 加，MDPI 研究背书：多数幻觉前两轮迭代解决，只复核一次不循环）：
                # 校验逮到不一致才触发一次 LLM 复核，输出修正清单；正常输出零额外开销
                if verdict.get('issues'):
                    try:
                        from services.llm_client import _call_api
                        issue_str = '\n'.join(
                            f"- {i.get('type')}: 报告写 {i.get('found') or i.get('found_palace') or i.get('star')}，引擎应为 {i.get('expected')}"
                            for i in verdict['issues'])
                        corr = _call_api(
                            '你是紫微斗数盘面审查员。以下解读报告中的盘面引用与引擎排盘不一致，引擎盘面为唯一正确依据。请逐条给出修正说明，格式"原引用 → 正确值（原因）"。只输出修正清单，不重写报告。',
                            [{'role': 'user', 'content': f'不一致清单：\n{issue_str}\n\n解读原文（节选）：\n{text[:2000]}'}],
                            max_tokens=1024, temperature=0.3, timeout=60)
                        if corr.get('success') and corr.get('text'):
                            yield 'data: ' + json.dumps({'type': 'interpretation_correction', 'correction': corr['text']}, ensure_ascii=False) + '\n\n'
                    except Exception:
                        pass
                # 样本积累（2026-08-04 加）：issues 落库，供高频错误模式校准（数据驱动防错）
                try:
                    import os as _os, datetime as _dt
                    _issue_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                                               'feedback', 'ziwei_issues')
                    _os.makedirs(_issue_dir, exist_ok=True)
                    _fn = _dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json'
                    # 每条 issue 预留 _review 标记（误报监控用：user_ignored / confirmed_false_positive / confirmed_true）
                    _issues_out = []
                    for _it in verdict.get('issues', []):
                        _it2 = dict(_it)
                        _it2['_review'] = None
                        _issues_out.append(_it2)
                    with open(_os.path.join(_issue_dir, _fn), 'w', encoding='utf-8') as _f:
                        json.dump({
                            'ts': _dt.datetime.now().isoformat(timespec='seconds'),
                            'birth': (plate_dict.get('input') or {}).get('birth_datetime', ''),
                            'gender': (plate_dict.get('input') or {}).get('gender', ''),
                            'issues': _issues_out,
                            'unverified': verdict.get('unverified', []),
                            'text_len': len(text),
                        }, _f, ensure_ascii=False, indent=1)
                except Exception:
                    pass
        except Exception:
            pass

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@ziwei_bp.route("/analyze/continue", methods=["POST"])
def api_ziwei_analyze_continue():
    """紫微斗数多轮对话续接"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    ip = request.remote_addr or 'unknown'
    pw_err = check_password(ip, data)
    if pw_err:
        return jsonify({"error": pw_err, "need_password": True}), 403

    messages = data.get("messages", [])
    reply = data.get("reply", "")
    if not messages or not reply:
        return jsonify({"error": "缺少 messages 或 reply"}), 400

    from analysis_service import continue_ziwei_analysis
    try:
        result = continue_ziwei_analysis(messages, reply, timeout=300)
    except Exception as e:
        return jsonify({"success": False, "error": f"分析异常: {str(e)}"}), 500

    if result["success"]:
        return jsonify({"success": True, "analysis": result["analysis"]})
    else:
        return jsonify({"success": False, "error": result["error"]}), 500


# ============================================================
# 紫微会话管理
# ============================================================
import uuid as _uuid
_ziwei_sessions = {}  # {session_id: {id, title, messages, plate_data, plate_summary, created_at, user_id}}

def _get_auth_user():
    """Extract user_id from Authorization Bearer token, or None."""
    import re as _re
    header = request.headers.get("Authorization", "")
    m = _re.match(r"^Bearer\s+(.+)$", header)
    if not m:
        return None
    from models.user import verify_token
    payload = verify_token(m.group(1))
    return payload["user_id"] if payload else None

@ziwei_bp.route("/sessions", methods=["GET", "POST"])
def api_ziwei_sessions():
    """会话列表 / 创建"""
    user_id = _get_auth_user()
    if request.method == "GET":
        device_fp = (request.headers.get("X-Device-Id") or "").strip() or None
        items = []
        for s in _ziwei_sessions.values():
            if not _session_visible_to(s, user_id, device_fp):
                continue  # 只可见自己的会话：已绑定看 user_id，匿名看设备指纹
            items.append({"id": s["id"], "title": s.get("title",""), "plate_summary": s.get("plate_summary",""),
                         "created_at": s.get("created_at",""), "message_count": len(s.get("messages",[]))})
        return jsonify(sorted(items, key=lambda x: x["created_at"], reverse=True))

    data = request.get_json(force=True) if request.method == "POST" else {}
    device_fp = (request.headers.get("X-Device-Id") or "").strip() or None
    sid = str(_uuid.uuid4())[:8]
    _ziwei_sessions[sid] = {
        "id": sid, "title": data.get("title", "新会话"),
        "messages": data.get("messages", []),
        "plate_data": data.get("plate_data", {}),
        "plate_summary": data.get("plate_summary", ""),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "user_id": user_id,
        "device_fingerprint": device_fp,
    }
    _save_session_to_disk(sid)
    return jsonify(_ziwei_sessions[sid])

@ziwei_bp.route("/sessions/<sid>", methods=["GET", "PUT", "PATCH", "DELETE"])
def api_ziwei_session(sid):
    """获取 / 更新 / 追加 / 删除单个会话（仅归属者可见可改）"""
    s = _ziwei_sessions.get(sid)
    if not s:
        return jsonify({"error": "not found"}), 404
    user_id = _get_auth_user()
    device_fp = (request.headers.get("X-Device-Id") or "").strip() or None
    if not _session_visible_to(s, user_id, device_fp):
        return jsonify({"error": "not found"}), 404  # 非归属者一律 404，不暴露存在性
    if request.method == "GET":
        return jsonify(s)
    if request.method == "PUT":
        data = request.get_json(force=True)
        if "title" in data: _ziwei_sessions[sid]["title"] = data["title"]
        if "messages" in data: _ziwei_sessions[sid]["messages"] = data["messages"]
        if "plate_data" in data: _ziwei_sessions[sid]["plate_data"] = data["plate_data"]
        _save_session_to_disk(sid)
        return jsonify({"ok": True})
    if request.method == "PATCH":
        """追加 messages（用于流式完成后保存）"""
        data = request.get_json(force=True)
        if "messages" in data:
            _ziwei_sessions[sid]["messages"] = data["messages"]
        _save_session_to_disk(sid)
        return jsonify({"ok": True})
    if request.method == "DELETE":
        del _ziwei_sessions[sid]
        fp = os.path.join(_SESSIONS_DIR, f'{sid}.json')
        if os.path.exists(fp):
            os.remove(fp)
        return jsonify({"ok": True})

def _session_visible_to(s: dict, user_id: str | None, device_fp: str | None) -> bool:
    """会话可见性：已绑定看 user_id 归属；匿名会话看设备指纹归属。
    任何人只能看到自己的会话，杜绝跨用户泄露。"""
    owner = s.get("user_id")
    if owner:
        return bool(user_id) and owner == user_id
    # 匿名会话：仅设备指纹匹配可见（未登录用户按设备隔离，登录用户可看自己设备的未认领会话）
    return bool(device_fp) and s.get("device_fingerprint") == device_fp


# ═══ 会话归属迁移 ═══
@ziwei_bp.route("/sessions/claimable", methods=["GET"])
def api_ziwei_session_claimable():
    """查询可认领的匿名会话。Header: Authorization Bearer + X-Device-Id"""
    user_id = _get_auth_user()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    device_fp = (request.headers.get("X-Device-Id") or "").strip() or None
    
    matched = 0
    for s in _ziwei_sessions.values():
        if s.get("user_id"):
            continue  # 已归属
        if device_fp and s.get("device_fingerprint") == device_fp:
            matched += 1
    # 注意：不列 orphan_list 详情，旧无指纹会话不向任何用户暴露，防跨用户认领
    return jsonify({"matched": matched, "orphans": 0, "orphan_list": []})


@ziwei_bp.route("/sessions/migrate", methods=["POST"])
def api_ziwei_session_migrate():
    """执行会话归属迁移。"""
    user_id = _get_auth_user()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    device_fp = (request.headers.get("X-Device-Id") or "").strip() or None
    data = request.get_json(silent=True) or {}
    migrate_matched = data.get("migrate_matched", True)
    orphan_ids = data.get("orphan_ids", [])
    if not isinstance(orphan_ids, list):
        orphan_ids = []

    count = 0
    for s in _ziwei_sessions.values():
        if s.get("user_id"):
            continue
        matched = device_fp and migrate_matched and s.get("device_fingerprint") == device_fp
        orphan_match = s["id"] in orphan_ids
        if matched or orphan_match:
            s["user_id"] = user_id
            _save_session_to_disk(s["id"])
            count += 1
    return jsonify({"migrated": count})


# ═══ 分享快照（安全分享：独立 share_id，原会话 ID 不外传） ═══
_SHARE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'share')


def _save_share(share: dict) -> None:
    os.makedirs(_SHARE_DIR, exist_ok=True)
    fp = os.path.join(_SHARE_DIR, f"{share['share_id']}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(share, f, ensure_ascii=False)


def _load_share(share_id: str) -> dict | None:
    fp = os.path.join(_SHARE_DIR, f"{share_id}.json")
    if not os.path.exists(fp):
        return None
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


@ziwei_bp.route("/share", methods=["POST"])
def api_ziwei_create_share():
    """创建分享快照：登录用户分享自己拥有的会话（含盘面+解读快照）。
    分享链接公开只读，原会话 ID 永不外传，分享者不能操作原会话。"""
    user_id = _get_auth_user()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    from models.user import get_user_by_id
    _u = get_user_by_id(user_id)
    _sharer = "一位用户"
    if _u and _u.get("email"):
        _sharer = _u["email"].split("@")[0][:12] or "一位用户"
    data = request.get_json(silent=True) or {}
    sid = (data.get("sid") or "").strip()
    s = _ziwei_sessions.get(sid)
    if not s or s.get("user_id") != user_id:
        return jsonify({"error": "not found"}), 404
    share_id = str(_uuid.uuid4())
    share = {
        "share_id": share_id,
        "sid": sid,  # 内部引用，响应不返回
        "title": s.get("title", "命盘分享"),
        "plate_summary": s.get("plate_summary", ""),
        "plate_data": s.get("plate_data", {}),
        "messages": s.get("messages", []),
        "sharer": _sharer,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "user_id": user_id,
    }
    _save_share(share)
    return jsonify({"share_id": share_id, "url": f"/ziwei/report/share/{share_id}"})


@ziwei_bp.route("/share/<share_id>", methods=["GET"])
def api_ziwei_get_share(share_id):
    """读取分享快照（公开只读）。只返回分享时刻的盘面与解读，不含任何用户身份信息。"""
    share = _load_share(share_id)
    if not share:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "id": share["share_id"],
        "title": share.get("title", ""),
        "plate_summary": share.get("plate_summary", ""),
        "plate_data": share.get("plate_data", {}),
        "messages": share.get("messages", []),
        "sharer": share.get("sharer", ""),
        "created_at": share.get("created_at", ""),
    })


# ═══ 验盘反馈保存 ═══
# 与 scripts/evaluate_ziwei_verify.py 的 FEEDBACK_DIR 保持一致（项目根/feedback/ziwei），勿改回 routes/ 下
_FEEDBACK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'feedback', 'ziwei')
# 报告目录：与 scripts/evaluate_ziwei_verify.py 的 REPORTS_DIR 保持一致（项目根/data/reports），与反馈记录目录分离
_REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'reports')

@ziwei_bp.route("/verify", methods=["POST"])
def api_ziwei_verify():
    """保存验盘反馈"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    sid = data.get("session_id", "unknown")
    plate = data.get("plate", {})
    predictions = data.get("predictions", [])
    source = data.get("source", "verification_triggered")
    device_id = (data.get("device_id") or "").strip()
    if len(device_id) > 64:
        device_id = device_id[:64]

    if not predictions:
        return jsonify({"error": "缺少 predictions"}), 400

    # 盘指纹
    fp = {"sihua": [], "ming_stars": [], "laiyin": "", "nian_gan": ""}
    if plate:
        palaces = plate.get("palaces", [])
        info = plate.get("input", {})
        bs = info.get("birth_datetime", "")
        fp["nian_gan"] = bs[:4] if bs and bs[0].isdigit() else ""
        for pal in palaces:
            tags = pal.get("tags", [])
            if "命宫" in tags:
                fp["ming_stars"] = [s.get("name", "") if isinstance(s, dict) else s for s in pal.get("major_stars", [])]
            if "来因宫" in tags:
                fp["laiyin"] = pal.get("name", "")
        for m in plate.get("year_mutagens", []):
            fp["sihua"].append(m["star"] + "/" + m["mutagen"] + "/" + m["palace"])

    total = len(predictions)
    correct = sum(1 for p in predictions if p.get("user_label") == "correct")
    wrong = sum(1 for p in predictions if p.get("user_label") == "wrong")
    partial = sum(1 for p in predictions if p.get("user_label") == "partially_correct")

    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_id": sid,
        "device_id": device_id or None,
        "source": source,
        "fingerprint": fp,
        "predictions": predictions,
        "summary": {
            "total": total, "correct": correct, "wrong": wrong,
            "partially_correct": partial,
            "hit_rate": round((correct + partial * 0.5) / total, 3) if total > 0 else 0,
        },
    }

    try:
        if not os.path.exists(_FEEDBACK_DIR):
            os.makedirs(_FEEDBACK_DIR)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = ts + "_" + sid[:6] + ".json"
        fp_path = os.path.join(_FEEDBACK_DIR, fn)
        with open(fp_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True, "file": fn, "summary": record["summary"]})
    except Exception as e:
        return jsonify({"error": "保存失败: " + str(e)}), 500

@ziwei_bp.route("/feedback/report")
def api_ziwei_feedback_report():
    """验盘反馈聚合报告（仅 ADMIN_TOKEN 可访问）"""
    # 内联 admin 鉴权（check_admin 从未定义，原调用为 NameError 500）：Bearer 或 X-Admin-Token 比较 ADMIN_TOKEN，不匹配 404 伪装
    _ah = request.headers.get("Authorization", "")
    if _ah.startswith("Bearer "):
        _adm = _ah[7:]
    else:
        _adm = request.headers.get("X-Admin-Token", "")
    if not ADMIN_TOKEN or _adm != ADMIN_TOKEN:
        return "Not Found", 404
    cache_path = os.path.join(_REPORTS_DIR, "report_cache.json")
    if not os.path.exists(cache_path):
        return jsonify({"error": "报告尚未生成，请先运行 scripts/evaluate_ziwei_verify.py（默认输出 data/reports/report_cache.json）"}), 404
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except Exception as e:
        return jsonify({"error": "读取报告失败: " + str(e)}), 500

    # 可选 HTML 渲染（?format=html）
    fmt = request.args.get("format", "json")
    if fmt == "html":
        return _render_feedback_html(report)
    return jsonify(report)

