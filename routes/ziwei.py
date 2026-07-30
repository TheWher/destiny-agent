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

    if not check_rate_limit(ip, max_requests=3, window_minutes=60):
        return jsonify({"error": "请求过于频繁，请稍后再试"}), 429

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

    if not check_rate_limit(ip, max_requests=3, window_minutes=60):
        return jsonify({"error": "请求过于频繁，请稍后再试（每小时限 3 次）"}), 429

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

    if not check_rate_limit(ip, max_requests=3, window_minutes=60):
        return jsonify({"error": "请求过于频繁（3次/时）"}), 429

    from flask import Response
    from analysis_service import _load_ziwei_system_prompt, _build_ziwei_user_message, _call_api_stream

    def generate():
        sp = _load_ziwei_system_prompt()
        um = _build_ziwei_user_message(plate_dict, bazi_ref=bazi_ref)
        for chunk in _call_api_stream(sp, [{"role": "user", "content": um}], 32768, 0.7, 600):
            yield chunk

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
_ziwei_sessions = {}  # {session_id: {id, title, messages, plate_data, plate_summary, created_at}}

@ziwei_bp.route("/sessions", methods=["GET", "POST"])
def api_ziwei_sessions():
    """会话列表 / 创建"""
    if request.method == "GET":
        items = [{"id": s["id"], "title": s.get("title",""), "plate_summary": s.get("plate_summary",""), "created_at": s.get("created_at",""), "message_count": len(s.get("messages",[]))} for s in _ziwei_sessions.values()]
        return jsonify(sorted(items, key=lambda x: x["created_at"], reverse=True))

    data = request.get_json(force=True) if request.method == "POST" else {}
    sid = str(_uuid.uuid4())[:8]
    _ziwei_sessions[sid] = {
        "id": sid, "title": data.get("title", "新会话"),
        "messages": data.get("messages", []),
        "plate_data": data.get("plate_data", {}),
        "plate_summary": data.get("plate_summary", ""),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save_session_to_disk(sid)
    return jsonify(_ziwei_sessions[sid])

@ziwei_bp.route("/sessions/<sid>", methods=["GET", "PUT", "PATCH", "DELETE"])
def api_ziwei_session(sid):
    """获取 / 更新 / 追加 / 删除单个会话"""
    if request.method == "GET":
        s = _ziwei_sessions.get(sid); return jsonify(s) if s else (jsonify({"error": "not found"}), 404)
    if request.method == "PUT":
        if sid not in _ziwei_sessions: return jsonify({"error": "not found"}), 404
        data = request.get_json(force=True)
        if "title" in data: _ziwei_sessions[sid]["title"] = data["title"]
        if "messages" in data: _ziwei_sessions[sid]["messages"] = data["messages"]
        if "plate_data" in data: _ziwei_sessions[sid]["plate_data"] = data["plate_data"]
        _save_session_to_disk(sid)
        return jsonify({"ok": True})
    if request.method == "PATCH":
        """追加 messages（用于流式完成后保存）"""
        if sid not in _ziwei_sessions: return jsonify({"error": "not found"}), 404
        data = request.get_json(force=True)
        if "messages" in data:
            _ziwei_sessions[sid]["messages"] = data["messages"]
        _save_session_to_disk(sid)
        return jsonify({"ok": True})
    if request.method == "DELETE":
        if sid in _ziwei_sessions:
            del _ziwei_sessions[sid]
            # 删除磁盘文件
            fp = os.path.join(_SESSIONS_DIR, f'{sid}.json')
            if os.path.exists(fp):
                os.remove(fp)
        return jsonify({"ok": True})

# ═══ 验盘反馈保存 ═══
_FEEDBACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feedback', 'ziwei')

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
    if not check_admin(request):
        return "Not Found", 404
    cache_path = os.path.join(_FEEDBACK_DIR, "report_cache.json")
    if not os.path.exists(cache_path):
        return jsonify({"error": "报告尚未生成，请先运行 scripts/evaluate_ziwei_verify.py --output"}), 404
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

