#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""embedding 检索后端 — 条目级向量检索（BAAI/bge-small-zh-v1.5）。

与 lexical 后端共享同一外部契约（BaseBackend）：retrieve_str / retrieve_hits。
差异在粒度：lexical 匹配到"块"拼整块（文件级/宫位级 dump），embedding 匹配到"条目"拼条目，
返回单位与答案单位对齐（star_palace 的星×宫格、classics 的 pattern、hua 的化曜×宫、
fuzuo 的辅星×宫、tiaohou 的单行）。这是验收线（文件级 43→0、平均 1640 及格 / ~1KB 优良）
能达成的关键。

编码对称性（bge-zh v1.5 无 instruction 前缀）：
- query 与 passage 走同一 encode 调用、同一 normalize_embeddings 参数，杜绝系统性偏差
- 模型下载走 HF_ENDPOINT=https://hf-mirror.com（国内直连 HuggingFace 可能卡死）

惰性注册：import 本模块即调用 register_backend()，不引入重依赖；
只有 KB_BACKEND=embedding 时 kb_loader 才会触发本模块加载。

2026-08-01 第二步（embedding 后端）
"""
import json
import os

from services.kb_loader import BaseBackend, register_backend, _load_json_kb

_MODEL_NAME = os.environ.get("KB_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")


def _extract_entries(kb_name: str, kb: dict) -> list:
    """条目抽取：对齐各 KB 的答案单位（dry_run_check.answer_text 同口径）。

    返回 [(entry_id, entry_text)]。entry_id 是 hits 出口的返回单位（注入层 join 键），
    entry_text 必须包含答案原文（归一化后 exact_contain 可判）。
    """
    entries = []
    if kb_name == "ziwei_star_palace.json":
        stars = kb.get("stars", {})
        for star, star_data in stars.items():
            if not isinstance(star_data, dict):
                continue
            palaces = star_data.get("palaces", {})
            for palace, val in palaces.items():
                entries.append((f"{star}|{palace}", f"{star} {palace}：{json.dumps(val, ensure_ascii=False)}"))
    elif kb_name == "ziwei_classics.json":
        patterns = kb.get("patterns", {})
        for name, text in patterns.items():
            if isinstance(text, str):
                entries.append((name, f"{name}：{text}"))
    elif kb_name == "ziwei_hua.json":
        interp = kb.get("interpretation", {})
        for hua, hdata in interp.items():
            if not isinstance(hdata, dict):
                continue
            guide = hdata.get("in_palace_guide", {})
            for palace, val in guide.items():
                if isinstance(val, str):
                    entries.append((f"{hua}|{palace}", f"{hua} {palace}：{val}"))
            meaning = hdata.get("meaning", "")
            if isinstance(meaning, str) and meaning:
                entries.append((f"{hua}|_meaning", f"{hua} {meaning}"))
    elif kb_name == "ziwei_fuzuo.json":
        for star, sdata in kb.items():
            if star.startswith("_") or not isinstance(sdata, dict):
                continue
            fen = sdata.get("分宫", {})
            for palace, val in fen.items():
                if isinstance(val, str):
                    entries.append((f"{star}|{palace}", f"{star} {palace}：{val}"))
            zuhe = sdata.get("组合", {})
            for zname, zval in zuhe.items():
                if isinstance(zval, str):
                    entries.append((f"{star}|组合|{zname}", f"{star} {zname}：{zval}"))
            zonglun = sdata.get("总论", "")
            if isinstance(zonglun, str) and zonglun:
                entries.append((f"{star}|总论", f"{star} 总论：{zonglun}"))
    elif kb_name == "tiaohou.json":
        table = kb.get("table", {})
        for gan, months in table.items():
            if not isinstance(months, dict):
                continue
            for zhi, val in months.items():
                entries.append((f"{gan}|{zhi}", f"{gan}日 {zhi}月 调候用神：{json.dumps(val, ensure_ascii=False)}"))
    else:
        # generic 兜底：顶层键值一条（目前 run 集未覆盖，为后续登记化预留）
        for key, val in kb.items():
            if key.startswith("_"):
                continue
            if isinstance(val, (str, dict, list)):
                text = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
                entries.append((str(key), f"{key}：{text}"))
    return entries


class EmbeddingBackend(BaseBackend):
    """向量检索后端：匹配到条目拼条目，返回单位 = 答案单位。"""

    def __init__(self):
        self._model = None
        self._index = {}  # kb_name -> {"ids": [...], "texts": [...], "vecs": ndarray}

    # ── 模型 / 索引 ──
    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(_MODEL_NAME)
        return self._model

    def _encode(self, texts):
        model = self._ensure_model()
        return model.encode(list(texts), normalize_embeddings=True, batch_size=64)

    def _get_index(self, kb_name):
        """懒构建 + 缓存条目索引。首次对某 KB 编码全量条目，之后只编码 query。"""
        if kb_name in self._index:
            return self._index[kb_name]
        kb = _load_json_kb(kb_name)
        entries = _extract_entries(kb_name, kb)
        if not entries:
            idx = {"ids": [], "texts": [], "vecs": None}
            self._index[kb_name] = idx
            return idx
        ids = [e[0] for e in entries]
        texts = [e[1] for e in entries]
        vecs = self._encode(texts)
        idx = {"ids": ids, "texts": texts, "vecs": vecs}
        self._index[kb_name] = idx
        return idx

    # ── 出口（与 lexical 同契约）──
    def retrieve_str(self, query_keywords, kb_name, top_k=10):
        hits = self._rank(query_keywords, kb_name, top_k)
        if not hits:
            return ""
        parts = []
        for eid, text in hits:
            parts.append(f"### {eid}\n{text}")
        return "\n\n".join(parts)

    def retrieve_hits(self, query_keywords, kb_name, top_k=10):
        return [eid for eid, _ in self._rank(query_keywords, kb_name, top_k)]

    def _rank(self, query_keywords, kb_name, top_k):
        idx = self._get_index(kb_name)
        if not idx["ids"] or idx["vecs"] is None:
            return []
        import numpy as np

        # query 编码：每个 keyword 独立编码取平均（比整句拼接更能保留"专名+槽位"双词信息）
        # 对称性：与 passage 同一 encode 调用、同一 normalize 参数，归一化空间一致
        qs = self._encode([k for k in query_keywords if k])
        if len(qs) == 0:
            return []
        q = np.asarray(qs).mean(axis=0)
        q = q / np.linalg.norm(q)
        scores = np.asarray(idx["vecs"]) @ q  # 归一化后点积 = 余弦相似度
        order = np.argsort(-scores)[:top_k]
        return [(idx["ids"][i], idx["texts"][i]) for i in order]


def register_embedding_backend():
    """注册 embedding 后端（kb_loader 在 KB_BACKEND=embedding 时调用）。"""
    register_backend("embedding", EmbeddingBackend())


# 模块加载即注册（保持"注册不动、后端可换"：结构层预留的 register_backend 入口）
register_embedding_backend()
