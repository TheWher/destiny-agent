#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用户命理画像持久化

跨会话记忆层：存储用户的八字/紫微分析结论和已验证事实，
供 function calling 时 LLM 按需检索和更新。
"""

import json
import os
import time
from datetime import datetime
from typing import Optional


# ── 存储路径 ────────────────────────────────────────────

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MEMORY_DIR = os.path.join(_ROOT, "sessions", "user_profiles")
os.makedirs(_MEMORY_DIR, exist_ok=True)


# ── 数据结构 ────────────────────────────────────────────

class UserMemory:
    """用户命理画像

    跨会话持久化，LLM 通过 memory_retrieve / memory_store Tool 读写。
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.bazi_profile: dict = {}
        self.ziwei_profile: dict = {}
        self.verified_facts: list[dict] = []     # [{year, desc, verified_at, source}]
        self.analysis_history: list[dict] = []   # [{timestamp, type, findings_summary, usage}]
        self.updated_at: str = ""

    # ── 文件 I/O ────────────────────────────────────

    @property
    def _filepath(self) -> str:
        return os.path.join(_MEMORY_DIR, f"{self.user_id}.json")

    def save(self) -> bool:
        """保存到磁盘"""
        try:
            data = {
                "user_id": self.user_id,
                "bazi_profile": self.bazi_profile,
                "ziwei_profile": self.ziwei_profile,
                "verified_facts": self.verified_facts[-50:],  # 只保留最近 50 条
                "analysis_history": self.analysis_history[-20:],  # 只保留最近 20 次
                "updated_at": datetime.now().isoformat(),
            }
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.updated_at = data["updated_at"]
            return True
        except Exception:
            return False

    def load(self) -> bool:
        """从磁盘加载"""
        if not os.path.exists(self._filepath):
            return False
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.bazi_profile = data.get("bazi_profile", {})
            self.ziwei_profile = data.get("ziwei_profile", {})
            self.verified_facts = data.get("verified_facts", [])
            self.analysis_history = data.get("analysis_history", [])
            self.updated_at = data.get("updated_at", "")
            return True
        except Exception:
            return False

    # ── 更新方法 ────────────────────────────────────

    def add_analysis(self, analysis_type: str, findings: str, usage: dict = None) -> None:
        """追加一次分析记录"""
        self.analysis_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": analysis_type,
            "findings_summary": findings[:500],  # 截断长文本
            "usage": usage or {},
        })
        # 保持上限
        if len(self.analysis_history) > 20:
            self.analysis_history = self.analysis_history[-20:]

    def add_fact(self, year: int, desc: str, source: str = "user_verified") -> None:
        """追加一条已验证事实"""
        self.verified_facts.append({
            "year": year,
            "desc": desc[:200],
            "verified_at": datetime.now().isoformat(),
            "source": source,
        })
        if len(self.verified_facts) > 50:
            self.verified_facts = self.verified_facts[-50:]

    def update_bazi_profile(self, profile: dict) -> None:
        """更新八字画像（合并而非覆盖）"""
        self.bazi_profile.update(profile)

    def update_ziwei_profile(self, profile: dict) -> None:
        """更新紫微画像"""
        self.ziwei_profile.update(profile)

    # ── 导出 ────────────────────────────────────────

    def get_context(self, max_facts: int = 5, max_history: int = 3) -> str:
        """生成可注入 LLM prompt 的上下文摘要"""
        parts = []

        if self.bazi_profile:
            bp = self.bazi_profile
            parts.append("## 八字画像")
            if bp.get("rizhu"):
                parts.append(f"- 日主：{bp['rizhu']}")
            if bp.get("pattern_summary"):
                parts.append(f"- 格局：{bp['pattern_summary']}")
            if bp.get("yongshen"):
                parts.append(f"- 用神：{bp['yongshen']}")
            if bp.get("key_signals"):
                parts.append(f"- 关键信号：{', '.join(bp['key_signals'])}")

        if self.ziwei_profile:
            zp = self.ziwei_profile
            parts.append("\n## 紫微画像")
            if zp.get("ming_gong"):
                parts.append(f"- 命宫：{zp['ming_gong']}")
            if zp.get("pattern"):
                parts.append(f"- 格局：{zp['pattern']}")
            if zp.get("key_interactions"):
                parts.append(f"- 关键交互：{', '.join(zp['key_interactions'])}")

        if self.verified_facts and max_facts > 0:
            parts.append(f"\n## 已验证事实（最近 {min(max_facts, len(self.verified_facts))} 条）")
            for f in self.verified_facts[-max_facts:]:
                parts.append(f"- {f['year']}年：{f['desc']}")

        if self.analysis_history and max_history > 0:
            parts.append(f"\n## 历史分析（最近 {min(max_history, len(self.analysis_history))} 次）")
            for h in self.analysis_history[-max_history:]:
                ts = h['timestamp'][:10]
                parts.append(f"- [{ts}] {h['type']}: {h['findings_summary'][:100]}")

        return "\n".join(parts) if parts else ""

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "bazi_profile": self.bazi_profile,
            "ziwei_profile": self.ziwei_profile,
            "verified_facts_count": len(self.verified_facts),
            "analysis_count": len(self.analysis_history),
            "updated_at": self.updated_at,
        }


# ── 辅助函数（供 Tool 注册使用） ──────────────────────

def load_memory(user_id: str) -> dict:
    """加载用户记忆，返回可序列化的 dict"""
    mem = UserMemory(user_id)
    if not mem.load():
        return {"user_id": user_id, "exists": False, "context": ""}
    return {
        "user_id": user_id,
        "exists": True,
        "bazi_profile": mem.bazi_profile,
        "ziwei_profile": mem.ziwei_profile,
        "verified_facts": mem.verified_facts[-5:],
        "analysis_history": [{
            "timestamp": h["timestamp"],
            "type": h["type"],
            "findings_summary": h["findings_summary"][:200],
        } for h in mem.analysis_history[-3:]],
        "context": mem.get_context(),
        "updated_at": mem.updated_at,
    }


def store_memory(user_id: str,
                 analysis_type: str = "",
                 findings: str = "",
                 bazi_profile: dict = None,
                 ziwei_profile: dict = None,
                 verified_facts: list[dict] = None) -> dict:
    """存储分析结果到用户记忆"""
    mem = UserMemory(user_id)
    mem.load()  # 加载已有数据（如果存在）

    if analysis_type and findings:
        mem.add_analysis(analysis_type, findings)

    if bazi_profile:
        mem.update_bazi_profile(bazi_profile)

    if ziwei_profile:
        mem.update_ziwei_profile(ziwei_profile)

    if verified_facts:
        for f in verified_facts:
            if isinstance(f, dict) and f.get("year") and f.get("desc"):
                mem.add_fact(f["year"], f["desc"], f.get("source", "llm_inferred"))

    if mem.save():
        return {"success": True, "user_id": user_id, "message": "记忆已保存"}
    return {"success": False, "error": "保存失败"}


# ── 测试 ──────────────────────────────────────────────

if __name__ == "__main__":
    # 基本读写测试
    mem = UserMemory("test_user_001")
    mem.update_bazi_profile({
        "rizhu": "己土",
        "pattern_summary": "伤官格，中和偏旺",
        "yongshen": "水",
        "key_signals": ["巳亥冲", "伤官见官"],
    })
    mem.add_analysis("bazi_analysis", "日主己土，生于申月，伤官格。用神水，喜金木，忌火土。")
    mem.add_fact(2018, "换工作到互联网行业")
    mem.add_fact(2023, "购置房产")
    mem.save()

    # 重新加载验证
    mem2 = UserMemory("test_user_001")
    mem2.load()
    print("Load OK:", mem2.to_dict())
    print("\nContext:")
    print(mem2.get_context())

    # 清理测试文件
    os.remove(mem._filepath)
    print("\nTest file cleaned.")
