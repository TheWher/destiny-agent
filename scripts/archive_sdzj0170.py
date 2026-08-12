# -*- coding: utf-8 -*-
"""SDZJ0170 正式落库：按卷合并 tmp markdown -> 素材池快照（带 frontmatter）"""
import os, re, glob, datetime

SRC = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\full"
DST = r"D:\OH-WorkSpace\Destiny_agent\knowledge_base\obsidian\素材池\网页快照"
os.makedirs(DST, exist_ok=True)

# 卷分组：文件名前缀/子章 id -> 卷
GROUPS = {
    "juan1": {"ids": ["1jvzoopnqo0t6"], "title": "新锓希夷陈先生紫微斗数全书卷之一（太微赋/形性赋/星垣论/斗数准绳/斗数发微论/重补斗数彀率/增补大微赋/诸星问答论）"},
    "juan2": {"ids": ["1jvzootg40y05","1jvzootg41an9","1jvzootg41nad","1jvzootg41zxh","1jvzootg42ckl","1jvzootg42p7p","1jvzootg431ut","1jvzootg43ehx","1jvzootg43r51","1jvzootg443s5","1jvzootg44gf9"], "title": "新锓希夷陈先生紫微斗数全书卷之二（骨髓赋注解/女命骨髓赋注解/太微赋注解/补遗骨髓赋注解/定富贵贫贱诀/十二宫诸星得地诀）"},
    "juan3": {"ids": ["1jvzooy7dkbhh"], "title": "新锓希夷陈先生紫微斗数全书卷之三（安身命例/安星诸诀/论星辰生克制化）"},
    "juan4": {"ids": ["1jvzop13hw26h","1jvzop13hwetl","1jvzop13hwrgp","1jvzop13hx43t","1jvzop13hxgqx","1jvzop13hxte1","1jvzop13hy615","1jvzop13hyio9","1jvzop13hyvbd","1jvzop13hz7yh","1jvzop13hzkll","1jvzop13hzx8p"], "title": "新锓希夷陈先生紫微斗数全书卷之四（十二宫论：兄弟/妻妾/子女/财帛/疾厄/迁移/奴仆/官禄/田宅/福德/父母）"},
    "juan5": {"ids": ["1jvzop58rvdbm"], "title": "新锓希夷陈先生紫微斗数全书卷之五（谭星要论/论人命入格/论格星数高下）"},
    "mingtu": {"ids": ["1jvzop88fh4it","1jvzop88fhh5x","1jvzop88fhtt1","1jvzop88fi6g5","1jvzop88fij39","1jvzop88fivqd","1jvzop88fj8dh","1jvzop88fjl0l","1jvzop88fjxnp","1jvzop88fkaat","1jvzop8d7olyq"], "title": "新锓希夷陈先生紫微斗数全书命图（孔仲尼命等古今富贵贫贱夭寿命图）"},
    "juan7": {"ids": ["1jvzop9sm8b3n","1jvzop9sm90dv","1jvzopa1f8umz","1jvzopa1fayhn"], "title": "新锓紫微斗数全书谭命活套卷之七（批贵命/批富命/批女命）"},
}

def load(name):
    for pat in [f"*{name}.md", f"*_sub_{name}.md", f"*_sub_{name}*.md"]:
        hits = glob.glob(os.path.join(SRC, pat))
        if hits:
            return open(hits[0], encoding="utf-8").read()
    return ""

def strip(md):
    md = re.sub(r"\[(?:上一篇|下一篇|目录)\]\(.*?\)", "", md)
    md = re.sub(r"\[\]\(.*?识典古籍.*?\)", "", md)
    md = re.sub(r"\[书库\]\(.*?\)", "", md)
    md = re.sub(r"登录后阅读更方便", "", md)
    md = re.sub(r"# 新锓希夷陈先生紫微斗数全书(全文)?", "", md)
    return md

now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
for grp, spec in GROUPS.items():
    parts = []
    for cid in spec["ids"]:
        md = load(cid)
        if not md:
            print(f"[MISS] {grp} {cid}")
            continue
        parts.append(strip(md).strip())
    body = "\n\n---\n\n".join(p for p in parts if p)
    fm = (
        "---\n"
        f"title: {spec['title']}\n"
        "url: https://www.shidianguji.com/book/SDZJ0170\n"
        "source: 识典古籍 shidianguji.com\n"
        f"fetched_at: {now}\n"
        "status: complete\n"
        "authority: 古籍数字化平台\n"
        "system: 古籍\n"
        "tags:\n"
        "  - 素材\n"
        "  - 古籍\n"
        "  - 紫微斗数全书\n"
        "  - SDZJ0170\n"
        "  - 南阳堂刊本\n"
        "  - 简体转写\n"
        "type: 网页快照\n"
        "content_mode: fit_markdown\n"
        "---\n"
    )
    fn = os.path.join(DST, f"2026-08-12-sdzj0170-{grp}.md")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(fm + "\n" + body)
    print(f"[saved] {fn} body={len(body)}")

# 目录页另存
mulu = open(os.path.join(SRC, "v7_collect_sub_1l8c31cc86psj.md"), encoding="utf-8").read()
mulu_fm = (
    "---\ntitle: 新锓希夷陈先生紫微斗数全书目录\n"
    "url: https://www.shidianguji.com/book/SDZJ0170/chapter/1l8c31cc86psj\n"
    "source: 识典古籍 shidianguji.com\n"
    f"fetched_at: {now}\nstatus: complete\nauthority: 古籍数字化平台\nsystem: 古籍\n"
    "tags:\n  - 素材\n  - 古籍\n  - 紫微斗数全书\n  - SDZJ0170\n  - 目录\n"
    "type: 网页快照\ncontent_mode: fit_markdown\n---\n"
)
with open(os.path.join(DST, "2026-08-12-sdzj0170-mulu.md"), "w", encoding="utf-8") as f:
    f.write(mulu_fm + "\n" + strip(mulu))
print("[saved] mulu")
