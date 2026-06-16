# -*- coding: utf-8 -*-
# Windows 终端 UTF-8 支持
import sys as _sys
if _sys.platform == "win32":
    try:
        import subprocess as _sp
        _sp.run(["chcp", "65001"], capture_output=True, timeout=2)
    except Exception:
        pass

"""
MathModelPro 统一启动器 v4.0

用法: python launcher.py [命令] [选项]

命令:
  start      启动全部服务（默认）
  stop       停止全部服务
  restart    重启全部服务
  status     查看服务状态
  check      检查环境和依赖
  backend    仅启动后端
  frontend   仅启动前端
  open       打开浏览器访问前端
  dev        开发模式（前后端同时启动，实时日志）

选项:
  --auto, -a          自动模式（跳过交互确认）
  --no-browser        不自动打开浏览器
  --port-backend N    指定后端端口（默认 8001）
  --port-frontend N   指定前端端口（默认 5173）

示例:
  python launcher.py                        # 启动全部服务
  python launcher.py start --no-browser     # 启动但不打开浏览器
  python launcher.py stop                   # 停止全部服务
  python launcher.py restart                # 重启全部服务
  python launcher.py check                  # 环境检查
  python launcher.py backend                # 仅启动后端
"""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
import platform
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.absolute()
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
VENV_PYTHON = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
LOG_DIR = BASE_DIR / ".logs"
PID_FILE = BASE_DIR / ".running_pids.json"

DEFAULT_BACKEND_PORT = 8001
DEFAULT_FRONTEND_PORT = 5173

# 运行时选项（由命令行参数设置）
AUTO_MODE = False
NO_BROWSER = False
BACKEND_PORT = DEFAULT_BACKEND_PORT
FRONTEND_PORT = DEFAULT_FRONTEND_PORT


# ── 工具函数 ──────────────────────────────────────────────

def log(msg: str, end: str = "\n"):
    """打印消息（立即刷新，保证实时输出，兼容 GBK 终端）"""
    try:
        print(msg, end=end, flush=True)
    except UnicodeEncodeError:
        # GBK 终端无法显示 emoji，替换为 ASCII
        safe = msg.encode("gbk", errors="replace").decode("gbk")
        print(safe, end=end, flush=True)


def find_program(name: str) -> str | None:
    """在 PATH 和常见位置中查找可执行程序"""
    # 1. 先查 PATH
    exts = [""] if platform.system() != "Windows" else ["", ".exe", ".cmd", ".bat"]
    for ext in exts:
        found = shutil.which(name + ext)
        if found:
            return found

    # 2. Windows 常见位置
    if platform.system() == "Windows":
        candidates = [
            os.path.expandvars(r"%APPDATA%\npm\{}.cmd").format(name),
            os.path.expandvars(r"%APPDATA%\npm\{}").format(name),
            os.path.expandvars(r"%LOCALAPPDATA%\pnpm\{}.exe").format(name),
            os.path.expandvars(r"%ProgramFiles%\nodejs\{}.cmd").format(name),
            os.path.expandvars(r"%ProgramFiles%\nodejs\{}.exe").format(name),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
    return None


def get_env() -> dict:
    """获取注入完整 PATH 的子进程环境变量"""
    env = os.environ.copy()
    extra = [
        os.path.expandvars(r"%APPDATA%\npm"),
        os.path.expandvars(r"%LOCALAPPDATA%\pnpm"),
    ]
    current_path = env.get("PATH", "")
    for p in extra:
        if os.path.isdir(p) and p not in current_path:
            current_path = p + os.pathsep + current_path
    env["PATH"] = current_path
    return env


def check_port(port: int) -> bool:
    """检查端口是否可用（可用=True，占用=False）"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) != 0
    except Exception:
        return False


def find_pid_on_port(port: int) -> str:
    """查找占用端口的进程 PID"""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    return parts[-1] if parts else ""
        else:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def kill_pid(pid: str):
    """强制终止进程"""
    if not pid:
        return
    try:
        if platform.system() == "Windows":
            subprocess.run(
                ["taskkill", "/PID", pid, "/F"],
                capture_output=True, timeout=5,
            )
        else:
            subprocess.run(["kill", "-9", pid], capture_output=True, timeout=5)
    except Exception:
        pass


def kill_by_window_title(title: str):
    """根据窗口标题终止进程（Windows 专用）"""
    if platform.system() != "Windows":
        return
    try:
        subprocess.run(
            ["taskkill", "/FI", f"WINDOWTITLE eq {title}", "/F"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


def read_json(path: Path) -> dict:
    """安全读取 JSON"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, data: dict):
    """安全写入 JSON"""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def url_get(url: str, timeout: int = 3) -> tuple[int, str]:
    """HTTP GET 请求，返回 (状态码, 内容)"""
    try:
        import urllib.request
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)


def wait_for_port(port: int, timeout_sec: int = 30) -> bool:
    """等待端口被占用（即服务启动成功）"""
    for _ in range(timeout_sec * 2):
        if not check_port(port):  # 端口被占用 = 服务已启动
            return True
        time.sleep(0.5)
        log(".", end="")
    return False


# ── 横幅 ──────────────────────────────────────────────────

def print_banner():
    """打印启动横幅"""
    banner = r"""
╔════════════════════════════════════════════╗
║       MathModelPro Launcher v4.0           ║
║     AI 驱动的数学建模协作平台               ║
╚════════════════════════════════════════════╝
"""
    log(banner)


def print_section(title: str):
    """打印分隔标题"""
    log(f"\n{'─' * 50}")
    log(f"  {title}")
    log(f"{'─' * 50}")


# ── 环境检查 ──────────────────────────────────────────────

def check_environment() -> bool:
    """检查运行环境，返回是否通过"""
    print_banner()
    print_section("环境检查")

    python_exe = VENV_PYTHON if VENV_PYTHON.exists() else sys.executable

    # 1. Python
    try:
        result = subprocess.run(
            [str(python_exe), "--version"], capture_output=True, text=True, timeout=10
        )
        log(f"  ✅ Python: {result.stdout.strip()}")
        if VENV_PYTHON.exists():
            log(f"     虚拟环境: {VENV_PYTHON}")
    except Exception:
        log("  ❌ Python: 未找到!")
        return False

    # 2. 后端依赖
    log("")
    log("  后端依赖检查...")
    required = ["fastapi", "uvicorn", "sqlalchemy", "loguru", "httpx", "pydantic"]
    missing = []

    for dep in required:
        try:
            result = subprocess.run(
                [str(python_exe), "-c", f"import {dep}"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                log(f"    ✅ {dep}")
            else:
                missing.append(dep)
                log(f"    ❌ {dep}: 未安装")
        except subprocess.TimeoutExpired:
            missing.append(dep)
            log(f"    ⏱️ {dep}: 导入超时")
        except Exception as e:
            missing.append(dep)
            log(f"    ❌ {dep}: {e}")

    # 可选依赖
    for dep in ["litellm"]:
        try:
            result = subprocess.run(
                [str(python_exe), "-c", f"import {dep}"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                log(f"    ✅ {dep}")
            else:
                log(f"    ⚠️ {dep}: 已安装但导入慢")
        except subprocess.TimeoutExpired:
            log(f"    ⚠️ {dep}: 已安装（导入超时，运行时可正常使用）")
        except Exception:
            log(f"    ⚠️ {dep}: 未安装（可选）")

    if missing:
        log(f"\n  ⚠️ 缺少依赖: {', '.join(missing)}")
        if AUTO_MODE or _confirm("  是否自动安装缺失的依赖？"):
            log("  正在安装后端依赖...")
            req_file = BACKEND_DIR / "requirements.txt"
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "install", "-r", str(req_file), "-q"],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                log("  ✅ 依赖安装完成")
                return True
            else:
                log(f"  ❌ 安装失败: {result.stderr[-200:]}")
                return False
        else:
            log(f"  请手动安装: cd backend && venv\\Scripts\\pip install {' '.join(missing)}")
            return False

    # 3. Node.js
    node = find_program("node")
    if node:
        try:
            result = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10)
            log(f"\n  ✅ Node.js: {result.stdout.strip()}")
        except Exception:
            log("\n  ❌ Node.js: 执行失败")
    else:
        log("\n  ❌ Node.js: 未找到！请安装 https://nodejs.org")
        return False

    # 4. 包管理器（pnpm > npm）
    pnpm = find_program("pnpm")
    npm = find_program("npm")
    pkg_manager = None
    if pnpm:
        pkg_manager = pnpm
        try:
            result = subprocess.run([pnpm, "--version"], capture_output=True, text=True, timeout=10)
            log(f"  ✅ pnpm: {result.stdout.strip()}")
        except Exception:
            log(f"  ⚠️ pnpm: 找到但无法执行 ({pnpm})")
            pkg_manager = None
    if not pkg_manager and npm:
        pkg_manager = npm
        try:
            result = subprocess.run([npm, "--version"], capture_output=True, text=True, timeout=10)
            log(f"  ✅ npm: {result.stdout.strip()} (pnpm 未安装，回退到 npm)")
        except Exception:
            log(f"  ❌ npm: 找到但无法执行")
            return False
    if not pkg_manager:
        log("  ❌ 未找到 pnpm 或 npm！请安装 Node.js 后重试")
        return False

    # 5. 前端依赖
    node_modules = FRONTEND_DIR / "node_modules"
    if node_modules.exists():
        log(f"  ✅ node_modules: 已安装")
    else:
        log(f"  ⚠️ node_modules: 未安装")
        if AUTO_MODE or _confirm("  是否自动安装前端依赖？"):
            log("  正在安装前端依赖（可能需要几分钟）...")
            cmd = [pkg_manager, "install"]
            result = subprocess.run(
                cmd, cwd=str(FRONTEND_DIR), env=get_env(),
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                log("  ✅ 前端依赖安装完成")
            else:
                log(f"  ❌ 安装失败，请手动运行: cd frontend && {pkg_manager} install")
                return False
        else:
            log(f"  请手动安装: cd frontend && {pkg_manager} install")
            return False

    # 6. 配置文件
    log("")
    config_path = BACKEND_DIR / "data" / "config.json"
    if config_path.exists():
        log(f"  ✅ 配置文件: data/config.json")
    else:
        config_path = BACKEND_DIR / "config.json"
        if config_path.exists():
            log(f"  ✅ 配置文件: config.json")
        else:
            log(f"  ⚠️ 配置文件不存在，将使用默认配置")

    # 7. 端口状态
    log("\n  端口状态:")
    for port, name in [(BACKEND_PORT, "后端"), (FRONTEND_PORT, "前端")]:
        if check_port(port):
            log(f"    ✅ {name} ({port}): 可用")
        else:
            pid = find_pid_on_port(port)
            log(f"    ⚠️ {name} ({port}): 被占用 (PID: {pid})")

    print_section("环境检查完成")
    return True


# ── 服务管理 ──────────────────────────────────────────────

def start_backend() -> subprocess.Popen | None:
    """启动后端服务"""
    print_section("启动后端")

    # 端口冲突处理
    if not check_port(BACKEND_PORT):
        pid = find_pid_on_port(BACKEND_PORT)
        log(f"⚠️ 端口 {BACKEND_PORT} 已被占用 (PID: {pid})")
        if AUTO_MODE or _confirm("  是否终止该进程并重新启动？"):
            kill_pid(pid)
            time.sleep(1)
            if not check_port(BACKEND_PORT):
                log(f"❌ 无法释放端口 {BACKEND_PORT}，跳过启动")
                return None
        else:
            log("  跳过后端启动")
            return None

    python_exe = VENV_PYTHON if VENV_PYTHON.exists() else sys.executable
    if not VENV_PYTHON.exists():
        log("⚠️ 虚拟环境不存在，使用系统 Python")

    LOG_DIR.mkdir(exist_ok=True)
    backend_log = LOG_DIR / "backend.log"

    try:
        with open(backend_log, "w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                [
                    str(python_exe), "-m", "uvicorn", "main:app",
                    "--host", "127.0.0.1", "--port", str(BACKEND_PORT),
                    "--log-level", "warning",
                ],
                cwd=str(BACKEND_DIR),
                env=get_env(),
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )

        # 保存 PID
        pids = read_json(PID_FILE)
        pids["backend"] = process.pid
        write_json(PID_FILE, pids)

        # 等待启动
        log("  等待后端启动...", end="")
        if wait_for_port(BACKEND_PORT, timeout_sec=30):
            log(" ✅")
            log(f"  后端地址: http://127.0.0.1:{BACKEND_PORT}")
            log(f"  健康检查: http://127.0.0.1:{BACKEND_PORT}/health")
            log(f"  API 文档: http://127.0.0.1:{BACKEND_PORT}/docs")
            return process
        else:
            log(" ❌ 超时")
            if backend_log.exists():
                log(f"  查看日志: {backend_log}")
                lines = backend_log.read_text(encoding="utf-8").split("\n")[-5:]
                for line in lines:
                    if line.strip():
                        log(f"    {line.strip()}")
            return None

    except Exception as e:
        log(f"❌ 启动失败: {e}")
        return None


def start_frontend() -> subprocess.Popen | None:
    """启动前端服务"""
    print_section("启动前端")

    # 查找包管理器
    pnpm = find_program("pnpm")
    npm = find_program("npm")
    pkg_manager = pnpm or npm
    if not pkg_manager:
        log("❌ 未找到 pnpm 或 npm！")
        log("  安装 Node.js: https://nodejs.org")
        return None

    pm_name = "pnpm" if pnpm else "npm"

    # 检查 node_modules
    if not (FRONTEND_DIR / "node_modules").exists():
        log(f"  node_modules 不存在，正在安装依赖...")
        result = subprocess.run(
            [pkg_manager, "install"],
            cwd=str(FRONTEND_DIR),
            env=get_env(),
            capture_output=True,
            timeout=300,
        )
        if result.returncode != 0:
            log(f"  ❌ 依赖安装失败")
            return None
        log(f"  ✅ 依赖安装完成")

    # 端口冲突处理
    if not check_port(FRONTEND_PORT):
        pid = find_pid_on_port(FRONTEND_PORT)
        log(f"⚠️ 端口 {FRONTEND_PORT} 已被占用 (PID: {pid})")
        if AUTO_MODE or _confirm("  是否终止该进程并重新启动？"):
            kill_pid(pid)
            time.sleep(1)
            if not check_port(FRONTEND_PORT):
                log(f"❌ 无法释放端口 {FRONTEND_PORT}，跳过启动")
                return None
        else:
            log("  跳过前端启动")
            return None

    LOG_DIR.mkdir(exist_ok=True)
    frontend_log = LOG_DIR / "frontend.log"

    try:
        with open(frontend_log, "w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                [pkg_manager, "run", "dev"],
                cwd=str(FRONTEND_DIR),
                env=get_env(),
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )

        # 保存 PID
        pids = read_json(PID_FILE)
        pids["frontend"] = process.pid
        write_json(PID_FILE, pids)

        # 等待启动
        log("  等待前端启动...", end="")
        if wait_for_port(FRONTEND_PORT, timeout_sec=40):
            log(" ✅")
            log(f"  前端地址: http://localhost:{FRONTEND_PORT}")
            return process
        else:
            log(" ⚠️ 超时（可能仍在编译中）")
            if frontend_log.exists():
                log(f"  查看日志: {frontend_log}")
            return process  # 前端 Vite 可能较慢，不强制失败

    except Exception as e:
        log(f"❌ 启动失败: {e}")
        return None


def stop_services():
    """停止所有服务"""
    print_section("停止服务")

    # 方式 1: 通过 PID 文件
    pids = read_json(PID_FILE)
    for name, label in [("backend", "后端"), ("frontend", "前端")]:
        pid = pids.get(name)
        if pid:
            kill_pid(str(pid))
            log(f"  ✅ {label} 已停止 (PID: {pid})")

    # 方式 2: 通过端口
    for port, label in [(BACKEND_PORT, "后端"), (FRONTEND_PORT, "前端")]:
        pid = find_pid_on_port(port)
        if pid:
            kill_pid(pid)
            log(f"  ✅ {label} 端口 {port} 已释放 (PID: {pid})")

    # 方式 3: Windows 窗口标题
    if platform.system() == "Windows":
        for title in ["MathModelPro-Backend", "MathModelPro-Frontend"]:
            kill_by_window_title(title)

    # 清理 PID 文件
    if PID_FILE.exists():
        PID_FILE.unlink()

    log("\n✅ 所有服务已停止")


def show_status():
    """显示服务状态"""
    print_banner()
    print_section("服务状态")

    # 后端
    backend_running = not check_port(BACKEND_PORT)
    if backend_running:
        log(f"  🟢 后端 API: 运行中 → http://127.0.0.1:{BACKEND_PORT}")
        # 健康检查
        code, body = url_get(f"http://127.0.0.1:{BACKEND_PORT}/health")
        if code == 200:
            try:
                data = json.loads(body)
                log(f"     健康状态: {data.get('status', 'ok')}")
            except Exception:
                log(f"     健康检查: 响应异常")
        else:
            log(f"     健康检查: 无法连接 ({code})")
        # API 端点统计
        code, body = url_get(f"http://127.0.0.1:{BACKEND_PORT}/openapi.json", timeout=5)
        if code == 200:
            try:
                paths = json.loads(body).get("paths", {})
                log(f"     API 端点: {len(paths)} 个")
            except Exception:
                pass
    else:
        log(f"  🔴 后端 API: 未运行 (端口 {BACKEND_PORT})")

    # 前端
    frontend_running = not check_port(FRONTEND_PORT)
    if frontend_running:
        log(f"  🟢 前端界面: 运行中 → http://localhost:{FRONTEND_PORT}")
    else:
        log(f"  🔴 前端界面: 未运行 (端口 {FRONTEND_PORT})")

    print_section("")


def _confirm(prompt: str) -> bool:
    """交互确认（自动模式下默认同意）"""
    if AUTO_MODE:
        return True
    try:
        response = input(f"{prompt} [Y/n]: ").strip().lower()
        return response in ("", "y", "yes")
    except (KeyboardInterrupt, EOFError):
        return False


# ── 命令处理 ──────────────────────────────────────────────

def cmd_start():
    """启动全部服务"""
    check_environment()

    print_section("启动所有服务")

    # 先停止旧进程
    stop_services()
    time.sleep(1)

    backend_proc = start_backend()
    frontend_proc = start_frontend()

    if not backend_proc and not frontend_proc:
        log("\n❌ 未能启动任何服务，请检查日志")
        return

    log("")
    log("╔════════════════════════════════════════════╗")
    log("║              🚀 启动成功！                 ║")
    log("╠════════════════════════════════════════════╣")
    log(f"║  前端: http://localhost:{FRONTEND_PORT}           ║")
    log(f"║  后端: http://127.0.0.1:{BACKEND_PORT}           ║")
    log(f"║  API:  http://127.0.0.1:{BACKEND_PORT}/docs      ║")
    log(f"║  健康: http://127.0.0.1:{BACKEND_PORT}/health    ║")
    log("╚════════════════════════════════════════════╝")
    log(f"\n  日志目录: {LOG_DIR}")
    log("  按 Ctrl+C 停止所有服务\n")

    if not NO_BROWSER:
        time.sleep(2)
        webbrowser.open(f"http://localhost:{FRONTEND_PORT}")

    # 监控进程
    try:
        while True:
            time.sleep(1)
            if backend_proc and backend_proc.poll() is not None:
                log("\n⚠️ 后端意外退出，查看日志: .logs/backend.log")
                break
            if frontend_proc and frontend_proc.poll() is not None:
                log("\n⚠️ 前端意外退出，查看日志: .logs/frontend.log")
                break
    except KeyboardInterrupt:
        log("\n\n正在关闭服务...")
        if backend_proc:
            backend_proc.terminate()
        if frontend_proc:
            frontend_proc.terminate()
        stop_services()
        log("👋 再见!")


def cmd_stop():
    """停止全部服务"""
    stop_services()


def cmd_restart():
    """重启全部服务"""
    stop_services()
    time.sleep(2)
    cmd_start()


def cmd_backend():
    """仅启动后端"""
    check_environment()
    proc = start_backend()
    if not proc:
        return
    log("\n按 Ctrl+C 停止后端...")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        stop_services()
        log("\n后端已停止")


def cmd_frontend():
    """仅启动前端"""
    proc = start_frontend()
    if not proc:
        return
    log("\n按 Ctrl+C 停止前端...")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        stop_services()
        log("\n前端已停止")


def cmd_dev():
    """开发模式"""
    cmd_start()


# ── 主入口 ────────────────────────────────────────────────

def parse_args():
    """解析命令行参数"""
    global AUTO_MODE, NO_BROWSER, BACKEND_PORT, FRONTEND_PORT

    parser = argparse.ArgumentParser(
        description="MathModelPro 统一启动器",
        add_help=False,
    )
    parser.add_argument("command", nargs="?", default="start",
                        choices=["start", "stop", "restart", "status",
                                 "check", "backend", "frontend", "open", "dev"])
    parser.add_argument("--auto", "-a", action="store_true",
                        help="自动模式（跳过交互确认）")
    parser.add_argument("--no-browser", action="store_true",
                        help="不自动打开浏览器")
    parser.add_argument("--port-backend", type=int, default=DEFAULT_BACKEND_PORT,
                        help=f"后端端口（默认 {DEFAULT_BACKEND_PORT}）")
    parser.add_argument("--port-frontend", type=int, default=DEFAULT_FRONTEND_PORT,
                        help=f"前端端口（默认 {DEFAULT_FRONTEND_PORT}）")
    parser.add_argument("--help", "-h", action="store_true",
                        help="显示帮助信息")

    args, _ = parser.parse_known_args()

    if args.help:
        print(__doc__)
        sys.exit(0)

    AUTO_MODE = args.auto
    NO_BROWSER = args.no_browser
    BACKEND_PORT = args.port_backend
    FRONTEND_PORT = args.port_frontend

    return args.command


def main():
    command = parse_args()

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": show_status,
        "check": check_environment,
        "backend": cmd_backend,
        "frontend": cmd_frontend,
        "open": lambda: (webbrowser.open(f"http://localhost:{FRONTEND_PORT}"),
                         log(f"浏览器已打开: http://localhost:{FRONTEND_PORT}")),
        "dev": cmd_dev,
    }

    try:
        commands[command]()
    except KeyboardInterrupt:
        log("\n\n操作已取消")
        stop_services()
    except Exception as e:
        log(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
