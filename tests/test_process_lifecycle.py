"""Windows regression: python tests/test_process_lifecycle.py (stdlib + existing Qt)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def fixture():
    role, directory, mode = sys.argv[1:4]
    directory = Path(directory)
    (directory / f"{os.getpid()}.pid").write_text(role)
    if role != "--grandchild":
        subprocess.Popen([sys.executable, __file__, "--child" if role == "--server" else "--grandchild",
                          str(directory), mode])
    if role == "--server":
        until = time.monotonic() + 5
        while len(list(directory.glob("*.pid"))) < 3:
            if time.monotonic() >= until:
                raise RuntimeError("fixture child did not start")
            time.sleep(0.01)
        if mode == "exit":
            return  # Descendants keep stdout open even after the launcher exits.
        for line in sys.stdin:
            request = json.loads(line)
            rid = request.get("id")
            if rid is None or mode == "timeout":
                continue
            result = {"id": rid, "result": {}}
            if (mode == "init-error" and rid == 0) or (mode == "server-error" and rid == 2):
                result = {"id": rid, "error": {"message": mode}}
            print(json.dumps(result), flush=True)
    time.sleep(60)


def run():
    # Fixture children need only the lightweight imports above. Loading the
    # test harness in all three generations consumes the query deadline.
    import ctypes
    import importlib.util
    import tempfile
    import threading
    from unittest.mock import patch

    if sys.platform != "win32":
        print("SKIP: Windows process-tree regression requires Windows")
        return
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    import codex_process as lifecycle
    from ctypes import wintypes as w
    kernel = lifecycle.kernel
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    kernel.WaitForSingleObject.restype = w.DWORD

    def alive(pid):
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)

    source = Path(__file__).resolve().parents[1] / "src/usage-dashboard.py"
    spec = importlib.util.spec_from_file_location("lifecycle_dashboard", source)
    dashboard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dashboard)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = dashboard.QApplication.instance() or dashboard.QApplication([])
    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(120)"])
    baseline_threads = {t.ident for t in threading.enumerate()}
    records = []
    try:
        with tempfile.TemporaryDirectory(prefix="dashboard-tree-") as temporary:
            root = Path(temporary)
            for index, mode in enumerate(["normal"] * 12 + ["init-error", "server-error", "timeout", "exit", "close", "quit"]):
                directory = root / str(index)
                directory.mkdir()
                # Force the same cmd -> launcher -> child -> grandchild shape as an npm shim.
                wrapper = directory / "codex.cmd"
                wrapper.write_text(f'@"{sys.executable}" "{Path(__file__).resolve()}" --server "{directory}" {mode}\n')
                owned = []

                def start(command):
                    query = lifecycle.QueryProcess(command)
                    owned.append(query.process)
                    return query

                with patch.object(dashboard, "find_codex", return_value=str(wrapper)), \
                     patch.object(dashboard, "QueryProcess", side_effect=start):
                    began = time.monotonic()
                    if mode in ("close", "quit"):
                        window = dashboard.Dashboard(False)
                        window.settings = directory / 'settings.json'
                        window.refresh()
                        window.refresh()  # Manual and auto requests must share the busy guard.
                        until = time.monotonic() + 5
                        while len(list(directory.glob("*.pid"))) < 3 and time.monotonic() < until:
                            app.processEvents()
                            time.sleep(0.01)
                        assert len(owned) == 1
                        if mode == "close":
                            window.close()
                        else:
                            # main connects this same slot to QApplication.aboutToQuit.
                            app.aboutToQuit.connect(window.shutdown)
                            app.aboutToQuit.emit()
                            app.aboutToQuit.disconnect(window.shutdown)
                        assert not window.worker.is_alive()
                        assert not window.timer.isActive() and not window.poller.isActive()
                        window.refresh()
                        assert len(owned) == 1
                        window.close()
                    else:
                        try:
                            assert dashboard.read_usage(timeout=1.5) == ({}, {}, {})
                            assert mode == "normal"
                        except (RuntimeError, TimeoutError) as error:
                            assert mode != "normal", str(error)
                            assert (mode in str(error)) or (mode in ("timeout", "exit") and "초과" in str(error))
                    pids = [int(path.stem) for path in directory.glob("*.pid")]
                    assert len(pids) == 3, (mode, pids)
                    pids += [process.pid for process in owned]
                    until = time.monotonic() + 2
                    while any(alive(pid) for pid in pids) and time.monotonic() < until:
                        time.sleep(0.02)
                    assert not any(alive(pid) for pid in pids), (mode, pids)
                    assert all(p.stdin.closed and p.stdout.closed for p in owned)
                    assert {t.ident for t in threading.enumerate()} == baseline_threads
                    assert unrelated.poll() is None
                    records.append({"mode": mode, "pids": pids, "remaining": 0,
                                    "seconds": round(time.monotonic() - began, 3)})

            # Assignment / resume / Popen failures must not leave a suspended process.
            real_popen = subprocess.Popen
            created = []

            def track(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                created.append(process)
                return process

            for function in ("AssignProcessToJobObject", "resume_process"):
                owner = kernel if function == "AssignProcessToJobObject" else lifecycle
                with patch.object(lifecycle.subprocess, "Popen", side_effect=track), \
                     patch.object(owner, function, side_effect=OSError("injected startup failure")):
                    try:
                        lifecycle.QueryProcess([sys.executable, "-c", "import time;time.sleep(60)"])
                        raise AssertionError("expected startup failure")
                    except OSError:
                        pass
                until = time.monotonic() + 2
                while alive(created[-1].pid) and time.monotonic() < until:
                    time.sleep(0.02)
                assert not alive(created[-1].pid)
                assert created[-1].stdin.closed and created[-1].stdout.closed
            try:
                lifecycle.QueryProcess([str(root / "missing.exe")])
                raise AssertionError("expected missing executable")
            except OSError:
                pass

            # CLI-only installation with npm first in PATH, plus legacy npm vendor layout.
            npm = root / "npm"
            npm.mkdir()
            (npm / "codex.cmd").write_text("@exit /b 1\n")
            package = npm / "node_modules/@openai/codex"
            package.mkdir(parents=True)
            (package / "package.json").write_text('{"name":"@openai/codex"}')
            arch = "arm64" if dashboard.platform.machine().lower() in ("arm64", "aarch64") else "x64"
            target = "aarch64" if arch == "arm64" else "x86_64"
            native = package / f"node_modules/@openai/codex-win32-{arch}/vendor/{target}-pc-windows-msvc/bin/codex.exe"
            native.parent.mkdir(parents=True)
            import shutil
            shutil.copyfile(sys.executable, native)
            with patch.dict(os.environ, {"PATH": str(npm), "LOCALAPPDATA": str(root / "no-app")}):
                assert dashboard.find_codex() == str(native.resolve())
                native.unlink()
                assert dashboard.find_codex() == str(npm / "codex.cmd")
                native.write_text("not an executable")
                assert dashboard.find_codex() == str(npm / "codex.cmd")
                native.unlink()
                legacy = package / f"vendor/{target}-pc-windows-msvc/bin/codex.exe"
                legacy.parent.mkdir(parents=True)
                shutil.copyfile(sys.executable, legacy)
                assert dashboard.find_codex() == str(legacy.resolve())
            assert unrelated.poll() is None
        print(json.dumps(records, indent=2))
        print("PASS: real Windows trees, 12 repeated queries, errors, timeout, exited launcher, close/quit, startup failures, npm discovery; unrelated process survived")
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=3)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--server", "--child", "--grandchild"):
        fixture()
    else:
        run()
