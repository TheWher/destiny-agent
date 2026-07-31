#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Flask 应用工厂"""

import os
import socket
import argparse
from flask import Flask

def get_local_ips() -> list[str]:
    """获取本机所有局域网 IPv4 地址"""
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            ips.append("127.0.0.1")
    return ips


def print_startup_info(port: int = 5000):
    """打印启动信息和访问地址"""
    ips = get_local_ips()
    print("=" * 60)
    print("  八字排盘 & 紫微斗数 Web 应用")
    print("=" * 60)
    print()
    print("  本地访问：")
    print(f"    http://localhost:{port}")
    print(f"    http://127.0.0.1:{port}")
    print()
    if ips:
        print("  局域网访问：")
        for ip in ips:
            print(f"    http://{ip}:{port}")
    print()
    print("=" * 60)
    print()


def create_app():
    """创建 Flask 应用实例，注册所有蓝图"""
    import os as _os
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    app = Flask(__name__, template_folder=_os.path.join(_root, "templates"), static_folder=_os.path.join(_root, "static"))

    # 注册蓝图
    from routes.pages import pages_bp
    from routes.bazi import bazi_bp
    from routes.ziwei import ziwei_bp
    from routes.charts import charts_bp
    from routes.auth import auth_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(bazi_bp)
    app.register_blueprint(ziwei_bp)
    app.register_blueprint(charts_bp)
    app.register_blueprint(auth_bp)

    # 启动时加载紫微会话
    from routes.ziwei import _ziwei_sessions, _load_sessions_from_disk
    _load_sessions_from_disk()

    return app


# 模块级 app 实例（兼容 WSGI）
app = create_app()




if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--no-debug", action="store_true")
    args = parser.parse_args()

    debug_mode = not args.no_debug
    print_startup_info(args.port)
    app.run(host=args.host, port=args.port, debug=debug_mode)
