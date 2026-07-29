#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Destiny Agent CLI — 统一命令行入口

用法：
  python cli.py test [--smoke] [--verbose]     # 测试
  python cli.py analyze bazi <y> <m> <d> <h> [<min>] <gender> [--password <pw>]
  python cli.py analyze ziwei <y> <m> <d> <h> [<min>] <gender> [--password <pw>]
  python cli.py verify-report [--output <path>]  # 验盘聚合报告
  python cli.py sessions list                     # 会话列表
  python cli.py sessions show <id>                # 会话详情
"""

import argparse
import json
import os
import sys

# 确保项目根在 sys.path 中
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def cmd_test(args):
    """运行测试"""
    import subprocess
    script = os.path.join(ROOT, "test_paipan.py")
    cmd = [sys.executable, script]
    if args.smoke:
        cmd.append("--smoke")
    if args.verbose:
        cmd.append("--verbose")
    subprocess.run(cmd)


def cmd_analyze(args):
    """单次命盘分析（直接调 service 函数，不走 HTTP）"""
    y, m, d, h = args.year, args.month, args.day, args.hour
    minute = args.minute or 0
    gender = args.gender

    from services.llm_client import API_CONFIG
    if not API_CONFIG.get("api_key"):
        print("错误：未配置 API Key。请检查 config.local.py")
        return

    if args.system == "bazi":
        from bazi_calculator import paipan
        from app import plate_to_dict
        from services.bazi_analysis import analyze_bazi

        plate = paipan(y, m, d, h, minute, gender=gender)
        plate.compute()
        pdict = plate_to_dict(plate)

        print(f"四柱：{' '.join(pdict['sizhu'])}")
        print("分析中...")
        result = analyze_bazi(pdict, timeout=600)
        if result.get("success"):
            print(result["analysis"])
        else:
            print(f"失败：{result.get('error', '未知错误')}")

    elif args.system == "ziwei":
        from ziwei_calculator import ziwei_paipan, plate_to_dict as zw_plate_to_dict
        from services.ziwei_analysis import analyze_ziwei

        plate = ziwei_paipan(y, m, d, h, minute, gender)
        pdict = zw_plate_to_dict(plate)

        # 验盘模式
        import datetime as _dt
        pdict["_verification_mode"] = True
        pdict["_current_year"] = _dt.date.today().year
        pdict["birth_year"] = y
        pdict["_current_age"] = pdict["_current_year"] - y

        print(f"命宫：{plate.get('soul_palace', '?')}  身宫：{plate.get('body_palace', '?')}")
        print(f"五行局：{plate.get('five_elements_class', '?')}")
        print("分析中（验盘模式，约 2-4 分钟）...")
        result = analyze_ziwei(pdict, timeout=600)
        if result.get("success"):
            if result.get("analysis"):
                print(result["analysis"])
            if result.get("verification"):
                v = result["verification"]
                print(f"\n--- 验盘合规检查 ---")
                print(f"预测条数：{v.get('predictions_count', 0)}")
                print(f"年份：{v.get('years_found', [])}")
                print(f"通过：{v.get('passed', False)}")
                if v.get("issues"):
                    for issue in v["issues"]:
                        print(f"  问题：{issue}")
        else:
            print(f"失败：{result.get('error', '未知错误')}")


def cmd_verify_report(args):
    """生成验盘反馈聚合报告"""
    from scripts.evaluate_ziwei_verify import load_feedbacks, analyze
    records = load_feedbacks()
    report = analyze(records)
    if args.output:
        output_path = args.output
        if not os.path.isabs(output_path):
            output_path = os.path.join(ROOT, output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"报告已保存：{output_path}")


def cmd_sessions(args):
    """会话管理"""
    SESSIONS_DIR = os.path.join(ROOT, "sessions")
    if args.action == "list":
        if not os.path.exists(SESSIONS_DIR):
            print("暂无会话")
            return
        files = sorted(os.listdir(SESSIONS_DIR), reverse=True)
        if not files:
            print("暂无会话")
            return
        print(f"{'ID':<10} {'创建时间':<20} {'标题':<30} {'消息数':>6}")
        print("-" * 68)
        for fn in files:
            if not fn.endswith(".json"):
                continue
            sid = fn[:-5]
            try:
                with open(os.path.join(SESSIONS_DIR, fn), "r", encoding="utf-8") as f:
                    s = json.load(f)
                ts = s.get("created_at", "")[:19]
                title = (s.get("title") or s.get("plate_summary", ""))[:28]
                msgs = len(s.get("messages", []))
                print(f"{sid:<10} {ts:<20} {title:<30} {msgs:>6}")
            except Exception:
                print(f"{sid:<10} (读取失败)")
    elif args.action == "show":
        sid = args.id
        fp = os.path.join(SESSIONS_DIR, f"{sid}.json")
        if not os.path.exists(fp):
            print(f"会话 {sid} 不存在")
            return
        with open(fp, "r", encoding="utf-8") as f:
            s = json.load(f)
        print(f"ID：{s.get('id')}")
        print(f"标题：{s.get('title', '无')}")
        print(f"创建：{s.get('created_at', '?')}")
        print(f"命盘：{s.get('plate_summary', '无')}")
        msgs = s.get("messages", [])
        print(f"消息数：{len(msgs)}")
        for i, m in enumerate(msgs):
            role = m.get("role", "?")
            content = m.get("content", "")
            preview = content[:120].replace("\n", " ")
            print(f"  [{i}] {role}: {preview}...")


def main():
    parser = argparse.ArgumentParser(
        description="Destiny Agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python cli.py test --smoke\n"
               "  python cli.py analyze bazi 2005 8 19 1 男\n"
               "  python cli.py verify-report --output feedback/ziwei/report_cache.json\n"
               "  python cli.py sessions list\n"
               "  python cli.py sessions show abc12345"
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # test
    p_test = sub.add_parser("test", help="运行测试")
    p_test.add_argument("--smoke", action="store_true", help="仅冒烟测试（5 条）")
    p_test.add_argument("--verbose", action="store_true", help="详细输出")

    # analyze
    p_analyze = sub.add_parser("analyze", help="单次命盘分析")
    p_analyze.add_argument("system", choices=["bazi", "ziwei"], help="分析系统")
    p_analyze.add_argument("year", type=int)
    p_analyze.add_argument("month", type=int)
    p_analyze.add_argument("day", type=int)
    p_analyze.add_argument("hour", type=int)
    p_analyze.add_argument("minute", type=int, nargs="?", default=0)
    p_analyze.add_argument("gender", choices=["男", "女"])
    p_analyze.add_argument("--password", type=str, default="", help="密码")

    # verify-report
    p_verify = sub.add_parser("verify-report", help="验盘聚合报告")
    p_verify.add_argument("--output", type=str, default=None, help="输出路径（如 feedback/ziwei/report_cache.json）")

    # sessions
    p_sessions = sub.add_parser("sessions", help="会话管理")
    p_sessions_sub = p_sessions.add_subparsers(dest="action")
    p_sessions_list = p_sessions_sub.add_parser("list", help="列出所有会话")
    p_sessions_show = p_sessions_sub.add_parser("show", help="查看会话详情")
    p_sessions_show.add_argument("id", type=str, help="会话 ID")

    args = parser.parse_args()

    if args.command == "test":
        cmd_test(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "verify-report":
        cmd_verify_report(args)
    elif args.command == "sessions":
        cmd_sessions(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
