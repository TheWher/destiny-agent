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

from bazi_calculator import paipan
from city_coords import search_city
from utils.auth import check_password, check_rate_limit, check_conv_rate_limit, check_global_ip_limit, WEB_PASSWORD, ADMIN_TOKEN
from utils.tier import resolve_user_from_request, get_rate_limit
from utils.cache import _make_cache_key, _cache_get, _make_ziwei_cache_key, _cache_set
from utils.feedback import save_feedback_log
from utils.plate import plate_to_dict, SHICHEN_NAMES

bazi_bp = Blueprint("bazi", __name__, url_prefix="/api")

@bazi_bp.route("/paipan", methods=["POST"])
def api_paipan():
    """排盘计算"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    # 参数提取与校验
    required = ["year", "month", "day", "hour", "gender", "longitude"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"缺少参数: {field}"}), 400

    try:
        year = int(data["year"])
        month = int(data["month"])
        day = int(data["day"])
        hour = int(data["hour"])
        minute = int(data.get("minute", 0))
        longitude = float(data["longitude"])
        gender = data["gender"]
        location = data.get("location", "")
        is_lunar = data.get("is_lunar", False)

        # 农历→公历转换
        if is_lunar:
            try:
                from zhdate import ZhDate
                lunar = ZhDate(year, month, day)
                solar = lunar.to_datetime()
                year, month, day = solar.year, solar.month, solar.day
            except ImportError:
                return jsonify({"error": "农历转换需要 zhdate 库，请用公历输入"}), 400

        # 是否启用真太阳时校正（由 paipan 内部处理，不再手动调 hour）
        use_solar = bool(data.get("solar_correction", 0))

        if gender not in ("男", "女"):
            return jsonify({"error": "性别必须为 '男' 或 '女'"}), 400
        if not (1 <= month <= 12):
            return jsonify({"error": "月份范围 1-12"}), 400
        if not (1 <= day <= 31):
            return jsonify({"error": "日期范围 1-31"}), 400
        if not (0 <= hour <= 23):
            return jsonify({"error": "小时范围 0-23"}), 400
        if not (0 <= minute <= 59):
            return jsonify({"error": "分钟范围 0-59"}), 400

    except (ValueError, TypeError):
        return jsonify({"error": "参数格式错误"}), 400

    try:
        plate = paipan(year, month, day, hour, minute, gender, longitude, location,
                       apply_solar_correction=use_solar)
        result = plate_to_dict(plate)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"排盘计算失败: {str(e)}"}), 500

@bazi_bp.route("/analyze", methods=["POST"])
def api_analyze():
    """Agent 深度分析：调用 LLM 对命盘进行 9 级递进分析（调候→格局→旺衰→病药→十神→刑冲合害→神煞→大运流年→四维交叉验证）"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    # 密码校验（优先检查，避免无效请求消耗 token）
    ip = request.remote_addr or 'unknown'
    pw_err = check_password(ip, data)
    if pw_err:
        return jsonify({"error": pw_err, "need_password": True}), 403

    # 支持两种传参方式：直接传排盘字典，或传出生参数
    if "plate" in data:
        plate_dict = data["plate"]
    else:
        # 传出生参数，先排盘
        required = ["year", "month", "day", "hour", "gender", "longitude"]
        for field in required:
            if field not in data:
                return jsonify({"error": f"缺少参数: {field}"}), 400

        try:
            year = int(data["year"])
            month = int(data["month"])
            day = int(data["day"])
            hour = int(data["hour"])
            minute = int(data.get("minute", 0))
            longitude = float(data["longitude"])
            gender = data["gender"]
            location = data.get("location", "")
            if gender not in ("男", "女"):
                return jsonify({"error": "性别必须为 '男' 或 '女'"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "参数格式错误"}), 400

        try:
            plate = paipan(year, month, day, hour, minute, gender, longitude, location,
                           apply_solar_correction=bool(data.get("solar_correction", 0)))
            plate_dict = plate_to_dict(plate)
        except Exception as e:
            return jsonify({"error": f"排盘计算失败: {str(e)}"}), 500

    # 查缓存（缓存命中不消耗限流配额）
    cache_key = _make_cache_key(plate_dict)
    cached = _cache_get(cache_key)
    if cached:
        return jsonify({**cached, "cached": True})

    user_id, tier = resolve_user_from_request(request)
    limit = get_rate_limit(tier, "bazi_read") or 3
    if limit and not check_rate_limit(f"{ip}:bazi_read", max_requests=limit, window_minutes=60, user_id=user_id):
        msg = (f"免费版每小时 {limit} 次。"
               f"升级 Pro 解锁 20 次/时") if tier == "free" else "请求过于频繁，请稍后再试"
        return jsonify({"error": msg, "rate_limited": True, "tier": tier, "redirect_auth": tier == "free"}), 429

    # 调用 LLM 分析（使用惰性导入避免循环依赖）
    from analysis_service import analyze_bazi

    known_events = data.get("known_events") or []
    # 校验格式
    if known_events:
        known_events = [
            {"year": int(e.get("year", 0)), "desc": str(e.get("desc", "")).strip()}
            for e in known_events
            if e.get("year") and str(e.get("year", "")).isdigit()
        ]

    result = analyze_bazi(plate_dict, timeout=180, known_events=known_events)

    if result["success"]:
        # 保存反馈日志
        feedback_file = save_feedback_log(plate_dict, result.get("messages", []), ip=ip, turn_type="initial")
        response_data = {
            "success": True,
            "analysis": result["analysis"],
            "model": result.get("model", ""),
            "usage": result.get("usage", {}),
            "messages": result.get("messages", []),
            "feedback_file": feedback_file or "",
        }
        # 写入缓存（后续重试直接返回）
        if cache_key:
            _cache_set(cache_key, response_data)
        return jsonify(response_data)
    else:
        return jsonify({"success": False, "error": result["error"]}), 500

@bazi_bp.route("/analyze/stream", methods=["POST"])
def api_analyze_stream():
    """三通道 SSE 流式验盘：analysis(隐藏) → commentary(进度事件) → final(验盘结果)

    GPT-5.5 参考实现 — SSE 事件流推送分析进度，
    前端通过 EventSource 或 fetch + ReadableStream 消费。
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    ip = request.remote_addr or 'unknown'
    pw_err = check_password(ip, data)
    if pw_err:
        return jsonify({"error": pw_err, "need_password": True}), 403

    # 提取/计算 plate_dict
    if "plate" in data:
        plate_dict = data["plate"]
    else:
        required = ["year", "month", "day", "hour", "gender", "longitude"]
        for field in required:
            if field not in data:
                return jsonify({"error": f"缺少参数: {field}"}), 400
        try:
            year = int(data["year"]); month = int(data["month"]); day = int(data["day"])
            hour = int(data["hour"]); minute = int(data.get("minute", 0))
            longitude = float(data["longitude"]); gender = data["gender"]
            location = data.get("location", "")
            if gender not in ("男", "女"):
                return jsonify({"error": "性别必须为 '男' 或 '女'"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "参数格式错误"}), 400
        try:
            plate = paipan(year, month, day, hour, minute, gender, longitude, location,
                           apply_solar_correction=bool(data.get("solar_correction", 0)))
            plate_dict = plate_to_dict(plate)
        except Exception as e:
            return jsonify({"error": f"排盘计算失败: {str(e)}"}), 500

    # 查缓存（缓存命中直接返回，不流式）
    cache_key = _make_cache_key(plate_dict)
    cached = _cache_get(cache_key)
    if cached:
        return jsonify({**cached, "cached": True})

    user_id, tier = resolve_user_from_request(request)
    limit = get_rate_limit(tier, "bazi_read") or 3
    if limit and not check_rate_limit(f"{ip}:bazi_read", max_requests=limit, window_minutes=60, user_id=user_id):
        msg = (f"免费版每小时 {limit} 次。"
               f"升级 Pro 解锁 20 次/时") if tier == "free" else "请求过于频繁，请稍后再试"
        return jsonify({"error": msg, "rate_limited": True, "tier": tier, "redirect_auth": tier == "free"}), 429

    from three_channel import three_channel_analyze
    import json as _json

    # 收集所有 SSE 事件（generator 已 yield result 事件 + 进度事件）
    events = list(three_channel_analyze(plate_dict))

    # 提取 result 事件用于缓存+日志
    result_data = None
    for evt in events:
        for line in evt.strip().split("\n"):
            if line.startswith("data:") and '"event":"result"' in line:
                try:
                    result_data = _json.loads(line[5:].strip())
                except Exception:
                    pass

    if result_data and result_data.get("success"):
        msgs = result_data.get("messages", [])
        fb = save_feedback_log(plate_dict, msgs, ip=ip, turn_type="initial")
        result_data["feedback_file"] = fb or ""
        if cache_key:
            _cache_set(cache_key, result_data)

    from flask import Response
    return Response(
        "".join(events),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@bazi_bp.route("/analyze/stream/continue", methods=["POST"])
def api_analyze_stream_continue():
    """三通道 SSE 流式续接：analysis(隐藏推理) → commentary(进度) → final(13章报告)

    用户确认验盘后调用。比 /api/analyze/continue 多了：
    - 隐藏推理层（analysis channel 产出结构化决策，用户不可见）
    - SSE 进度事件（14 个分析阶段逐个推送）
    - 内部决策锚点注入（后续章节直接引用，不重复推理）
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    ip = request.remote_addr or 'unknown'
    pw_err = check_password(ip, data)
    if pw_err:
        return jsonify({"error": pw_err, "need_password": True}), 403

    user_id, tier = resolve_user_from_request(request)
    conv_limit = get_rate_limit(tier, "conv_message") or 30
    if conv_limit and not check_rate_limit(f"{ip}:conv_message", max_requests=conv_limit, window_minutes=60, user_id=user_id):
        msg = (f"免费版每小时 {conv_limit} 次。"
               f"升级 Pro 解锁 100 次/时") if tier == "free" else "请求过于频繁，请稍后再试"
        return jsonify({"error": msg, "rate_limited": True, "tier": tier, "redirect_auth": tier == "free"}), 429

    # 对话粒度限流 + IP 全局兜底
    conv_id = data.get("conversation_id", "")
    if conv_id:
        if not check_conv_rate_limit(ip, conv_id, max_requests=conv_limit, user_id=user_id):
            return jsonify({"error": "该对话请求过于频繁，请稍后再试"}), 429
        if not check_global_ip_limit(ip, max_requests=get_rate_limit(tier, "global_ip") or 100, user_id=user_id):
            return jsonify({"error": "全局请求过于频繁，请稍后再试"}), 429

    if "messages" not in data or "reply" not in data:
        return jsonify({"error": "缺少参数: messages 或 reply"}), 400

    from three_channel import three_channel_continue
    import json as _json

    # 收集所有 SSE 事件（generator 已 yield result 事件 + 进度事件）
    events = list(three_channel_continue(data["messages"], data["reply"]))

    # 提取 result 事件保存反馈日志
    result_data = None
    for evt in events:
        for line in evt.strip().split("\n"):
            if line.startswith("data:") and '"event":"result"' in line:
                try:
                    result_data = _json.loads(line[5:].strip())
                except Exception:
                    pass

    if result_data and result_data.get("success"):
        # 重建完整对话 messages
        full_msgs = list(data["messages"])
        full_msgs.append({"role": "user", "content": data["reply"]})
        full_msgs.append({"role": "assistant", "content": result_data.get("analysis", "")})
        # 从首条 user 消息提取排盘摘要
        plate_summary = {}
        for m in data["messages"]:
            if m.get("role") == "user" and "命盘数据" in m.get("content", ""):
                import re as _re
                m_ri = _re.search(r"日主[：:]\s*(\S+)", m["content"])
                m_g = _re.search(r"性别[：:]\s*(\S+)", m["content"])
                m_b = _re.search(r"公历[：:]\s*(.+?)(?:\n|$)", m["content"])
                plate_summary = {
                    "birth": m_b.group(1).strip() if m_b else "?",
                    "gender": m_g.group(1).strip() if m_g else "?",
                    "ri_zhu": m_ri.group(1).strip() if m_ri else "?",
                }
                break
        minimal_plate = {
            "input": {"birth_datetime": plate_summary.get("birth", "?"), "gender": plate_summary.get("gender", "?"), "location": ""},
            "ri_zhu": plate_summary.get("ri_zhu", "?"),
            "year_type": "",
            "pillars": {},
            "qiyun": {"age": "?"},
        }
        save_feedback_log(minimal_plate, full_msgs, ip=ip, turn_type="continue")

    from flask import Response
    return Response(
        "".join(events),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@bazi_bp.route("/analyze/continue", methods=["POST"])
def api_analyze_continue():
    """续接分析：将之前的对话 + 用户回复发给 Agent 继续批断"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    # 密码校验
    ip = request.remote_addr or 'unknown'
    pw_err = check_password(ip, data)
    if pw_err:
        return jsonify({"error": pw_err, "need_password": True}), 403

    user_id, tier = resolve_user_from_request(request)
    conv_limit = get_rate_limit(tier, "conv_message") or 30
    if conv_limit and not check_rate_limit(f"{ip}:conv_message", max_requests=conv_limit, window_minutes=60, user_id=user_id):
        msg = (f"免费版每小时 {conv_limit} 次。"
               f"升级 Pro 解锁 100 次/时") if tier == "free" else "请求过于频繁，请稍后再试"
        return jsonify({"error": msg, "rate_limited": True, "tier": tier, "redirect_auth": tier == "free"}), 429

    # 对话粒度限流 + IP 全局兜底
    conv_id = data.get("conversation_id", "")
    if conv_id:
        if not check_conv_rate_limit(ip, conv_id, max_requests=conv_limit, user_id=user_id):
            return jsonify({"error": "该对话请求过于频繁，请稍后再试"}), 429
        if not check_global_ip_limit(ip, max_requests=get_rate_limit(tier, "global_ip") or 100, user_id=user_id):
            return jsonify({"error": "全局请求过于频繁，请稍后再试"}), 429

    if "messages" not in data or "reply" not in data:
        return jsonify({"error": "缺少参数: messages 或 reply"}), 400

    from analysis_service import continue_analysis
    result = continue_analysis(data["messages"], data["reply"], timeout=480)

    if result["success"]:
        # 组装完整对话 + 保存反馈日志
        full_msgs = list(data["messages"])
        full_msgs.append({"role": "user", "content": data["reply"]})
        full_msgs.append({"role": "assistant", "content": result["analysis"]})
        # 从首条 user 消息提取排盘摘要（Markdown 格式）
        plate_summary = {}
        for m in data["messages"]:
            if m.get("role") == "user" and "命盘数据" in m.get("content", ""):
                # 提取日主
                import re as _re
                m_ri = _re.search(r"日主[：:]\s*(\S+)", m["content"])
                m_g = _re.search(r"性别[：:]\s*(\S+)", m["content"])
                m_b = _re.search(r"公历[：:]\s*(.+?)(?:\n|$)", m["content"])
                plate_summary = {
                    "birth": m_b.group(1).strip() if m_b else "?",
                    "gender": m_g.group(1).strip() if m_g else "?",
                    "ri_zhu": m_ri.group(1).strip() if m_ri else "?",
                }
                break
        # 用最小 plate_dict 来存日志
        minimal_plate = {
            "input": {"birth_datetime": plate_summary.get("birth", "?"), "gender": plate_summary.get("gender", "?"), "location": ""},
            "ri_zhu": plate_summary.get("ri_zhu", "?"),
            "year_type": "",
            "pillars": {},
            "qiyun": {"age": "?"},
        }
        save_feedback_log(minimal_plate, full_msgs, ip=ip, turn_type="continue")
        return jsonify({"success": True, "analysis": result["analysis"]})
    else:
        return jsonify({"success": False, "error": result["error"]}), 500


# ============================================================
# 验盘反馈 API
# ============================================================

@bazi_bp.route("/verify", methods=["POST"])
def api_verify():
    """保存验盘反馈：用户对 Agent 验证预测的确认/纠正标签。

    Request:
        {feedback_file: "20260615_034827_乙_8592.json",
         predictions: [{index: 0, label: "correct"|"wrong"|"partially_correct",
                        user_note: "实际是考上民办二本，发挥更好"}]}
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "请求数据格式错误"}), 400

    filename = data.get("feedback_file", "").strip()
    predictions = data.get("predictions", [])

    if not filename or not predictions:
        return jsonify({"error": "缺少参数: feedback_file 或 predictions"}), 400

    # 安全检查：防止路径穿越
    if "/" in filename or "\\" in filename or ".." in filename:
        return jsonify({"error": "无效的文件名"}), 400

    filepath = os.path.join(FEEDBACK_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "反馈日志文件不存在"}), 404

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            log = json.load(f)

        # 初始化 verification 字段
        if "verification" not in log:
            log["verification"] = {"predictions": [], "summary": {}}

        # 合并预测标签（去重，按 index 覆盖）
        existing_by_idx = {p["index"]: p for p in log["verification"]["predictions"]}
        for pred in predictions:
            existing_by_idx[pred["index"]] = {
                "index": pred["index"],
                "label": pred.get("label", "unlabeled"),
                "user_note": pred.get("user_note", ""),
                "verified_at": datetime.now().isoformat(timespec="seconds"),
            }
        log["verification"]["predictions"] = sorted(
            existing_by_idx.values(), key=lambda x: x["index"]
        )

        # 计算汇总
        labels = [p["label"] for p in log["verification"]["predictions"]]
        log["verification"]["summary"] = {
            "total": len(labels),
            "correct": labels.count("correct"),
            "wrong": labels.count("wrong"),
            "partially_correct": labels.count("partially_correct"),
            "hit_rate": round(
                (labels.count("correct") + labels.count("partially_correct") * 0.5)
                / max(len(labels), 1),
                2,
            ),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

        return jsonify({
            "success": True,
            "summary": log["verification"]["summary"],
        })

    except Exception as e:
        return jsonify({"error": f"保存反馈失败: {str(e)}"}), 500

@bazi_bp.route("/feedback/list", methods=["GET"])
def api_feedback_list():
    """列出所有反馈日志的摘要信息，用于评估面板。"""
    limit = request.args.get("limit", 50, type=int)
    verified_only = request.args.get("verified_only", "0") == "1"

    try:
        results = []
        files = sorted(
            [f for f in os.listdir(FEEDBACK_DIR) if f.endswith(".json")],
            reverse=True,
        )
        for fn in files[:limit]:
            filepath = os.path.join(FEEDBACK_DIR, fn)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    log = json.load(f)
                entry = {
                    "filename": fn,
                    "timestamp": log.get("timestamp", "?"),
                    "turn_type": log.get("turn_type", "?"),
                    "plate_summary": log.get("plate_summary", {}),
                    "verification": log.get("verification", {}).get("summary"),
                    "has_verification": "verification" in log,
                }
                if verified_only and not entry["has_verification"]:
                    continue
                results.append(entry)
            except Exception:
                continue

        return jsonify({
            "total_files": len(files),
            "results": results,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 知识库查询（glossary + references）
# ============================================================

@bazi_bp.route("/glossary/lookup", methods=["GET"])
def api_glossary_lookup():
    """服务端术语查询。GET /api/glossary/lookup?term=日主"""
    import json as _json
    term = request.args.get("term", "").strip()
    glossary_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base", "glossary.json")
    try:
        with open(glossary_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
    except Exception:
        return {"error": "glossary not found"}, 500

    terms = data.get("terms", {})
    if term == "all":
        return {"terms": [{"term": k, "definition": v["definition"], "category": v.get("category", "")} for k, v in terms.items()]}
    if term in terms:
        return {"term": term, "definition": terms[term]["definition"], "category": terms[term].get("category", "")}
    # 模糊匹配
    for k, v in terms.items():
        if term in k or term in v.get("definition", ""):
            return {"term": k, "definition": v["definition"], "category": v.get("category", "")}
    return {"error": "term not found"}, 404

@bazi_bp.route("/glossary/references", methods=["GET"])
def api_glossary_references():
    """返回字段级古籍引用，前端 tooltip 使用。"""
    import json as _json
    ref_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base", "classical_references.json")
    try:
        with open(ref_path, "r", encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return {"references": []}

# ============================================================
# 启动
# ============================================================

