# -*- coding: utf-8 -*-
"""邮箱质量检查 — 软提示用，永不硬拦截

用途：注册时检测"疑似临时邮箱 / 疑似拼写错误"，返回 warning 提示文案，
由前端展示确认提示，但允许用户继续注册（验证期避免误伤真实用户）。

将来要收紧数据洁净度时，把调用方的"提示"改成"拒绝"即可，一条开关。
"""

# 常见邮箱域名（拼写检查基准 + 正常域名白名单）
COMMON_DOMAINS = [
    "gmail.com", "googlemail.com", "qq.com", "foxmail.com", "163.com", "126.com",
    "139.com", "outlook.com", "hotmail.com", "live.com", "msn.com", "yahoo.com",
    "icloud.com", "me.com", "aliyun.com", "sina.com", "sohu.com", "yeah.net",
    "189.cn", "tom.com", "21cn.com", "proton.me", "gmx.com", "zoho.com",
    "aol.com", "yandex.com", "hey.com", "fastmail.com", "mail.ru", "naver.com",
]

# 临时/一次性邮箱域名黑名单（常见）
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "grr.la", "sharklasers.com",
    "tempmail.com", "temp-mail.org", "10minutemail.com", "yopmail.com",
    "trashmail.com", "throwawaymail.com", "mailnesia.com", "maildrop.cc",
    "getnada.com", "tempail.com", "emailondeck.com", "mailcatch.com",
    "spamgourmet.com", "jetable.org", "mytemp.email", "dispostable.com",
    "mintemail.com", "mailtemp.net", "tmpmail.org", "discard.email",
    "spambox.us", "tmail.ws", "maileater.com", "mailsac.com", "mailnull.com",
    "mvrht.com", "mvrht.net", "mega.zik.dj", "mailto.plus", "bouncemail.com",
}


def _levenshtein(a: str, b: str, max_d: int = 2) -> int:
    """限制距离的编辑距离，超过 max_d 提前返回 max_d+1。"""
    if abs(len(a) - len(b)) > max_d:
        return max_d + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(v)
            row_min = min(row_min, v)
        prev = cur
        if row_min > max_d:
            return max_d + 1
    return prev[-1]


def check_email_quality(email: str) -> dict:
    """返回 {ok: bool, warning: str|None}。ok 恒为 True（软提示，永不拦截）。"""
    email = (email or "").strip().lower()
    if "@" not in email:
        return {"ok": True, "warning": None}
    domain = email.rsplit("@", 1)[1]
    if not domain or "." not in domain:
        return {"ok": True, "warning": None}

    # 1) 临时邮箱
    if domain in DISPOSABLE_DOMAINS:
        return {"ok": True,
                "warning": "这个邮箱看起来是临时邮箱（一次性地址），收不到重要通知，确认一下？"}

    # 2) 拼写接近常见域名（gmial.com → gmail.com）
    for known in COMMON_DOMAINS:
        if known == domain:
            return {"ok": True, "warning": None}
        if _levenshtein(domain, known) <= 2:
            return {"ok": True,
                    "warning": f"邮箱域名 {domain} 看起来拼写有误，你是指 {known} 吗？"}

    return {"ok": True, "warning": None}
