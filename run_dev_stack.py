#!/usr/bin/env python

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


class Colors:
    BOLD = "\033[1m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"


ManagedProcess = Tuple[str, subprocess.Popen]


def log_service(service_name: str, message: str, status: str = "INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {
        "INFO": Colors.CYAN,
        "SUCCESS": Colors.GREEN,
        "ERROR": Colors.RED,
        "WARN": Colors.YELLOW,
    }
    color = colors.get(status, Colors.RESET)
    print(f"{color}[{timestamp}] {service_name:15} | {message}{Colors.RESET}")


def get_project_root() -> Path:
    return Path(__file__).resolve().parent


def get_venv_python() -> str:
    venv_path = get_project_root() / ".venv"
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"

    if python_exe.exists():
        return str(python_exe)

    log_service("STARTUP", f"venv not found at {venv_path}, using system Python", "WARN")
    return sys.executable


def get_npm_command() -> Optional[str]:
    if sys.platform == "win32":
        return shutil.which("npm.cmd") or shutil.which("npm")
    return shutil.which("npm")


def ensure_backend_dependencies(python_exe: str) -> bool:
    check = subprocess.run(
        [
            python_exe,
            "-c",
            (
                "import importlib.util, sys; "
                "modules = ('fastapi', 'uvicorn', 'sqlalchemy', 'sqlmodel', "
                "'pydantic_settings', 'multipart', 'pypdf', 'PIL'); "
                "missing = [name for name in modules if importlib.util.find_spec(name) is None]; "
                "print(', '.join(missing)); sys.exit(bool(missing))"
            ),
        ],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        return True

    requirements = get_project_root() / "backend" / "requirements.txt"
    log_service(
        "BACKEND",
        f"Missing Python dependencies: {check.stdout.strip() or check.stderr.strip()}",
        "ERROR",
    )
    log_service(
        "BACKEND",
        f'Install them with: "{python_exe}" -m pip install -r "{requirements}"',
        "ERROR",
    )
    return False


def ensure_frontend_built(frontend_dir: Path, static_dir: Path) -> bool:
    index_path = static_dir / "index.html"
    if index_path.is_file():
        build_time = index_path.stat().st_mtime
        source_paths = [path for path in frontend_dir.iterdir() if path.is_file()]
        for source_dir in (frontend_dir / "src", frontend_dir / "public"):
            if source_dir.is_dir():
                source_paths.extend(source_dir.rglob("*"))
        frontend_changed = any(
            path.is_file()
            and path.stat().st_mtime > build_time
            for path in source_paths
        )
        if not frontend_changed:
            return True

    npm_cmd = get_npm_command()
    if not npm_cmd:
        log_service(
            "FRONTEND",
            "npm is required for the first run to build the web interface.",
            "ERROR",
        )
        return False

    if not (frontend_dir / "node_modules").is_dir():
        log_service("FRONTEND", "Installing frontend build dependencies...", "INFO")
        install = subprocess.run(
            [npm_cmd, "install"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
        )
        if install.returncode != 0:
            log_service(
                "FRONTEND",
                install.stderr.strip() or install.stdout.strip() or "npm install failed.",
                "ERROR",
            )
            return False

    log_service("FRONTEND", "Building static web interface...", "INFO")
    build = subprocess.run(
        [npm_cmd, "run", "build"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        log_service(
            "FRONTEND",
            build.stderr.strip() or build.stdout.strip() or "Frontend build failed.",
            "ERROR",
        )
        return False
    if not (static_dir / "index.html").is_file():
        log_service("FRONTEND", f"Build did not create {static_dir / 'index.html'}", "ERROR")
        return False
    return True


def start_backend(python_exe: str, backend_dir: Path) -> Optional[subprocess.Popen]:
    log_service("BACKEND", "Starting local application...", "INFO")
    try:
        process = subprocess.Popen(
            [
                python_exe,
                "-m",
                "uvicorn",
                "app.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        log_service("BACKEND", f"Application started (PID: {process.pid})", "SUCCESS")
        return process
    except OSError as error:
        log_service("BACKEND", f"Failed to start application: {error}", "ERROR")
        return None


def stream_process_output(
    process: subprocess.Popen, service_name: str, stop_event: threading.Event
):
    if process.stdout is None:
        log_service(service_name, "Process output is unavailable.", "ERROR")
        return

    while not stop_event.is_set() and process.poll() is None:
        line = process.stdout.readline()
        if not line:
            break
        log_service(service_name, line.strip())


def wait_for_backend(process: subprocess.Popen, timeout: float = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    return False


def cleanup_processes(
    processes: List[ManagedProcess], stop_event: threading.Event
):
    stop_event.set()
    for service_name, process in processes:
        if process.poll() is not None:
            continue
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        except OSError as error:
            log_service("SHUTDOWN", f"Could not stop {service_name}: {error}", "ERROR")


def main():
    parser = argparse.ArgumentParser(description="Run Private Converter locally")
    parser.parse_args()

    project_root = get_project_root()
    backend_dir = project_root / "backend"
    frontend_dir = project_root / "frontend"
    static_dir = backend_dir / "static"

    if not backend_dir.is_dir():
        log_service("STARTUP", f"Backend directory not found: {backend_dir}", "ERROR")
        sys.exit(1)
    if not frontend_dir.is_dir():
        log_service("STARTUP", f"Frontend directory not found: {frontend_dir}", "ERROR")
        sys.exit(1)
    python_exe = get_venv_python()
    if not ensure_backend_dependencies(python_exe):
        sys.exit(1)
    if not ensure_frontend_built(frontend_dir, static_dir):
        sys.exit(1)

    processes: List[ManagedProcess] = []
    stop_event = threading.Event()
    try:
        backend_proc = start_backend(python_exe, backend_dir)
        if backend_proc is None:
            sys.exit(1)
        processes.append(("BACKEND", backend_proc))

        output_thread = threading.Thread(
            target=stream_process_output,
            args=(backend_proc, "BACKEND", stop_event),
            daemon=True,
        )
        output_thread.start()
        if not wait_for_backend(backend_proc):
            log_service("BACKEND", "Application did not become ready; see the error above.", "ERROR")
            cleanup_processes(processes, stop_event)
            sys.exit(1)
        print(f"\n{Colors.BOLD}{Colors.GREEN}Private Converter is ready{Colors.RESET}")
        print(f"Open {Colors.CYAN}http://127.0.0.1:8000/{Colors.RESET}")
        print(f"API docs: {Colors.CYAN}http://127.0.0.1:8000/docs{Colors.RESET}")
        print("Press Ctrl+C to stop.\n")

        while backend_proc.poll() is None:
            time.sleep(0.5)

        log_service(
            "BACKEND",
            f"Application exited with code {backend_proc.returncode}",
            "ERROR",
        )
        cleanup_processes(processes, stop_event)
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        cleanup_processes(processes, stop_event)
        log_service("SHUTDOWN", "Application stopped", "SUCCESS")
    except Exception as error:
        log_service("STARTUP", f"Error: {error}", "ERROR")
        cleanup_processes(processes, stop_event)
        sys.exit(1)


if __name__ == "__main__":
    main()
