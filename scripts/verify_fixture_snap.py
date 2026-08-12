# -*- coding: utf-8 -*-
"""
verify_fixture_snap.py — 解析器三层回归骨架（fixture 断言脚本，锁值集快照版本）

背景（2026-08-12 凌晨共识 → fixture_snap-20260812-0，五样本）：
推演驱动链"先判定单位后计数"的第一道闸 = 切分回归夹具。
fixture 固化凌晨共识的预期输出：主语层（三档路径/主语值/盘在场）、四化层
（化X结构/标记词/复合形态/方位词）、段数层（段数/起落点/标记层推导）、
静态成分段（注记/骨架/第三桶）、双签（层级+功能角色）、证据面向
（句式/框架/术语 + 豁免/保留）、出处类型（原创/引述/注疏）、对角线检查。

本脚本按值集快照锁版本跑，断言分两块：
  - 解析器一致性：全绿只证明解析器与预期一致（规格自洽），不证明预期正确；
    预期本身是共识产物，假说验证靠第一波料（料源三侧、20-30 谓词样本、掺边界句）。
  - 假说验证：未开扫时为料单清单，开扫后落真实断言。

归因三层：主语识别（显式/可计算/隐式）、四化检测（化X结构/标记词）、段数起落。
错误类别：断言失败（结构违例=真 bug）、待定（主语信息不足，正常输出非 bug）、
恢复成功（跨句回注转正）。显式识别错误=真 bug；隐式恢复失败=料的信息量问题。
关系动词（坐守/会照/冲破）不进三态函数，直接归静态骨架/第三桶。

用法：python scripts/verify_fixture_snap.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
# 值集快照版本：v3 登记落地 → 快照+1，旧 fixture 留档不覆盖，本常量同步改
LOCKED_VERSION = "snap-20260812-0"

PLACEHOLDER_MARK = "<PLACEHOLDER"

# ============ 判定常量（与 fixture schema_fields 同源；改值集须过 v3 登记口径）============
SUBJECT_CATEGORIES = {"宫干", "大限", "流年", "生年干", "待定"}
SUBJECT_PATHS = {"显式", "可计算", "隐式"}
MARKER_VALUES = {"N/A", "无", "自化", "转", "飞"}
MARKER_WORDS = {"飞", "转", "自化"}
STATIC_CLASSES = {"注记", "骨架", "静态受动框架"}
EXPECTED_STATUSES = {"定稿", "待精读", "待定", "待核"}
ROLES = {"机制性", "注疏性动态", "转述", "静态注记", "待定"}
LAYERS = {"本命盘宫干层", "运限", "流年", "本命", "待定"}
FACINGS = {"句式", "框架", "术语"}
SOURCE_TYPES = {"原创", "引述", "注疏"}
EXEMPTIONS = {"豁免", "保留"}
DYNAMIC_CATEGORIES = {"宫干", "大限", "流年"}
STATIC_ROLE_MAP = {"动态": {"机制性", "注疏性动态"}, "静态注记": {"静态注记"}, "待定": {"待定"}}
# 双签层级派生映射（2026-08-12 定，notes 同源）：layer = f(subject.category)，一一对应。
# 前提：宫干→本命盘宫干层 是默认本命盘假设，句面无时间词时句面自身答不了盘层；
# 未来若有可计算档样本声明运限/流年层（大限盘/流年盘宫干飞化），映射校验将 warn 提示，
# 需盘层语境标注确认，不静默吞掉。
LAYER_BY_CATEGORY = {"宫干": "本命盘宫干层", "大限": "运限", "流年": "流年", "生年干": "本命", "待定": "待定"}

# 显式载体词表（同义组收编；判据=载体字面出现，不按元词"宫干"字面判断）
EXPLICIT_CARRIERS = {
    "生年干": ("生年", "原局", "本命", "命局"),
    "大限": ("大限", "限运", "限年"),
    "流年": ("流年",),
}
STEMS = "甲乙丙丁戊己庚辛壬癸"
# 本宫=命宫 语境相关（2026-08-12 定，执行规格）：古籍中“本宫”有时指当前讨论之宫位，非无条件=命宫；
# 只在上下文可证为命宫（对宫指迁移）时按命宫同义处理，s04 存句即此语境。
PALACES = ("命宫", "命", "本宫", "兄弟", "夫妻", "子女", "财帛", "疾厄", "迁移",
           "仆役", "奴仆", "官禄", "田宅", "福德", "父母")
DIRECTION_WORDS = ("入", "出", "冲", "照", "会", "拱", "夹", "朝")
# 复合凝固搭配（只收凝固搭配，不收标记词+方位词的可分组合"转入/飞出"；
# 匹配按词表分组走，不合成全词 trie，防最长匹配跨边界吞词）
COMPOUND_WORDS = ("冲破", "会照", "坐守", "自化")
# 方向性复合词：凝固搭配整体作方向单位，优先于单字方向词（'冲破'不得被'冲'切碎）。
# '自化/坐守'非方向词，不参与切分。
DIRECTION_COMPOUNDS = ("冲破", "会照")

# 异体字归一映射表（管线入口，2026-08-12 定）：料池保真存储不动，词表保持规范字单一来源，
# 入口映射只做转换。已知异体=确定性转换，静默执行不过待精读闸；未收录异体字进缺词清单
# （与词表同一待遇），不得静默漏匹配。按首波异体出现率补表（先量后切桶）。
# 剋→克 真异体（quanlan 同文异写实证：L29「生剋之機」/ L334「论星辰生克制化」L335「生克制化之机」L942「生克制化之垣」）
VARIANT_MAP = {"衝": "冲", "沖": "冲", "會": "会", "當": "当", "夾": "夹", "剋": "克", "佈": "布"}


def normalize_variants(text):
    """异体字归一：管线入口映射表，转换结果唯一。s03 source_line 为第一个回归锚点。"""
    return "".join(VARIANT_MAP.get(ch, ch) for ch in text)


def is_placeholder(v):
    return isinstance(v, str) and PLACEHOLDER_MARK in v


def load_fixture():
    path = FIXTURES_DIR / f"fixture_{LOCKED_VERSION}.json"
    if not path.exists():
        sys.exit(f"[FATAL] fixture 缺失：{path}（值集快照版本 LOCKED_VERSION 是否已 +1？）")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != LOCKED_VERSION:
        sys.exit(f"[FATAL] fixture 版本不符：文件={data.get('version')}，锁定={LOCKED_VERSION}")
    return data


# ============ 推导函数（断言=推导函数的回归测试，别手工填完再断言）============

def derive_marker(category, count, start_eq_end, marker_words):
    """标记层推导：从切分结果（段数、起落同异）+ 四化标记词推标记层。
    规则：自化必须起落同、飞必须单段起落异、转必须段数>=2 整体单值记转、
    无标记且单段→无；生年干句强制 N/A（v3 登记）。
    返回 (marker, issues)；issues 为一致性软警告，与 fixture 冲突时才升级为失败。"""
    issues = []
    if category == "生年干":
        return "N/A", issues  # ∨ 第二支对生年干句不激活
    if count is None:
        return "待定", ["段数未结构化"]
    if count >= 2:
        if "转" not in marker_words:
            issues.append("多段句缺转标记词（转链漏标风险），不得落'无'档")
        return "转", issues
    # count == 1
    if "转" in marker_words:
        issues.append("转标记词但段数=1，违反'转必须段数>=2'")
    if "自化" in marker_words:
        if start_eq_end is not True:
            issues.append("自化必须起落同")
        return "自化", issues
    if "飞" in marker_words:
        if start_eq_end is not False:
            issues.append("飞必须单段起落异")
        return "飞", issues
    if marker_words:
        issues.append(f"未知标记词组合：{marker_words}")
    if start_eq_end is True:
        issues.append("无标记词但起落同（疑似自化漏标）")
    return "无", issues


def tri_state(category, marker):
    """三态判定：动态 / 静态注记 / 待定。只吃四化谓词；关系动词不进函数。
    ∨ 定义：动态 ⟺ 主语类别∈{宫干/大限/流年} ∨ 标记层≠无，生年干 N/A 覆盖、
    主语待定∧标记=无 时两支全哑火进待定（待定不喂任何计数线）。"""
    if category == "生年干":
        return "静态注记"
    if category == "待定" and marker == "无":
        return "待定"
    if category in DYNAMIC_CATEGORIES or marker in ("飞", "转", "自化"):
        return "动态"
    if category == "待定":
        return "动态"  # 标记支兜底；签名/结构键第一维挂待定
    return "待定"


def subject_surface(sentence):
    """载体字面扫描 → [(category, path), ...] 候选。
    按段扫（2026-08-12 定，执行规格）：方向词之前=主语位，方向词之后=落点位。
    落点位整体不参与载体扫描：显式载体词表全表（时间词/生年词族/宫名/天干）在落点位
    均不激活主语判定（'宫化禄入大限命宫''化禄入原局命宫'类：落点是目标宫限定语，
    主语仍由主语位词表判定；整句扫会把落点限定语误当主语，类别和层一起歪）。
    显式=主语位载体字面出现（宫名+天干/时间词/生年词族）；可计算=主语位宫名独现+句有方向词。"""
    # 顺序焊死（2026-08-12 定，执行规格）：归一 → 复合词匹配 → 方向词 → 主语识别。
    # 复合词整体优先于单字方向词：'冲破'不得先被'冲'切碎。归一发生在切分前。
    seg_end = len(sentence)
    for c in DIRECTION_COMPOUNDS:
        pos = sentence.find(c)
        if pos != -1:
            seg_end = min(seg_end, pos)
    for d in DIRECTION_WORDS:
        pos = sentence.find(d)
        if pos != -1:
            seg_end = min(seg_end, pos)
    head = sentence[:seg_end]
    direction_present = seg_end < len(sentence)
    norm_p = lambda p: p[:-1] if p.endswith("宫") else p
    cands = []
    explicit_pals = set()
    for cat, words in EXPLICIT_CARRIERS.items():
        if any(w in head for w in words):
            cands.append((cat, "显式"))
    for p in PALACES:
        if p in head and any((p + s) in head for s in STEMS):
            cands.append(("宫干", "显式"))
            explicit_pals.add(norm_p(p))
    for p in PALACES:
        if p in head and not any((p + s) in head for s in STEMS) and norm_p(p) not in explicit_pals:
            # 可计算 = 宫名独现 + 方向词；自化配单点（起落同、无方向词）走自化分支
            # （2026-08-12 定，执行规格：自化X 即本宫宫干四化落本宫，天干值需排盘，同档可计算）
            if direction_present or "自化" in head:
                cands.append(("宫干", "可计算"))
    # 去重：同宫异写（'命宫'/'命'）同档位重复命中，避免双候选统计虚高；
    # 同宫异档（宫名+天干→显式 vs 宫名独现→可计算）取信息更全的显式档，不让显式句降级成可计算
    return list(dict.fromkeys(cands))


def parse_start_eq_end(text):
    if not text:
        return None
    if "起落同" in text:
        return True
    if "起落异" in text:
        return False
    return None


# ============ 按样本分层断言 ============

def check_sample(sample, schema_fields):
    """按层断言。枚举校验以 fixture 声明的 schema_fields 为准（加载器可读的字段枚举），
    值域漂移在此层抓出；推导常量只服务推导函数，不作为校验源。"""
    sid = sample["id"]
    out = []

    def add(layer, name, status, detail=""):
        out.append({"sid": sid, "layer": layer, "name": name, "status": status, "detail": detail})

    def enum_check(label, value, key):
        allowed = set(schema_fields.get(key, []))
        if not allowed:
            add("结构层", f"{sid} {label}（schema_fields 缺 {key} 枚举）", "warn")
            return
        if is_placeholder(value):
            add("结构层", f"{sid} {label} 枚举（占位待核）", "pending")
            return
        if isinstance(value, list):
            ok = all(v in allowed for v in value)
        else:
            ok = value in allowed
        add("结构层", f"{sid} {label} ∈ 值集", "pass" if ok else "fail",
            detail=f"值={value}，允许={sorted(allowed)}" if not ok else "")

    # ---- 结构层：枚举值域（以 fixture schema_fields 为准，加载器不裂的关键）----
    subj, sihua, seg, sig = sample["subject"], sample["sihua"], sample["segments"], sample["signature"]
    enum_check("subject.category", subj["category"], "subject.category")
    enum_check("subject.path", subj["path"], "subject.path")
    enum_check("sihua.marker_words", sihua.get("marker_words", []), "sihua.marker_words")
    enum_check("segments.marker", seg["marker"], "segments.marker")
    enum_check("signature.layer", sig["layer"], "signature.layer")
    enum_check("signature.role", sig["role"], "signature.role")
    facing = sample.get("evidence_facing", {})
    enum_check("evidence_facing.facing", facing.get("facing", []), "evidence_facing.facing")
    enum_check("source_type", sample.get("source_type"), "source_type")
    for i, comp in enumerate(sample.get("static_components", [])):
        enum_check(f"static_components[{i}].classification", comp.get("classification"), "static_components.classification")

    # 证据豁免形态：'无' 或 {facing: 豁免|保留} 字典（s03 多面分别标），值域校验
    ex_val = facing.get("exemption")
    if isinstance(ex_val, dict):
        ok = set(ex_val.values()) <= EXEMPTIONS and set(ex_val.keys()) <= FACINGS
        add("结构层", f"{sid} evidence_facing.exemption 字典形态合法", "pass" if ok else "fail",
            detail=str(ex_val) if not ok else "")
    elif ex_val not in (None, "无") and not is_placeholder(ex_val):
        add("结构层", f"{sid} evidence_facing.exemption 形态未知", "fail", detail=str(ex_val))

    # ---- 预期状态分层闸门 ----
    exp_status = sample.get("expected_status", "定稿")
    if isinstance(exp_status, dict):
        ok = set(exp_status.keys()) <= {"surface", "parse"} and set(exp_status.values()) <= EXPECTED_STATUSES
        add("结构层", f"{sid} expected_status 分层形态合法（{exp_status}）", "pass" if ok else "fail")
    surface_gate = exp_status.get("surface", "定稿") if isinstance(exp_status, dict) else exp_status
    parse_gate = exp_status.get("parse", "定稿") if isinstance(exp_status, dict) else exp_status
    sentence_pending = is_placeholder(sample.get("sentence", ""))

    # ---- 主语层（显式/可计算/隐式三档路径，载体字面判据）----
    if surface_gate in ("定稿", "待精读") and not sentence_pending:
        cands = subject_surface(sample["sentence"])
        cat, path = subj["category"], subj["path"]
        if cands:
            ok = (cat, path) in cands
            add("主语识别", f"{sid} 主语类别/路径与句面载体一致", "pass" if ok else "fail",
                detail=f"句面载体候选={cands}，fixture={cat}/{path}")
            if len(cands) > 1:
                # 双候选观察项（2026-08-12 定，执行规格）：分桶留痕，锚点桶/观测桶不混计。
                bucket = "锚点桶" if subj["category"] == "生年干" else "观测桶"
                seg_end2 = len(sample["sentence"])
                for d in DIRECTION_WORDS:
                    pos = sample["sentence"].find(d)
                    if pos != -1:
                        seg_end2 = min(seg_end2, pos)
                head_txt = sample["sentence"][:seg_end2]
                tail_txt = sample["sentence"][seg_end2:]
                norm = lambda p: p[:-1] if p.endswith("宫") else p
                head_pals = {norm(p) for p in PALACES if p in head_txt}
                tail_pals = {norm(p) for p in PALACES if p in tail_txt}
                same_spot = bool(head_pals & tail_pals)
                others = [c for c in cands if c != (cat, path)]
                # 双候选观察项（2026-08-12 定）：同宫信号不升硬断言。判据1 的语义必然是三件套
                # （主语=生年干/标记=N/A/三态=静态注记），句首宫名与落点是否同宫是句面形态不是必然：
                # '命宫生年禄入命'同宫=True，'父母宫生年禄入命'同宫=False，两者都是合法判据1 样本。
                # 锚点桶 warn 只留痕不驱动消歧方向；观测桶同宫占比才驱动。裸'生年禄入命'（无句首宫名）
                # 无双候选、不触发本 warn，作用域边界天然成立。
                add("主语识别", f"{sid} 双候选出现（观察项）", "warn",
                    detail=f"命中={cat}/{path}，其余候选={others}，同宫={same_spot}，桶={bucket}"
                           f"（同宫是句面形态非判据1 必然；观测桶占比才驱动消歧方向）")
        else:
            if path in ("显式", "可计算"):
                add("主语识别", f"{sid} 句面无载体却标{path}（显式识别错误=真 bug）", "fail")
            else:
                add("主语识别", f"{sid} 省略主语/待定档（隐式路径；跨句恢复判定待第一波料）", "warn")
    elif surface_gate == "待核" or sentence_pending:
        add("主语识别", f"{sid} 句面占位/待核，主语表面检查跳过", "pending")

    # ---- 四化层（结构在场性，词表/复合形态留待解析器细化）----
    add("四化检测", f"{sid} 四化结构在场", "pass" if sihua.get("structures") else "fail",
        detail=str(sihua.get("structures")))
    if sihua.get("compound"):
        add("四化检测", f"{sid} 复合形态：{sihua['compound']}", "warn")

    # ---- 段数层（标记层推导 = 核心回归锚点）----
    count = seg.get("count")
    words = sihua.get("marker_words", [])
    eq = parse_start_eq_end(seg.get("start_end", ""))
    derived, issues = derive_marker(subj["category"], count, eq, words)
    ok = seg["marker"] == derived
    add("段数起落", f"{sid} 标记层推导一致（fixture={seg['marker']}，推导={derived}）",
        "pass" if ok else "fail",
        detail="" if ok else f"段数={count}，起落同异={eq}，标记词={words}")
    for iss in issues:
        add("段数起落", f"{sid} 一致性警告：{iss}", "warn")
    if subj["category"] == "生年干" and seg["marker"] != "N/A":
        add("段数起落", f"{sid} 生年干句标记层必须 N/A（v3 登记），实际={seg['marker']}", "fail")

    # ---- 双签层级映射校验（layer = f(subject.category)，声明对齐；warn 级不挡绿）----
    expect_layer = LAYER_BY_CATEGORY.get(subj["category"])
    if expect_layer and sig["layer"] != expect_layer:
        hint = ""
        if subj["category"] == "宫干" and subj["path"] == "可计算":
            hint = "（可计算档默认本命盘假设被打破：句面无时间词，盘层需语境标注确认，不得静默归层）"
        add("双签", f"{sid} layer 与 subject.category 派生映射不符", "warn",
            detail=f"category={subj['category']} → 应={expect_layer}，声明={sig['layer']}{hint}")

    # ---- 三态 + 双签（功能角色）----
    if parse_gate in ("定稿", "待精读"):
        state = tri_state(subj["category"], seg["marker"])
        allowed_roles = STATIC_ROLE_MAP.get(state, set())
        ok = sig["role"] in allowed_roles
        add("双签/三态", f"{sid} 三态判定与功能角色一致（三态={state}，role={sig['role']}）",
            "pass" if ok else "fail")

    # ---- 证据面向锚点：注疏性动态 = 句式豁免 + 框架保留（不进句式线、进框架线）----
    if sig["role"] == "注疏性动态":
        ex = facing.get("exemption", {})
        ok = ("句式" in facing.get("facing", [])) and ex.get("句式") == "豁免" \
             and ("框架" in facing.get("facing", [])) and ex.get("框架") == "保留"
        add("证据面向", f"{sid} 注疏性动态锚点：句式豁免+框架保留", "pass" if ok else "fail",
            detail=f"exemption={ex}")

    # ---- 判据1 锚点（生年干句：N/A + 静态注记，带入不认三元）----
    if sample.get("evidence_basis") and any("判据1" in b for b in sample["evidence_basis"]):
        state = tri_state(subj["category"], seg["marker"])
        ok = (subj["category"] == "生年干" and seg["marker"] == "N/A"
              and state == "静态注记" and sig["role"] == "静态注记")
        add("判据1", f"{sid} 判据1 锚点：生年干/N/A/静态注记（带入不认三元）",
            "pass" if ok else "fail",
            detail=f"category={subj['category']}, marker={seg['marker']}, state={state}, role={sig['role']}")

    # ---- 静态成分段（两小类计数 + 第三桶放行不计数）----
    for i, comp in enumerate(sample.get("static_components", [])):
        cls, cnt = comp.get("classification"), comp.get("counted_in_static_line")
        cgate = comp.get("status", "定稿")
        if cls == "静态受动框架":
            ok = (cnt is False)
            add("静态成分段", f"{sid}.{i} 第三桶不计数（counted_in_static_line=false 强制）",
                "pass" if ok else "fail", detail=f"counted={cnt}，status={cgate}")
        else:
            if cnt in (True, False):
                add("静态成分段", f"{sid}.{i} 两小类计数标记（class={cls}，counted={cnt}）", "pass")
            else:
                add("静态成分段", f"{sid}.{i} 两小类缺计数标记", "fail")

    # ---- 对角线检查（术语分层交叉表；落格计算待解析器接入，先验字段形状+探针标注）----
    diag = sample.get("diagonal_check")
    if diag is None:
        add("对角线", f"{sid} 无对角线检查（单点注记不落交叉表）", "warn")
    else:
        ok = isinstance(diag.get("expected_diagonal"), bool)
        add("对角线", f"{sid} expected_diagonal 布尔校验", "pass" if ok else "fail",
            detail=str(diag.get("expected_diagonal")))
        if diag.get("anomaly_shape"):
            add("对角线", f"{sid} 探针形状标注：{diag['anomaly_shape']} → 术语先渗信号（喂探针环，不进静态线结论）",
                "warn")

    # ---- 异体字归一锚点（s03 source_line = 归一函数第一个回归锚点，2026-08-12 定）----
    sl = sample.get("source_line", "")
    if sl and not is_placeholder(sl) and any(ch in sl for ch in VARIANT_MAP):
        norm = normalize_variants(sl)
        ok = not any(ch in norm for ch in VARIANT_MAP)
        add("异体归一", f"{sid} source_line 异体归一成功", "pass" if ok else "fail",
            detail=f"剩余异体：{[c for c in VARIANT_MAP if c in norm]}" if not ok else "")
        if "冲破" not in norm:
            add("异体归一", f"{sid} 归一后复合方向词'冲破'不可达（复合优先链断裂）", "fail")

    return out


def print_block(title):
    print(f"\n== {title} ==")


def run():
    fixture = load_fixture()
    print(f"== 值集快照：{fixture['version']}")
    print(f"== 基线：{fixture['value_set_baseline']}")
    print_block("解析器一致性（全绿 = 规格自洽，不等于假说验证通过）")

    entries = []
    schema_fields = fixture.get("schema_fields", {})
    for sample in fixture["samples"]:
        entries += check_sample(sample, schema_fields)

    n_pass = n_fail = n_warn = n_pending = 0
    for e in entries:
        if e["status"] == "pass":
            n_pass += 1
            print(f"  [PASS] {e['name']}")
        elif e["status"] == "fail":
            n_fail += 1
            print(f"  [FAIL] {e['name']}：{e['detail']}")
        elif e["status"] == "warn":
            n_warn += 1
            print(f"  [WARN] {e['name']}{'：' + e['detail'] if e['detail'] else ''}")
        else:
            n_pending += 1
            print(f"  [待核] {e['name']}")
    print(f"\n  汇总：PASS {n_pass} / FAIL {n_fail} / WARN {n_warn} / 待核 {n_pending}")
    print("  校准：全绿只证明解析器与预期一致；预期本身是共识，正确性待第一波料。")

    print_block("假说验证（未开扫，料单参数先行）")
    for line in [
        "料源三侧：梁系 / 三合古籍 / 注疏系；抽样按动态谓词样本计，量级 20-30",
        "覆盖：三档主语（显式/可计算/隐式）、四值标记（N/A/无/自化/转/飞）、静态两小类（注记/骨架）",
        "边界：掺受动/无方向词/省略主语句（清晰句全过会高估解析器）；每段标出处行，跨句恢复靠它测",
        "首波必报：三档主语分布、缺词清单、来源层级待定率、受动分布（哪侧哪层）",
        "盘层语境：宫名独现可计算档句子标盘层（句面时间词→显式运限/流年；无信号→默认本命盘挂待精读），",
        "  首波报告单列默认本命盘样本数与待精读样本数，防默认假设静默混进交叉表落格",
        "段作用域：显式判据按段扫（方向词前=主语位，方向词后=落点位）；报告'时间词在落点位'形态出现率，",
        "  占比高则词表作用域升级成硬规则（现为执行规格，不进 v3）",
        "观察项：转链多段句若每段各带方向词，句面多方向词，切分点与链长对齐待首波转链样本（先量后切桶，不提前焊）",
        "观察项：主语位词族与宫名并存双候选（去重后口径：同宫异写如'命宫'/'命'只计一候；",
        "  如'命宫生年禄入命'→生年干显式+宫干可计算），双候选率分两桶：锚点桶（生年干/N/A）同宫是句面形态非必然，",
        "  只留痕不驱动消歧；观测桶（其余类别）同宫占比才驱动消歧规则方向，两桶不混计；出现率从回归 warn 直接统计",
        "异体字：料池原文保真（s03 实证'衝破'异体'衝'），管线入口归一映射表（料池/词表不动）；",
        "  已知异体确定性转换静默执行，未收录异体进缺词清单（与词表同一待遇），首波报告异体出现率后按率补表",
        "受动分布首笔已证：s03 段为原局/大限/流年/流月层级矩阵互冲，全运限层受动、三合注疏侧，首波此形态可少抽",
        "口径：source_type=引述 滤出静态线计数；待定样本不喂任何计数线；第三桶（静态受动框架）不占两小类",
    ]:
        print(f"  [料单] {line}")

    print_block("待核清单（开扫前从料核，不编）")
    for sid, note in [
        ("s01", "出处行待核（梁系/刘韫龄断语）；落点宫句面未示"),
        ("s02", "出处行待核；转链起宫 X 待核"),
        ("s03", "原文已核：ziweicn 快照第 44 行'原局化禄受大限化忌衝破，最为吃紧'（异体'衝'）；冲字双义注疏侧已解（对宫见化忌）、古籍原文层仍待查（只改负载/语义标尺，切分预期已焊死）"),
        ("s04", "已核（2026-08-12）：本宫天同自化忌，ziweicn 快照 tongju-chenxu-huaxing L26，出处保真原句'本宫天同又有自化忌'；source_type=注疏，surface 定稿"),
        ("s05", "出处行待核（三合/判据1 样本）"),
    ]:
        print(f"  [待核] {sid}：{note}")

    failures = [e["name"] for e in entries if e["status"] == "fail"]
    return failures


if __name__ == "__main__":
    failures = run()
    if failures:
        print(f"\n{failures.__len__()} 项断言未过")
        sys.exit(1)
    print("\n零差，规格自洽。")
