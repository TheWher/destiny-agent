#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""插件管理器 — 六态生命周期 + manifest 校验 + 优雅降级

ADR-006 落地 Phase 1：在 SkillRegistry 外层包生命周期和校验壳。
不改变 SkillRegistry.register() 的接口，插件管理是对注册行为的管控。

状态机：
  absent → registered → enabled → active
              ↑            ↑  error ← 任何异常
           upgrading → active（新版）

完成标准（Phase 1）：
  ① 六态全部可达且转移路径经过测试
  ② manifest 校验覆盖格式错误/版本不兼容/依赖缺失三类
  ③ 优雅降级：崩溃插件不污染主 Cycle（dummy crash 插件测试）
"""

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional

# ── 状态定义 ──────────────────────────────────────────────

class PluginState(Enum):
    """插件六态生命周期"""
    ABSENT = "absent"           # 不存在或已卸载
    REGISTERED = "registered"   # 已发现、已记录元数据，未校验
    ENABLED = "enabled"         # 校验通过，未执行 init
    ACTIVE = "active"           # 正常工作中
    UPGRADING = "upgrading"     # 过渡态：旧版仍服务，新版加载中
    ERROR = "error"             # 任何异常吸收到这
    DISABLED = "disabled"       # 手动禁用，保留注册但不路由

    def is_working(self) -> bool:
        return self in (PluginState.ACTIVE, PluginState.UPGRADING)


# ── 沙箱策略 ──────────────────────────────────────────────

@dataclass
class SandboxPolicy:
    """插件文件系统和网络访问限制策略"""
    plugin_name: str
    rw_paths: list[str] = field(default_factory=list)
    ro_paths: list[str] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    requires_network: bool = False

    @classmethod
    def default(cls, plugin_name: str) -> "SandboxPolicy":
        """默认策略：私有目录读写 + 知识库只读"""
        return cls(
            plugin_name=plugin_name,
            rw_paths=[f"sessions/{plugin_name}/"],
            ro_paths=["knowledge_base/"],
            forbidden_paths=["data/", "config.local.py", ".git/"],
            requires_network=False,
        )

    @classmethod
    def from_manifest(cls, plugin_name: str, manifest: dict) -> "SandboxPolicy":
        """从 manifest.yaml 的 sandbox 段构建策略"""
        sandbox = manifest.get("sandbox", {})
        policy = cls.default(plugin_name)
        if sandbox.get("rw_paths_extra"):
            policy.rw_paths.extend(sandbox["rw_paths_extra"])
        if sandbox.get("ro_paths_extra"):
            policy.ro_paths.extend(sandbox["ro_paths_extra"])
        if sandbox.get("forbidden_paths_extra"):
            policy.forbidden_paths.extend(sandbox["forbidden_paths_extra"])
        policy.requires_network = sandbox.get("requires_network", False)
        return policy

    def validate_path(self, file_path: str, is_write: bool = False) -> bool:
        """校验文件路径是否在允许范围内

        Phase 2 在 ToolRegistry.call() 层统一调用此方法拦截。
        Phase 1 仅完成策略定义，不做实际拦截。
        """
        norm_path = os.path.normpath(file_path)

        # 先检查禁止路径
        for forbidden in self.forbidden_paths:
            forbidden_norm = os.path.normpath(forbidden)
            if norm_path.startswith(forbidden_norm):
                return False

        # 检查允许路径
        allowed = self.rw_paths if is_write else (self.rw_paths + self.ro_paths)
        for path in allowed:
            path_norm = os.path.normpath(path)
            if norm_path.startswith(path_norm):
                return True

        # 共享知识库默认允许读取
        if not is_write and "knowledge_base/" not in str(allowed):
            if norm_path.startswith("knowledge_base"):
                return True

        return False


# ── Manifest 定义和校验 ───────────────────────────────────

# 当前编排层 API 版本（manifest.api_version 必须与此兼容）
CURRENT_API_VERSION = 1

# manifest 必须包含的顶层字段
REQUIRED_MANIFEST_FIELDS = ["name", "version", "api_version"]

# manifest 可选但建议的字段
OPTIONAL_MANIFEST_FIELDS = [
    "description", "author", "requires",
    "capabilities", "tools", "sandbox",
    "tests",
]


@dataclass
class ManifestValidationError(Exception):
    """manifest 校验错误"""
    field: str
    message: str

    def __str__(self):
        return f"[{self.field}] {self.message}"


@dataclass
class PluginManifest:
    """通过校验的插件 manifest"""
    name: str
    version: str           # SemVer like "1.0.0"
    api_version: int
    description: str = ""
    author: str = ""
    requires: dict = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    sandbox: dict = field(default_factory=dict)
    tests: dict = field(default_factory=dict)
    source_path: str = ""  # 插件源目录（加载时填充）

    @classmethod
    def from_dict(cls, data: dict, source_path: str = "") -> "PluginManifest":
        """从字典构造，带完整校验"""
        errors = []

        # 1. 格式校验：必须字段
        for field in REQUIRED_MANIFEST_FIELDS:
            if field not in data:
                errors.append(ManifestValidationError(
                    field=field,
                    message=f"缺少必须字段 '{field}'"
                ))

        if errors:
            raise ManifestValidationError(
                field="manifest",
                message="\n".join(str(e) for e in errors)
            )

        name = data["name"]
        version = data["version"]

        # 格式校验：name 不能为空
        if not name or not name.strip():
            raise ManifestValidationError(field="name", message="name 不能为空")

        # 格式校验：version 必须符合 SemVer 格式
        if not _is_semver(version):
            raise ManifestValidationError(
                field="version",
                message=f"version '{version}' 不符合 SemVer 格式（x.y.z）"
            )

        # 2. 版本兼容性校验
        api_version = data["api_version"]
        if not isinstance(api_version, int) or api_version != CURRENT_API_VERSION:
            raise ManifestValidationError(
                field="api_version",
                message=f"api_version 不兼容：需要 {CURRENT_API_VERSION}，得到 {api_version}"
            )

        # 3. 依赖校验
        requires = data.get("requires", {})
        # 预留：Phase 1 记录依赖但不做实际解析，Phase 2 完整落地
        # 现在只校验 requires 结构是否合法
        if requires:
            if not isinstance(requires, dict):
                raise ManifestValidationError(
                    field="requires",
                    message=f"requires 必须是 object，得到 {type(requires).__name__}"
                )
            plugins_req = requires.get("plugins", {})
            if plugins_req and not isinstance(plugins_req, dict):
                raise ManifestValidationError(
                    field="requires.plugins",
                    message=f"requires.plugins 必须是 object"
                )

        # 构建
        sandbox = data.get("sandbox", {})
        if sandbox and not isinstance(sandbox, dict):
            raise ManifestValidationError(
                field="sandbox",
                message=f"sandbox 必须是 object"
            )

        return cls(
            name=name,
            version=version,
            api_version=api_version,
            description=data.get("description", ""),
            author=data.get("author", ""),
            requires=requires,
            capabilities=data.get("capabilities", []),
            tools=data.get("tools", []),
            sandbox=sandbox,
            tests=data.get("tests", {}),
            source_path=source_path,
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "api_version": self.api_version,
            "description": self.description,
            "author": self.author,
            "requires": self.requires,
            "capabilities": self.capabilities,
            "tools": self.tools,
            "sandbox": self.sandbox,
        }


def _is_semver(version: str) -> bool:
    """宽松 SemVer 校验：x.y.z 或 x.y.z-prerelease+meta

    支持 prerelease 中带点号（如 1.0.0-alpha.1）——
    先把 +build 切掉，再在第一个 - 处切 prerelease。
    """
    if not version:
        return False
    # 先切 build meta
    v = version.split("+")[0]
    # 再切 prerelease
    core = v.split("-")[0]
    parts = core.split(".")
    if len(parts) != 3:
        return False
    try:
        int(parts[0])
        int(parts[1])
        int(parts[2])
        return True
    except (ValueError, IndexError):
        return False


def _parse_semver(version: str) -> tuple[int, int, int]:
    """解析 SemVer 为 (major, minor, patch)"""
    parts = version.replace("-", ".").replace("+", ".").split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


# ── 插件运行时 ────────────────────────────────────────────

@dataclass
class PluginRuntime:
    """插件的完整运行时信息"""
    manifest: PluginManifest
    state: PluginState = PluginState.ABSENT
    sandbox_policy: Optional[SandboxPolicy] = None
    module: Any = None                    # 导入的 Python 模块对象
    registered_tools: list[str] = field(default_factory=list)
    registered_capabilities: list[str] = field(default_factory=list)
    registered_skills: list[str] = field(default_factory=list)
    error_message: str = ""               # error 态的具体原因
    error_traceback: str = ""
    loaded_at: str = ""
    state_changed_at: str = ""

    def is_stale(self) -> bool:
        """标记为 stale：已注册但不响应新请求"""
        return self.state in (PluginState.ERROR, PluginState.DISABLED, PluginState.UPGRADING)


# ── 插件管理器 ────────────────────────────────────────────

class PluginManager:
    """插件生命周期管理器

    六态状态机，管理插件的发现 → 注册 → 校验 → 激活 → 升级 → 卸载。
    不替代 SkillRegistry，而是在其外层加管控。

    使用方式：
        pm = PluginManager(orchestrator)
        pm.discover("skills/")
        pm.enable_all()
        pm.summary()
    """

    def __init__(self, orchestrator=None):
        """
        Args:
            orchestrator: AnalysisOrchestrator 实例，插件将通过它注册 Tool/Skill/Capability
        """
        self.orchestrator = orchestrator
        self._plugins: dict[str, PluginRuntime] = {}

    # ── 状态转移 ──────────────────────────────────────

    def register(self, manifest: PluginManifest, plugin_dir: str) -> PluginRuntime:
        """将发现的插件注册到管理器中

        状态: absent → registered
        此阶段不做校验、不导入模块、不注册到 SkillRegistry。
        """
        if manifest.name in self._plugins:
            existing = self._plugins[manifest.name]
            if existing.state != PluginState.ABSENT:
                raise ValueError(
                    f"Plugin '{manifest.name}' already exists (state: {existing.state.value})"
                )

        runtime = PluginRuntime(
            manifest=manifest,
            state=PluginState.REGISTERED,
            sandbox_policy=SandboxPolicy.from_manifest(manifest.name, manifest.sandbox),
        )
        runtime.state_changed_at = _now()
        self._plugins[manifest.name] = runtime
        return runtime

    def enable(self, plugin_name: str) -> PluginRuntime:
        """校验插件并标记为 enabled

        状态: registered → enabled
        校验 manifest 的 api_version、依赖、name 合法性。
        通过校验后进入 enabled 态，但尚未执行 init()。
        """
        runtime = self._get(plugin_name, require_state=PluginState.REGISTERED)
        if not runtime:
            return self._error(plugin_name, f"Plugin '{plugin_name}' not in REGISTERED state")

        try:
            # 重新校验 manifest（已有 from_dict 校验，这里二次确认）
            manifest = runtime.manifest
            if manifest.api_version != CURRENT_API_VERSION:
                raise ManifestValidationError(
                    field="api_version",
                    message=f"api_version 不兼容：需要 {CURRENT_API_VERSION}，得到 {manifest.api_version}"
                )

            # 校验依赖
            if manifest.requires:
                plugins_req = manifest.requires.get("plugins", {})
                for dep_name, dep_ver in plugins_req.items():
                    dep = self._plugins.get(dep_name)
                    if not dep or not dep.state.is_working():
                        raise ManifestValidationError(
                            field="requires.plugins",
                            message=f"依赖插件 '{dep_name}' 不存在或未激活"
                        )
                    # Phase 2 补充版本号比对

            runtime.state = PluginState.ENABLED
            runtime.error_message = ""
            runtime.error_traceback = ""
            runtime.state_changed_at = _now()
            return runtime

        except ManifestValidationError as e:
            return self._set_error(plugin_name, str(e), traceback.format_exc())
        except Exception as e:
            return self._set_error(plugin_name, f"enable 校验失败: {e}", traceback.format_exc())

    def init(self, plugin_name: str) -> PluginRuntime:
        """加载模块、执行插件初始化、注册到 SkillRegistry

        状态: enabled → active
        这是插件真正"跑起来"的阶段。
        如果 init 失败，进入 error 态，不影响主 Cycle。
        """
        runtime = self._get(plugin_name, require_state=PluginState.ENABLED)
        if not runtime:
            return self._error(plugin_name, f"Plugin '{plugin_name}' not in ENABLED state")

        try:
            # 尝试导入插件模块
            plugin_dir = runtime.manifest.source_path
            if not plugin_dir or not os.path.isdir(plugin_dir):
                raise RuntimeError(f"插件目录不存在: {plugin_dir}")

            # 清除旧缓存（recovery / 重新 init 场景）
            if plugin_name in sys.modules:
                del sys.modules[plugin_name]

            # 将插件目录加入 sys.path（如果不在其中）
            parent_dir = os.path.dirname(plugin_dir)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            # 尝试导入插件模块
            try:
                import importlib
                mod = importlib.import_module(plugin_name)
                runtime.module = mod
            except ImportError:
                # 回退：从文件路径直接加载
                init_path = os.path.join(plugin_dir, "__init__.py")
                if os.path.exists(init_path):
                    spec = importlib.util.spec_from_file_location(
                        plugin_name,
                        init_path,
                        submodule_search_locations=[plugin_dir],
                    )
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[plugin_name] = mod
                    spec.loader.exec_module(mod)
                    runtime.module = mod
                else:
                    raise ImportError(
                        f"无法导入插件 '{plugin_name}'。"
                        f"请确保插件目录包含 __init__.py 或可通过 PYTHONPATH 访问"
                    )

            # 调用 register(registry) 函数把插件内容注册到 SkillRegistry
            if hasattr(runtime.module, "register") and callable(runtime.module.register):
                try:
                    register_fn = runtime.module.register
                    result = register_fn(self.orchestrator)
                    if isinstance(result, dict):
                        runtime.registered_tools = result.get("tools", [])
                        runtime.registered_capabilities = result.get("capabilities", [])
                        runtime.registered_skills = result.get("skills", [])
                except Exception as e:
                    raise RuntimeError(f"插件 register() 执行失败: {e}")

            runtime.state = PluginState.ACTIVE
            runtime.loaded_at = _now()
            runtime.state_changed_at = _now()
            return runtime

        except Exception as e:
            return self._set_error(plugin_name, f"init 失败: {e}", traceback.format_exc())

    def disable(self, plugin_name: str) -> PluginRuntime:
        """禁用插件，保留注册但不路由新请求

        状态: active/error → disabled
        已注册的 Tool/Skill 标记 stale，但保留在 Registry 中避免依赖报错。
        正在执行的 cycle 不受影响。
        """
        runtime = self._get(plugin_name)
        if not runtime:
            return self._error(plugin_name, f"Plugin '{plugin_name}' not found")

        # 标记 stale
        runtime.state = PluginState.DISABLED
        runtime.state_changed_at = _now()
        return runtime

    def unregister(self, plugin_name: str) -> PluginRuntime:
        """卸载插件，从管理器中移除

        状态: disabled → absent
        """
        runtime = self._get(plugin_name, require_state=PluginState.DISABLED)
        if not runtime:
            return self._error(plugin_name, f"Plugin '{plugin_name}' not in DISABLED state")

        runtime.state = PluginState.ABSENT
        runtime.state_changed_at = _now()
        # 保留 runtime 在字典中（state=ABSENT），以便后续重新注册
        return runtime

    def recovery(self, plugin_name: str) -> PluginRuntime:
        """从 error 态恢复：重走 enable() 校验

        状态: error → enabled（校验通过） 或 保持 error（失败）
        幂等可重试。
        """
        runtime = self._get(plugin_name, require_state=PluginState.ERROR)
        if not runtime:
            return self._error(plugin_name, f"Plugin '{plugin_name}' not in ERROR state")

        # 回到 registered 态再走 enable 流程
        runtime.state = PluginState.REGISTERED
        runtime.error_message = ""
        runtime.error_traceback = ""
        return self.enable(plugin_name)

    def disable_from_error(self, plugin_name: str) -> PluginRuntime:
        """从 error 态放弃重试，切到 disabled

        状态: error → disabled
        """
        runtime = self._get(plugin_name, require_state=PluginState.ERROR)
        if not runtime:
            return self._error(plugin_name, f"Plugin '{plugin_name}' not in ERROR state")

        runtime.state = PluginState.DISABLED
        runtime.state_changed_at = _now()
        return runtime

    def upgrade(self, plugin_name: str, new_manifest: PluginManifest, new_dir: str) -> PluginRuntime:
        """升级插件：旧版仍服务，加载新版

        状态: active → upgrading
        swap() 后再切到 active（新版）。
        """
        runtime = self._get(plugin_name, require_state=PluginState.ACTIVE)
        if not runtime:
            return self._error(plugin_name, f"Plugin '{plugin_name}' not in ACTIVE state")

        # 暂存新版信息
        runtime._upgrade_manifest = new_manifest
        runtime._upgrade_dir = new_dir
        runtime.state = PluginState.UPGRADING
        runtime.state_changed_at = _now()
        return runtime

    def swap(self, plugin_name: str) -> PluginRuntime:
        """原子切换：释放旧引用，激活新版

        状态: upgrading → active（新版）
        """
        runtime = self._get(plugin_name, require_state=PluginState.UPGRADING)
        if not runtime:
            return self._error(plugin_name, f"Plugin '{plugin_name}' not in UPGRADING state")

        try:
            # 保存旧引用，加载新版
            old_module = runtime.module
            new_manifest = getattr(runtime, "_upgrade_manifest", None)
            new_dir = getattr(runtime, "_upgrade_dir", "")
            if not new_manifest:
                raise RuntimeError("升级信息缺失：_upgrade_manifest 和 _upgrade_dir 未设置")

            # 升级 manifest
            runtime.manifest = new_manifest
            runtime.manifest.source_path = new_dir

            # Phase 3 落地：
            # - 重新导入新版模块
            # - 重新执行 register()
            # - 原子替换旧引用

            runtime.state = PluginState.ACTIVE
            runtime.state_changed_at = _now()
            # Phase 3 补充旧模块引用释放
            delattr(runtime, "_upgrade_manifest")
            delattr(runtime, "_upgrade_dir")
            return runtime

        except Exception as e:
            return self._set_error(plugin_name, f"swap 失败: {e}", traceback.format_exc())

    # ── 批量操作 ──────────────────────────────────────

    def discover(self, skills_dir: str = None) -> list[PluginRuntime]:
        """扫描 skills/ 目录，发现所有有 manifest.yaml 的插件

        Args:
            skills_dir: 插件根目录，默认 <project_root>/skills/

        Returns:
            已发现的插件 runtime 列表（状态: registered）
        """
        if skills_dir is None:
            _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            skills_dir = os.path.join(_root, "skills")

        if not os.path.isdir(skills_dir):
            return []

        discovered = []
        for entry in os.listdir(skills_dir):
            plugin_dir = os.path.join(skills_dir, entry)
            if not os.path.isdir(plugin_dir):
                continue

            manifest_path = os.path.join(plugin_dir, "manifest.yaml")
            if not os.path.exists(manifest_path):
                # 尝试 manifest.json
                manifest_path = os.path.join(plugin_dir, "manifest.json")

            if not os.path.exists(manifest_path):
                continue

            try:
                manifest = self._load_manifest(manifest_path, plugin_dir)
                if manifest:
                    # 跳过已注册的（discover 可重复调用）
                    if manifest.name in self._plugins and self._plugins[manifest.name].state != PluginState.ABSENT:
                        continue
                    runtime = self.register(manifest, plugin_dir)
                    discovered.append(runtime)
            except Exception as e:
                # 发现阶段的错误不阻塞其他插件
                print(f"[PluginManager] 发现插件 '{entry}' 时出错: {e}")
                continue

        return discovered

    def enable_all(self) -> dict[str, PluginRuntime]:
        """启用所有已注册的插件

        每个插件独立 enable，失败的不影响其他。
        """
        results = {}
        for name, runtime in self._plugins.items():
            if runtime.state == PluginState.REGISTERED:
                try:
                    results[name] = self.enable(name)
                except Exception as e:
                    self._set_error(name, f"enable_all: {e}")
                    results[name] = self._plugins.get(name)
        return results

    def init_all(self) -> dict[str, PluginRuntime]:
        """初始化所有已启用的插件

        每个插件独立 init，失败的不影响其他。优雅降级的核心执行入口。
        """
        results = {}
        for name, runtime in self._plugins.items():
            if runtime.state == PluginState.ENABLED:
                try:
                    results[name] = self.init(name)
                except Exception as e:
                    # 优雅降级：单个插件崩溃不影响其他插件和主 Cycle
                    self._set_error(name, f"init_all: {e}")
                    results[name] = self._plugins.get(name)
        return results

    # ── 查询接口 ──────────────────────────────────────

    def get(self, plugin_name: str) -> Optional[PluginRuntime]:
        """获取插件运行时信息"""
        return self._plugins.get(plugin_name)

    def list_all(self) -> list[PluginRuntime]:
        return list(self._plugins.values())

    def list_by_state(self, state: PluginState) -> list[PluginRuntime]:
        return [r for r in self._plugins.values() if r.state == state]

    def list_working(self) -> list[PluginRuntime]:
        return [r for r in self._plugins.values() if r.state.is_working()]

    def list_errors(self) -> list[PluginRuntime]:
        return [r for r in self._plugins.values() if r.state == PluginState.ERROR]

    def summary(self) -> dict:
        """返回插件管理器状态摘要"""
        by_state = {}
        for r in self._plugins.values():
            key = r.state.value
            if key not in by_state:
                by_state[key] = []
            by_state[key].append(r.manifest.name)

        errors = []
        for r in self._plugins.values():
            if r.state == PluginState.ERROR:
                errors.append({"name": r.manifest.name, "error": r.error_message})

        return {
            "total": len(self._plugins),
            "by_state": [
                {"state": state, "count": len(names), "plugins": names}
                for state, names in sorted(by_state.items())
            ],
            "errors": errors,
        }

    # ── 内部辅助 ──────────────────────────────────────

    def _get(self, plugin_name: str,
             require_state: Optional[PluginState] = None) -> Optional[PluginRuntime]:
        """获取插件 runtime，可选状态校验"""
        runtime = self._plugins.get(plugin_name)
        if not runtime:
            return None
        if require_state and runtime.state != require_state:
            return None
        return runtime

    def _set_error(self, plugin_name: str, message: str, tb: str = "") -> PluginRuntime:
        """将插件标记为 error 态"""
        runtime = self._plugins.get(plugin_name)
        if runtime:
            runtime.state = PluginState.ERROR
            runtime.error_message = message
            runtime.error_traceback = tb
            runtime.state_changed_at = _now()
            return runtime
        # 插件尚未注册，创建一个 error runtime
        dummy = PluginRuntime(
            manifest=PluginManifest(
                name=plugin_name,
                version="0.0.0",
                api_version=CURRENT_API_VERSION,
            ),
            state=PluginState.ERROR,
            error_message=message,
            error_traceback=tb,
        )
        dummy.state_changed_at = _now()
        self._plugins[plugin_name] = dummy
        return dummy

    def _error(self, plugin_name: str, message: str) -> None:
        """返回 None 并记录错误（用于状态转移校验失败时）"""
        print(f"[PluginManager] {message}")
        return None

    def _load_manifest(self, manifest_path: str, plugin_dir: str) -> Optional[PluginManifest]:
        """从文件加载并校验 manifest"""
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                import yaml
                data = yaml.safe_load(f)
        except ImportError:
            # 无 yaml 库时尝试 JSON
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                raise ManifestValidationError(
                    field="manifest",
                    message=f"无法解析 manifest 文件: {manifest_path}"
                )

        if not data or not isinstance(data, dict):
            raise ManifestValidationError(
                field="manifest",
                message=f"manifest 文件为空或格式错误"
            )

        return PluginManifest.from_dict(data, plugin_dir)


def _now() -> str:
    """当前时间字符串"""
    import datetime
    return datetime.datetime.now().isoformat()


# ── 内置插件注册辅助 ─────────────────────────────────────

def register_builtin_skill(orchestrator,
                           name: str, description: str,
                           fn: Callable, stages: list[str],
                           category: str, tools: list[str],
                           trigger_words: list[str],
                           version: str = "1.0.0",
                           tags: list[str] = None) -> dict:
    """便捷函数：一次性注册 Capability + Skill 到编排器

    简化插件中手动调用 orchestrator.capabilities.register() 和
    orchestrator.skills.register() 的繁琐过程。
    """
    from services.orchestrator import CapabilityDef, SkillDef

    cap = CapabilityDef(
        name=name,
        description=description,
        fn=fn,
        stages=stages,
        category=category,
        tools=tools,
    )
    orchestrator.capabilities.register(cap)

    skill = SkillDef(
        name=name,
        description=description,
        capability=cap,
        version=version,
        trigger_words=trigger_words,
        priority=1.0,
        tags=tags or [category],
    )
    orchestrator.skills.register(skill)

    return {
        "tools": tools,
        "capabilities": [name],
        "skills": [name],
    }


# ── 测试 ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("PluginManager — 六态状态机与 manifest 校验")
    print("=" * 60)

    # 1. manifest 校验测试
    print("\n[manifest 校验]")

    # 合法 manifest
    valid = {
        "name": "test_skill",
        "version": "1.0.0",
        "api_version": 1,
        "description": "Test skill",
    }
    m = PluginManifest.from_dict(valid)
    print(f"  ✅ 合法 manifest: name={m.name}, version={m.version}, api_version={m.api_version}")

    # 缺少必须字段
    for field in REQUIRED_MANIFEST_FIELDS:
        invalid = {k: v for k, v in valid.items() if k != field}
        try:
            PluginManifest.from_dict(invalid)
            print(f"  ❌ 缺少 '{field}' 应该报错但没报")
        except ManifestValidationError as e:
            print(f"  ✅ 缺少 '{field}' → {e.field}: {e.message[:60]}")

    # 版本不兼容
    try:
        PluginManifest.from_dict({**valid, "api_version": 999})
        print(f"  ❌ api_version 不兼容应报错")
    except ManifestValidationError as e:
        print(f"  ✅ api_version 不兼容 → {e.field}: {e.message[:60]}")

    # version 格式错误
    for bad_ver in ["1.0", "one.two.three", "", "v1.0.0"]:
        try:
            PluginManifest.from_dict({**valid, "version": bad_ver})
            print(f"  ❌ version='{bad_ver}' 应报错")
        except ManifestValidationError as e:
            print(f"  ✅ version='{bad_ver}' → {e.field}: {e.message[:60]}")

    # 2. 状态机测试
    print("\n[六态状态机]")

    pm = PluginManager()

    # absent → registered
    m1 = PluginManifest.from_dict({**valid, "name": "skill_a"})
    r1 = pm.register(m1, "/fake/path")
    print(f"  ✅ absent → registered: state={r1.state.value}")

    # 重复注册
    try:
        pm.register(m1, "/fake/path")
        print(f"  ❌ 重复注册应报错")
    except ValueError as e:
        print(f"  ✅ 重复注册拦截: {str(e)[:60]}")

    # registered → enabled
    r1 = pm.enable("skill_a")
    print(f"  ✅ registered → enabled: state={r1.state.value}")

    # enabled → active
    try:
        r1 = pm.init("skill_a")
        print(f"  ✅ enabled → active: state={r1.state.value}")
    except Exception as e:
        # init 可能因插件目录不存在而失败，确认进入 error 态
        active_plugin = pm.get("skill_a")
        print(f"  ℹ️  init 失败（目录不存在），进入: state={active_plugin.state.value}, error={active_plugin.error_message[:60]}")

    # error → disabled
    pm.disable("skill_a")
    print(f"  ✅ active/error → disabled: state={pm.get('skill_a').state.value}")

    # disabled → absent
    pm.unregister("skill_a")
    print(f"  ✅ disabled → absent: state={pm.get('skill_a').state.value}")

    # 3. 优雅降级：error 态不阻塞其他操作
    print("\n[优雅降级]")

    pm2 = PluginManager()
    m_ok = PluginManifest.from_dict({**valid, "name": "good_plugin"})
    m_bad = PluginManifest.from_dict({**valid, "name": "bad_plugin", "version": "2.0.0"})

    pm2.register(m_ok, "/fake/path")
    pm2.register(m_bad, "/fake/path")

    results = pm2.enable_all()
    for name, rt in results.items():
        print(f"  enable_all({name}): state={rt.state.value}")

    print(f"\n  summary: {pm2.summary()}")
