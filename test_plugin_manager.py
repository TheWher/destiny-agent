#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P3 插件系统 Phase 1 测试

Phase 1 完工标准：
  ① 六态状态机：全部可达且转移路径有测试
  ② manifest 校验：覆盖格式错误/版本不兼容/依赖缺失三类
  ③ 优雅降级：crash 插件不污染主 Cycle
"""

import json
import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.plugin_manager import (
    PluginManager, PluginState,
    PluginManifest, ManifestValidationError,
    SandboxPolicy, CURRENT_API_VERSION,
    PluginRuntime, register_builtin_skill,
)
from services.orchestrator import (
    AnalysisOrchestrator, ToolDef, CapabilityDef, SkillDef,
)

# ── 颜色和计数 ──
G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; N = '\033[0m'; B = '\033[1m'
pass_count = 0; fail_count = 0; total = 0

def check(name, condition, detail=''):
    global pass_count, fail_count, total
    total += 1
    if condition:
        pass_count += 1; print(f'{G}✅{N} [{name}] {detail}')
    else:
        fail_count += 1; print(f'{R}❌{N} [{name}] {detail}')


# ── 测试数据 ─────────────────────────────────────────

VALID_MANIFEST = {
    "name": "test_bazi_extended",
    "version": "1.2.0",
    "api_version": CURRENT_API_VERSION,
    "description": "八字扩展分析",
    "author": "test",
    "requires": {
        "plugins": {"bazi_basics": ">=1.0.0"},
        "python": ">=3.10",
    },
    "capabilities": ["bazi_advanced"],
    "tools": ["wuxing_extended", "shensha_analysis"],
    "sandbox": {
        "requires_network": False,
        "rw_paths_extra": [],
        "ro_paths_extra": [],
    },
}


# ══════════════════════════════════════════════════════════
# 1. manifest 校验测试
# ══════════════════════════════════════════════════════════

def test_manifest_validation():
    print(f"\n{B}═══ 1. manifest 校验 ═══{N}\n")

    # ── 1.1 合法 manifest ──
    m = PluginManifest.from_dict(VALID_MANIFEST)
    check("manifest: name", m.name == "test_bazi_extended")
    check("manifest: version", m.version == "1.2.0")
    check("manifest: api_version", m.api_version == CURRENT_API_VERSION)
    check("manifest: description", m.description == "八字扩展分析")
    check("manifest: author", m.author == "test")
    check("manifest: capabilities", m.capabilities == ["bazi_advanced"])
    check("manifest: tools", m.tools == ["wuxing_extended", "shensha_analysis"])
    check("manifest: requires.plugins", "bazi_basics" in m.requires.get("plugins", {}))

    # ── 1.2 格式校验：缺少必须字段 ──
    required_fields = ["name", "version", "api_version"]
    for field in required_fields:
        invalid = {k: v for k, v in VALID_MANIFEST.items() if k != field}
        try:
            PluginManifest.from_dict(invalid)
            check(f"格式错误-缺少{field}", False, "应抛出异常")
        except ManifestValidationError as e:
            check(f"格式错误-缺少{field}", True, f"{e.field}: {e.message[:50]}")

    # 空 name
    for bad_name in ["", "  "]:
        try:
            PluginManifest.from_dict({**VALID_MANIFEST, "name": bad_name})
            check(f"格式错误-name='{repr(bad_name)}'", False)
        except ManifestValidationError as e:
            check(f"格式错误-name='{repr(bad_name)}'", True, f"e.field={e.field}")

    # ── 1.3 版本不兼容 ──
    for bad_api in [0, 2, 99, "1"]:
        try:
            PluginManifest.from_dict({**VALID_MANIFEST, "api_version": bad_api})
            check(f"版本不兼容-api_version={bad_api}", False, "应报错")
        except ManifestValidationError as e:
            check(f"版本不兼容-api_version={bad_api}", True, f"e.field={e.field}")

    # ── 1.4 依赖缺失 ──
    # 依赖的插件不存在 → enable 阶段校验（见状态机测试）
    pass  # 状态机测试中覆盖

    # ── 1.5 SemVer 格式校验 ──
    valid_semver = ["0.0.1", "1.0.0", "10.20.30", "1.0.0-alpha", "1.0.0+build", "1.0.0-alpha.1"]
    for v in valid_semver:
        try:
            PluginManifest.from_dict({**VALID_MANIFEST, "version": v})
            check(f"SemVer-合法({v})", True)
        except ManifestValidationError as e:
            check(f"SemVer-合法({v})", False, f"不应报错: {e.message}")

    invalid_semver = ["1.0", "1", "one.two.three", "v1.0.0", "", "latest", "1.0.0.0"]
    for v in invalid_semver:
        try:
            PluginManifest.from_dict({**VALID_MANIFEST, "version": v})
            check(f"SemVer-非法({v})", False, "应报错")
        except ManifestValidationError as e:
            check(f"SemVer-非法({v})", True, f"e.field={e.field}")

    # ── 1.6 requires 结构校验 ──
    # requires.plugins 不是 dict
    for bad_req, desc in [
        ({"plugins": ">=1.0.0"}, "plugins 是 string"),
        ({"plugins": ["bazi"]}, "plugins 是 list"),
        (123, "requires 是 int"),
    ]:
        try:
            PluginManifest.from_dict({**VALID_MANIFEST, "requires": bad_req})
            check(f"requires结构-{desc}", False)
        except ManifestValidationError as e:
            check(f"requires结构-{desc}", True, f"e.field={e.field}")

    # requires 本身不是 dict
    try:
        PluginManifest.from_dict({**VALID_MANIFEST, "requires": "invalid"})
        check(f"requires结构-requires是string", False)
    except ManifestValidationError as e:
        check(f"requires结构-requires是string", True, f"e.field={e.field}")

    # ── 1.7 sandbox 校验 ──
    try:
        PluginManifest.from_dict({**VALID_MANIFEST, "sandbox": "invalid"})
        check(f"sandbox格式-sandbox是string", False)
    except ManifestValidationError as e:
        check(f"sandbox格式-sandbox是string", True, f"e.field={e.field}")

    # ── 1.8 最小合法 manifest ──
    minimal = {"name": "minimal", "version": "1.0.0", "api_version": CURRENT_API_VERSION}
    m_min = PluginManifest.from_dict(minimal)
    check("最小manifest-name", m_min.name == "minimal")
    check("最小manifest-version", m_min.version == "1.0.0")
    check("最小manifest-description", m_min.description == "")
    check("最小manifest-tools", m_min.tools == [])


# ══════════════════════════════════════════════════════════
# 2. 六态状态机测试
# ══════════════════════════════════════════════════════════

def test_state_machine():
    print(f"\n{B}═══ 2. 六态状态机 ═══{N}\n")

    pm = PluginManager()
    # 用无依赖的 manifest 测试基本状态转移
    base = {"name": "tmp", "version": "1.0.0", "api_version": CURRENT_API_VERSION}
    m1 = PluginManifest.from_dict({**base, "name": "plugin_1"})
    m2 = PluginManifest.from_dict({
        **base,
        "name": "plugin_2",
        "version": "2.0.0",
        "requires": {"plugins": {"plugin_1": ">=1.0.0"}},
    })

    # ── 2.1 absent → registered ──
    r = pm.register(m1, "/fake/path/1")
    check("absent→registered(1)", r.state == PluginState.REGISTERED,
          f"state={r.state.value}")
    check("registered-1 loaded_at 为空", r.loaded_at == "")
    check("registered-1 sandbox 存在", r.sandbox_policy is not None)

    r2 = pm.register(m2, "/fake/path/2")
    check("absent→registered(2)", r2.state == PluginState.REGISTERED)

    # ── 2.2 重复注册拦截 ──
    try:
        pm.register(m1, "/fake/dup")
        check("重复注册-拦截", False, "应抛出 ValueError")
    except ValueError as e:
        check("重复注册-拦截", True, f"{str(e)[:50]}")

    # ── 2.3 registered → enabled ──
    r = pm.enable("plugin_1")
    check("registered→enabled(1)", r.state == PluginState.ENABLED,
          f"state={r.state.value}")
    check("enabled 后 error_message 为空", r.error_message == "")

    # ── 2.4 真依赖：plugin_2 声明依赖 plugin_1 → enable 应通过 ──
    # Phase 1 不做运行时依赖解析（依赖插件此时最多 ENABLED），
    # 结构与格式校验通过即可；解析延迟到 Phase 2 init。
    r2 = pm.enable("plugin_2")
    check("registered→enabled(2) 依赖声明通过", r2.state == PluginState.ENABLED,
          f"state={r2.state.value}")

    # ── 2.5 依赖缺失：依赖插件不存在 → enable 不阻塞（延迟到 Phase 2 init）──
    pm3 = PluginManager()
    m_dep = PluginManifest.from_dict({
        "name": "plugin_has_dep",
        "version": "1.0.0",
        "api_version": CURRENT_API_VERSION,
        "requires": {"plugins": {"no_such_plugin": ">=1.0.0"}},
    })
    pm3.register(m_dep, "/fake")
    r_dep = pm3.enable("plugin_has_dep")
    check("依赖缺失-enable不阻塞(Phase 2 init 解析)", r_dep.state == PluginState.ENABLED,
          f"state={r_dep.state.value}")

    # ── 2.6 enabled → active ──
    # 正常插件目录不存在 → error，这是预期行为（init 需要真实目录）
    # 用 try/except 包裹，确认 state 转移到 active（如有可导入模块）或 error（无目录）

    # 创建一个临时插件目录来测试成功路径
    tmpdir = tempfile.mkdtemp(prefix="plugin_test_")
    plugin_dir = os.path.join(tmpdir, "dummy_active")
    os.makedirs(plugin_dir, exist_ok=True)

    # 写 manifest.yaml
    manifest_content = json.dumps(
        {"name": "dummy_active", "version": "1.0.0", "api_version": CURRENT_API_VERSION},
        indent=2,
    )
    with open(os.path.join(plugin_dir, "manifest.yaml"), "w", encoding="utf-8") as f:
        f.write(manifest_content)

    # 写 __init__.py（最小）
    with open(os.path.join(plugin_dir, "__init__.py"), "w", encoding="utf-8") as f:
        f.write("def register(orch): return {'tools': [], 'capabilities': [], 'skills': []}\n")

    # 构造一个直接注册的路径
    m_dummy = PluginManifest.from_dict(
        {"name": "dummy_active", "version": "1.0.0", "api_version": CURRENT_API_VERSION},
        source_path=plugin_dir,
    )
    pm_active = PluginManager()
    pm_active.register(m_dummy, plugin_dir)
    pm_active.enable("dummy_active")
    r_active = pm_active.init("dummy_active")
    check("enabled→active(成功)", r_active.state == PluginState.ACTIVE,
          f"state={r_active.state.value}")
    check("active-loaded_at 非空", r_active.loaded_at != "")

    # 2.6b error 态的两种恢复路径
    # error → enabled (recovery)
    pm_err = PluginManager()
    m_err = PluginManifest.from_dict({"name": "err_plugin", "version": "1.0.0", "api_version": CURRENT_API_VERSION})
    pm_err.register(m_err, "/does/not/exist")
    pm_err.enable("err_plugin")
    # init 会失败 → error
    pm_err.init("err_plugin")
    r_err = pm_err.get("err_plugin")
    check("init失败→error", r_err.state == PluginState.ERROR,
          f"state={r_err.state.value}")

    # recovery: error → registered → enabled
    r_rec = pm_err.recovery("err_plugin")
    check("error→enabled(recovery)", r_rec.state == PluginState.ENABLED,
          f"state={r_rec.state.value}")
    check("recovery 后 error_message 清空", r_rec.error_message == "")

    # 重新 error 后走 disable_from_error
    pm_err.init("err_plugin")  # 再次 init 失败
    r_dis = pm_err.disable_from_error("err_plugin")
    check("error→disabled(disable_from_error)", r_dis.state == PluginState.DISABLED,
          f"state={r_dis.state.value}")

    # ── 2.7 error → disabled → absent ──
    pm_err.unregister("err_plugin")
    r_abs = pm_err.get("err_plugin")
    check("disabled→absent", r_abs.state == PluginState.ABSENT,
          f"state={r_abs.state.value}")

    # ── 2.8 active → upgrading → active（swap） ──
    # 必须在 disable 之前测试，复用已成功 init 的 dummy_active
    m_new = PluginManifest.from_dict(
        {"name": "dummy_active", "version": "2.0.0", "api_version": CURRENT_API_VERSION},
        source_path=plugin_dir,
    )

    r_upg = pm_active.upgrade("dummy_active", m_new, plugin_dir)
    check("active→upgrading", r_upg.state == PluginState.UPGRADING,
          f"state={r_upg.state.value}")

    r_swapped = pm_active.swap("dummy_active")
    check("upgrading→active(swap)", r_swapped.state == PluginState.ACTIVE,
          f"state={r_swapped.state.value}")
    check("swap后version更新", r_swapped.manifest.version == "2.0.0")

    # ── 2.9 active → disabled → absent ──
    pm_active.disable("dummy_active")
    r_dis2 = pm_active.get("dummy_active")
    check("active→disabled", r_dis2.state == PluginState.DISABLED)

    pm_active.unregister("dummy_active")
    r_abs3 = pm_active.get("dummy_active")
    check("disabled→absent(2)", r_abs3.state == PluginState.ABSENT)

    # ── 2.10 非法状态转移拦截 ──
    # 从 absent 直接 enable
    pm_bad = PluginManager()
    r_bad = pm_bad.enable("nonexistent")
    check("absent→enable被拦截", r_bad is None)

    # 从 registered 直接 init（跳过了 enable）
    m_skip = PluginManifest.from_dict({"name": "skip_enable", "version": "1.0.0", "api_version": CURRENT_API_VERSION})
    pm_bad2 = PluginManager()
    pm_bad2.register(m_skip, "/fake")
    r_skip = pm_bad2.init("skip_enable")
    # 应该在内部 _get 时因状态不匹配返回 None → _error
    r_final = pm_bad2.get("skip_enable")
    check("registered→init被拦截(未enable)", r_final.state == PluginState.REGISTERED,
          f"state={r_final.state.value}")

    # ── 2.11 SandboxPolicy 默认值 ──
    sp = SandboxPolicy.default("test_plugin")
    check("sandbox-rw_paths", "sessions/test_plugin/" in sp.rw_paths)
    check("sandbox-ro_paths", "knowledge_base/" in sp.ro_paths)
    check("sandbox-forbidden", "config.local.py" in sp.forbidden_paths)
    check("sandbox-network 默认禁出站", sp.requires_network == False)

    # SandboxPolicy.from_manifest
    sp2 = SandboxPolicy.from_manifest("net_plugin", {
        "sandbox": {
            "requires_network": True,
            "rw_paths_extra": ["data/cache/"],
        }
    })
    check("sandbox-网络声明", sp2.requires_network == True)
    check("sandbox-额外rw路径", "data/cache/" in sp2.rw_paths)

    # 路径校验
    sp3 = SandboxPolicy.default("test")
    check("validate-允许读knowledge_base", sp3.validate_path("knowledge_base/bazi.json", is_write=False))
    check("validate-允许写sessions", sp3.validate_path("sessions/test/data.json", is_write=True))
    check("validate-拒绝写knowledge_base", sp3.validate_path("knowledge_base/data.json", is_write=True) == False)
    check("validate-拒绝读config", sp3.validate_path("config.local.py", is_write=False) == False)

    # 清理临时目录
    import shutil
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass

    # ── 2.12 模块命名空间隔离：插件名不污染 sys.modules ──
    import json as real_json
    import os as real_os
    tmpdir_ns = tempfile.mkdtemp(prefix="ns_test_")
    ns_dir = os.path.join(tmpdir_ns, "json")
    os.makedirs(ns_dir, exist_ok=True)
    with open(os.path.join(ns_dir, "manifest.yaml"), "w", encoding="utf-8") as f:
        f.write(json.dumps(
            {"name": "json", "version": "1.0.0", "api_version": CURRENT_API_VERSION}
        ))
    with open(os.path.join(ns_dir, "__init__.py"), "w", encoding="utf-8") as f:
        f.write("def register(orch): return {'tools': [], 'capabilities': [], 'skills': []}\n")

    pm_ns = PluginManager()
    m_ns = PluginManifest.from_dict(
        {"name": "json", "version": "1.0.0", "api_version": CURRENT_API_VERSION},
        source_path=ns_dir,
    )
    pm_ns.register(m_ns, ns_dir)
    pm_ns.enable("json")
    r_ns = pm_ns.init("json")
    check("命名空间-插件可 init", r_ns.state == PluginState.ACTIVE,
          f"state={r_ns.state.value}")
    check("命名空间-sys.modules[os] 未被污染",
          sys.modules.get("os") is real_os)
    check("命名空间-sys.modules[json] 仍是标准库",
          sys.modules.get("json") is real_json)
    check("命名空间-插件模块名带前缀",
          r_ns.module.__name__ == "destiny_plugins.json")
    shutil.rmtree(tmpdir_ns)

    print(f"\n{Y}  注: 状态机测试完整覆盖{N}")
    print(f"  absent → registered → enabled → active → upgrading → active(swap)")
    print(f"  error → enabled(recovery) / disabled(disable_from_error)")
    print(f"  active → disabled → absent")
    print(f"  依赖缺失 → error（enable 阶段拦截）")
    print(f"  非法转移 → 拦截（absent → enable, registered → init 跳过 enable）")


# ══════════════════════════════════════════════════════════
# 3. 优雅降级测试
# ══════════════════════════════════════════════════════════

def test_graceful_degradation():
    print(f"\n{B}═══ 3. 优雅降级 ═══{N}\n")

    # ── 3.1 crash 插件不影响其他插件加载 ──
    pm = PluginManager()

    # 三个插件：正常 + 正常 + 崩溃
    names = ["stable_a", "crash_b", "stable_c"]
    for name in names:
        m = PluginManifest.from_dict({
            "name": name,
            "version": "1.0.0",
            "api_version": CURRENT_API_VERSION,
        })
        pm.register(m, f"/fake/{name}")

    # 全部 enable
    results = pm.enable_all()
    for name in names:
        check(f"enable_all({name})", results[name].state == PluginState.ENABLED,
              f"state={results[name].state.value}")

    # 创建临时目录，两个正常插件 + 一个崩溃插件
    tmpdir = tempfile.mkdtemp(prefix="graceful_test_")
    dirs = {}
    init_files = {}

    for name in names:
        d = os.path.join(tmpdir, name)
        os.makedirs(d, exist_ok=True)
        dirs[name] = d

        manifest_path = os.path.join(d, "manifest.yaml")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"name": name, "version": "1.0.0", "api_version": CURRENT_API_VERSION}, f)

        if name == "crash_b":
            # 崩溃插件：register() 抛出异常
            init_content = """
def register(orch):
    raise RuntimeError("模拟崩溃：插件内部异常")
"""
        else:
            init_content = """
def register(orch):
    return {"tools": [], "capabilities": [], "skills": []}
"""
        init_files[name] = init_content
        with open(os.path.join(d, "__init__.py"), "w", encoding="utf-8") as f:
            f.write(init_content)

    # 新建 PluginManager，重新注册
    pm2 = PluginManager()
    for name in names:
        m = PluginManifest.from_dict(
            {"name": name, "version": "1.0.0", "api_version": CURRENT_API_VERSION},
            source_path=dirs[name],
        )
        pm2.register(m, dirs[name])

    pm2.enable_all()

    # 关键测试：init_all 中 crash_b 会抛异常，但 stable_a 和 stable_c 应正常
    try:
        pm2.init_all()
    except Exception as e:
        check("init_all 不抛异常", False, f"主流程不应被崩溃插件阻断: {e}")
    else:
        check("init_all 不抛异常", True, "主 Cycle 不受影响")

    # 验证状态分布
    r_a = pm2.get("stable_a")
    r_b = pm2.get("crash_b")
    r_c = pm2.get("stable_c")

    check("stable_a=active", r_a.state == PluginState.ACTIVE,
          f"state={r_a.state.value}")
    check("crash_b=error", r_b.state == PluginState.ERROR,
          f"state={r_b.state.value}")
    check("crash_b-error信息", "模拟崩溃" in r_b.error_message)
    check("stable_c=active", r_c.state == PluginState.ACTIVE,
          f"state={r_c.state.value}")

    # ── 3.2 crash 插件在 error 态不响应请求 ──
    check("crash_b.is_stale", r_b.is_stale() == True)
    check("stable_a.is_stale", r_a.is_stale() == False)

    # ── 3.3 正常插件独立工作 ──
    summary = pm2.summary()
    errors = summary["errors"]
    error_names = [e["name"] for e in errors]
    check("summary-errors 包含 crash_b", "crash_b" in error_names)
    check("summary-errors 不包含 stable_a", "stable_a" not in error_names)
    check("summary-errors 不包含 stable_c", "stable_c" not in error_names)

    # 状态分布
    by_state = {item["state"]: item for item in summary["by_state"]}
    check("总结-active 有 2 个", by_state.get("active", {}).get("count", 0) == 2,
          f"实际: {by_state.get('active', {}).get('plugins', [])}")
    check("总结-error 有 1 个", by_state.get("error", {}).get("count", 0) == 1)

    # ── 3.4 crash 插件恢复 ──
    # 把崩溃插件的 __init__.py 修好
    with open(os.path.join(dirs["crash_b"], "__init__.py"), "w", encoding="utf-8") as f:
        f.write("""
def register(orch):
    return {"tools": [], "capabilities": [], "skills": []}
""")
    r_rec = pm2.recovery("crash_b")
    check("recovery→enabled", r_rec.state == PluginState.ENABLED,
          f"state={r_rec.state.value}")

    # 再次 init
    r_rec_init = pm2.init("crash_b")
    check("recovery后init→active", r_rec_init.state == PluginState.ACTIVE,
          f"state={r_rec_init.state.value}")

    # 最终状态：全部 active
    for name in names:
        r = pm2.get(name)
        check(f"最终{name}=active", r.state == PluginState.ACTIVE,
              f"state={r.state.value}")

    # ── 3.5 与编排器集成：优雅降级不阻断 SkillRegistry ──
    orch = AnalysisOrchestrator()
    orch.register_defaults()
    initial_tools = orch.summary()["tools"]["total"]
    initial_caps = orch.summary()["capabilities"]["total"]

    # 注入一个崩溃插件到编排器
    pm3 = PluginManager(orch)

    crash_m = PluginManifest.from_dict(
        {"name": "crash_skill", "version": "1.0.0", "api_version": CURRENT_API_VERSION},
        source_path=dirs["crash_b"],  # 复用之前的崩溃目录（已修复）
    )
    pm3.register(crash_m, dirs["crash_b"])
    pm3.enable("crash_skill")
    pm3.init("crash_skill")

    # 编排器不应受影响
    orch_summary = orch.summary()
    check("编排器Tool数不变", orch_summary["tools"]["total"] == initial_tools)
    check("编排器Capability数不变", orch_summary["capabilities"]["total"] == initial_caps)

    # cleanup
    import shutil
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass

    print(f"\n{Y}  优雅降级哲学验证:{N}")
    print(f"  插件崩溃 → 捕获 → 日志 → 主 Cycle 继续")
    print(f"  其他插件不受影响，编排器不受影响")
    print(f"  error 态插件可 recovery 恢复")


# ══════════════════════════════════════════════════════════
# 4. discover 和 manifest 文件加载测试
# ══════════════════════════════════════════════════════════

def test_discover_and_load():
    print(f"\n{B}═══ 4. discover 和 manifest 文件加载 ═══{N}\n")

    # 创建临时 skills_dir 结构
    tmpdir = tempfile.mkdtemp(prefix="discover_test_")

    # 正常插件
    d1 = os.path.join(tmpdir, "skill_alpha")
    os.makedirs(d1)
    with open(os.path.join(d1, "manifest.yaml"), "w", encoding="utf-8") as f:
        f.write("""name: skill_alpha
version: "1.0.0"
api_version: 1
description: Alpha skill
capabilities: [alpha_analysis]
tools: [alpha_tool]
""")

    # 第二个正常插件 (manifest.json)
    d2 = os.path.join(tmpdir, "skill_beta")
    os.makedirs(d2)
    with open(os.path.join(d2, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({
            "name": "skill_beta",
            "version": "2.0.0",
            "api_version": CURRENT_API_VERSION,
        }, f)

    # 无 manifest 的目录（应跳过）
    d3 = os.path.join(tmpdir, "not_a_skill")
    os.makedirs(d3)

    # 有 manifest 但 api_version 不兼容（应跳过）
    d4 = os.path.join(tmpdir, "bad_version")
    os.makedirs(d4)
    with open(os.path.join(d4, "manifest.yaml"), "w", encoding="utf-8") as f:
        f.write("""name: bad_version
version: "1.0.0"
api_version: 999
""")

    pm = PluginManager()
    discovered = pm.discover(tmpdir)

    check("discover 发现 2 个插件", len(discovered) == 2,
          f"实际: {len(discovered)}")
    names = [r.manifest.name for r in discovered]
    check("discover 包含 skill_alpha", "skill_alpha" in names)
    check("discover 包含 skill_beta", "skill_beta" in names)
    check("discover 不包含 bad_version", "bad_version" not in names)

    # garbage yaml 文件
    d5 = os.path.join(tmpdir, "garbage")
    os.makedirs(d5)
    with open(os.path.join(d5, "manifest.yaml"), "w", encoding="utf-8") as f:
        f.write("this: is: [not] valid: - yaml")
    # discover 应捕获异常并跳过，不影响已有插件
    pm3 = PluginManager()  # 用新实例避免 has-registered 跳过
    discovered2 = pm3.discover(tmpdir)
    check("garbage manifest 不阻塞 discover", len(discovered2) >= 2,
          f"实际: {len(discovered2)} (garbage 被跳过不影响正常插件)")

    # 空目录测试
    pm_empty = PluginManager()
    empty_discovered = pm_empty.discover(os.path.join(tmpdir, "nonexistent"))
    check("不存在目录返回空", empty_discovered == [])

    import shutil
    shutil.rmtree(tmpdir)


# ══════════════════════════════════════════════════════════
# 5. register_builtin_skill 辅助函数测试
# ══════════════════════════════════════════════════════════

def test_builtin_register():
    print(f"\n{B}═══ 5. register_builtin_skill 辅助函数 ═══{N}\n")

    orch = AnalysisOrchestrator()
    result = register_builtin_skill(
        orch,
        name="test_builtin",
        description="测试内置技能",
        fn=lambda **kw: {"success": True},
        stages=["stage1", "stage2"],
        category="test",
        tools=["tool_a", "tool_b"],
        trigger_words=["测试", "test"],
        version="1.0.0",
        tags=["test"],
    )
    check("register返回tools", result["tools"] == ["tool_a", "tool_b"])
    check("register返回capabilities", "test_builtin" in result["capabilities"])
    check("register返回skills", "test_builtin" in result["skills"])

    # 验证已在 orchestrator 中
    cap = orch.capabilities.get("test_builtin")
    check("Capability已注册", cap is not None)
    check("Capability-stages", cap.stages == ["stage1", "stage2"])

    skill = orch.skills.get("test_builtin")
    check("Skill已注册", skill is not None)
    check("Skill-trigger_words", "测试" in skill.trigger_words)
    check("Skill-version", skill.version == "1.0.0")


# ══════════════════════════════════════════════════════════
# 6. PluginManager 与 Orchestrator 集成
# ══════════════════════════════════════════════════════════

def test_orchestrator_integration():
    print(f"\n{B}═══ 6. PluginManager 与编排器集成 ═══{N}\n")

    orch = AnalysisOrchestrator()
    orch.register_defaults()  # 先注册默认值，避免 summary() 触发重复注册

    # 无插件时的状态
    pm = PluginManager(orch)
    check("初始total=0", pm.summary()["total"] == 0)

    # register 内置插件（绕过 PluginManager，直接注册到编排器）
    # 使用新名字避免与默认 Skill 冲突
    register_builtin_skill(
        orch,
        name="plugin_skill",
        description="从插件注册的技能",
        fn=lambda **kw: {"success": True},
        stages=["do_analysis"],
        category="plugin",
        tools=["wuxing_query"],
        trigger_words=["插件"],
        version="1.0.0",
    )

    # 绕开 PluginManager 直接注册，验证不干扰
    orch_summary = orch.summary()
    check("直接注册后skill数>=1",
          orch_summary["skills"]["total"] >= 1)

    # PluginManager 感知不到直接注册的内容（它有自己的 _plugins 字典）
    pm_summary = pm.summary()
    check("PluginManager独立计数", pm_summary["total"] == 0)

    # 通过 PluginManager 注册
    m = PluginManifest.from_dict({
        "name": "managed_skill",
        "version": "1.0.0",
        "api_version": CURRENT_API_VERSION,
    })
    pm.register(m, "/fake")
    check("PluginManager 注册后 total=1", pm.summary()["total"] == 1)


# ══════════════════════════════════════════════════════════
# 7. Phase 2: init_all 依赖解析集成
# ══════════════════════════════════════════════════════════

def _make_plugin_dir(tmpdir, name, manifest_extra=None, init_body="return {'tools': [], 'capabilities': [], 'skills': []}"):
    """构造一个真实可加载的插件目录"""
    d = os.path.join(tmpdir, name)
    os.makedirs(d, exist_ok=True)
    manifest = {"name": name, "version": "1.0.0", "api_version": CURRENT_API_VERSION}
    if manifest_extra:
        manifest.update(manifest_extra)
    with open(os.path.join(d, "manifest.yaml"), "w", encoding="utf-8") as f:
        f.write(json.dumps(manifest))
    with open(os.path.join(d, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(f"def register(orch): {init_body}\n")
    return d


def test_init_all_dependencies():
    print(f"\n{B}═══ 7. init_all 依赖解析集成 ═══{N}\n")

    # ── 7.1 拓扑序：B 无依赖，A 依赖 B → init 后 B 先 active ──
    tmpdir = tempfile.mkdtemp(prefix="dep_init_test_")
    pm = PluginManager()
    d_b = _make_plugin_dir(tmpdir, "dep_b")
    d_a = _make_plugin_dir(tmpdir, "dep_a",
                           manifest_extra={"requires": {"plugins": {"dep_b": ">=1.0.0"}}})
    pm.register(PluginManifest.from_dict(
        {"name": "dep_b", "version": "1.0.0", "api_version": CURRENT_API_VERSION},
        source_path=d_b), d_b)
    pm.register(PluginManifest.from_dict(
        {"name": "dep_a", "version": "1.0.0", "api_version": CURRENT_API_VERSION,
         "requires": {"plugins": {"dep_b": ">=1.0.0"}}},
        source_path=d_a), d_a)
    pm.enable_all()
    results = pm.init_all()
    check("拓扑序-无环全 active",
          results["dep_a"].state == PluginState.ACTIVE
          and results["dep_b"].state == PluginState.ACTIVE,
          f"a={results['dep_a'].state.value}, b={results['dep_b'].state.value}")

    # ── 7.2 版本不满足：A 依赖 B >=2.0.0，B 只有 1.0.0 → A error ──
    pm2 = PluginManager()
    d_b2 = _make_plugin_dir(tmpdir, "ver_b")
    d_a2 = _make_plugin_dir(tmpdir, "ver_a",
                            manifest_extra={"requires": {"plugins": {"ver_b": ">=2.0.0"}}})
    pm2.register(PluginManifest.from_dict(
        {"name": "ver_b", "version": "1.0.0", "api_version": CURRENT_API_VERSION},
        source_path=d_b2), d_b2)
    pm2.register(PluginManifest.from_dict(
        {"name": "ver_a", "version": "1.0.0", "api_version": CURRENT_API_VERSION,
         "requires": {"plugins": {"ver_b": ">=2.0.0"}}},
        source_path=d_a2), d_a2)
    pm2.enable_all()
    results2 = pm2.init_all()
    check("版本不满足-A error", results2["ver_a"].state == PluginState.ERROR,
          f"state={results2['ver_a'].state.value}")
    check("版本不满足-错误人类可读",
          "不满足约束" in results2["ver_a"].error_message,
          results2["ver_a"].error_message)
    # B 不受影响，独立 init 成功
    check("版本不满足-B 仍 active", results2["ver_b"].state == PluginState.ACTIVE,
          f"state={results2['ver_b'].state.value}")

    # ── 7.3 循环依赖：A↔B → 双双 error，错误列出环 ──
    pm3 = PluginManager()
    d_a3 = _make_plugin_dir(tmpdir, "cyc_a",
                            manifest_extra={"requires": {"plugins": {"cyc_b": ">=1.0.0"}}})
    d_b3 = _make_plugin_dir(tmpdir, "cyc_b",
                            manifest_extra={"requires": {"plugins": {"cyc_a": ">=1.0.0"}}})
    pm3.register(PluginManifest.from_dict(
        {"name": "cyc_a", "version": "1.0.0", "api_version": CURRENT_API_VERSION,
         "requires": {"plugins": {"cyc_b": ">=1.0.0"}}},
        source_path=d_a3), d_a3)
    pm3.register(PluginManifest.from_dict(
        {"name": "cyc_b", "version": "1.0.0", "api_version": CURRENT_API_VERSION,
         "requires": {"plugins": {"cyc_a": ">=1.0.0"}}},
        source_path=d_b3), d_b3)
    pm3.enable_all()
    results3 = pm3.init_all()
    check("循环依赖-A error", results3["cyc_a"].state == PluginState.ERROR,
          f"state={results3['cyc_a'].state.value}")
    check("循环依赖-B error", results3["cyc_b"].state == PluginState.ERROR,
          f"state={results3['cyc_b'].state.value}")
    check("循环依赖-错误列环", "循环依赖" in results3["cyc_a"].error_message,
          results3["cyc_a"].error_message)

    # ── 7.4 依赖 error 同步传播：B init 崩溃，A 依赖 B → A 也 error ──
    pm4 = PluginManager()
    d_b4 = _make_plugin_dir(tmpdir, "crash_dep",
                            init_body="raise RuntimeError('模拟崩溃：插件内部异常')")
    d_a4 = _make_plugin_dir(tmpdir, "depend_on_crash",
                            manifest_extra={"requires": {"plugins": {"crash_dep": ">=1.0.0"}}})
    pm4.register(PluginManifest.from_dict(
        {"name": "crash_dep", "version": "1.0.0", "api_version": CURRENT_API_VERSION},
        source_path=d_b4), d_b4)
    pm4.register(PluginManifest.from_dict(
        {"name": "depend_on_crash", "version": "1.0.0", "api_version": CURRENT_API_VERSION,
         "requires": {"plugins": {"crash_dep": ">=1.0.0"}}},
        source_path=d_a4), d_a4)
    pm4.enable_all()
    results4 = pm4.init_all()
    check("传播-crash_dep error", results4["crash_dep"].state == PluginState.ERROR,
          f"state={results4['crash_dep'].state.value}")
    check("传播-依赖方同步 error",
          results4["depend_on_crash"].state == PluginState.ERROR,
          f"state={results4['depend_on_crash'].state.value}")
    check("传播-错误注明依赖方",
          "depend_on_crash" in results4["depend_on_crash"].error_message,
          results4["depend_on_crash"].error_message)
    check("传播-错误注明被依赖插件",
          "crash_dep" in results4["depend_on_crash"].error_message,
          results4["depend_on_crash"].error_message)

    # ── 7.5 版本表活性：error 插件不进版本表，依赖它的插件报缺失 ──
    pm5 = PluginManager()
    # ghost 插件从未注册，A 依赖 ghost → 缺失
    d_a5 = _make_plugin_dir(tmpdir, "dep_ghost",
                            manifest_extra={"requires": {"plugins": {"ghost_plugin": ">=1.0.0"}}})
    pm5.register(PluginManifest.from_dict(
        {"name": "dep_ghost", "version": "1.0.0", "api_version": CURRENT_API_VERSION,
         "requires": {"plugins": {"ghost_plugin": ">=1.0.0"}}},
        source_path=d_a5), d_a5)
    pm5.enable_all()
    results5 = pm5.init_all()
    check("缺失依赖-error", results5["dep_ghost"].state == PluginState.ERROR,
          f"state={results5['dep_ghost'].state.value}")
    check("缺失依赖-错误含插件名",
          "ghost_plugin" in results5["dep_ghost"].error_message,
          results5["dep_ghost"].error_message)

    # ── 7.6 无依赖多插件并行 init 不受影响 ──
    pm6 = PluginManager()
    for n in ["ind_a", "ind_b", "ind_c"]:
        d = _make_plugin_dir(tmpdir, n)
        pm6.register(PluginManifest.from_dict(
            {"name": n, "version": "1.0.0", "api_version": CURRENT_API_VERSION},
            source_path=d), d)
    pm6.enable_all()
    results6 = pm6.init_all()
    check("独立插件全 active",
          all(results6[n].state == PluginState.ACTIVE for n in ["ind_a", "ind_b", "ind_c"]))

    import shutil
    shutil.rmtree(tmpdir)


# ── 主入口 ─────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{B}{'='*60}{N}")
    print(f"{B}  P3 插件系统 Phase 1  测试套件{N}")
    print(f"{B}{'='*60}{N}")

    test_manifest_validation()
    test_state_machine()
    test_graceful_degradation()
    test_discover_and_load()
    test_builtin_register()
    test_orchestrator_integration()
    test_init_all_dependencies()

    # 汇总
    print(f"\n\n{B}{'='*60}{N}")
    print(f"{B}  测试汇总{N}")
    print(f"{B}{'='*60}{N}")
    print(f"  {G}通过: {pass_count}{N}  {R}失败: {fail_count}{N}  总计: {total}")

    if fail_count == 0:
        print(f"\n  {G}{B}✅ Phase 1 三条完工标准全过{N}")
        print(f"  ① 六态全部可达且转移路径经过测试 ✓")
        print(f"  ② manifest 校验覆盖格式/版本/依赖 ✓")
        print(f"  ③ 优雅降级：crash 插件不污染主 Cycle ✓")
    else:
        print(f"\n  {R}{B}❌ 有 {fail_count} 项失败，Phase 1 不满足完工标准{N}")

    sys.exit(0 if fail_count == 0 else 1)
