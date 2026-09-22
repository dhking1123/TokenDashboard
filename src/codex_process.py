"""Own one query's process tree and pipes; never signal processes by name."""
import ctypes
import os
import select
import signal
import subprocess
import sys
import time
from ctypes import wintypes as w


if sys.platform == "win32":
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class JobLimits(ctypes.Structure):
        _fields_ = [("per_process", ctypes.c_longlong), ("per_job", ctypes.c_longlong),
                    ("flags", w.DWORD), ("min_working_set", ctypes.c_size_t),
                    ("max_working_set", ctypes.c_size_t), ("active_processes", w.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
                    ("scheduling", w.DWORD)]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("basic", JobLimits), ("io", ctypes.c_ulonglong * 6),
                    ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                    ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]

    class ThreadEntry(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("tid", w.DWORD),
                    ("pid", w.DWORD), ("priority", w.LONG), ("base_priority", w.LONG),
                    ("flags", w.DWORD)]

    for name, args, result in (
        ("CreateJobObjectW", [w.LPVOID, w.LPCWSTR], w.HANDLE),
        ("SetInformationJobObject", [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD], w.BOOL),
        ("AssignProcessToJobObject", [w.HANDLE, w.HANDLE], w.BOOL),
        ("CloseHandle", [w.HANDLE], w.BOOL),
        ("CreateToolhelp32Snapshot", [w.DWORD, w.DWORD], w.HANDLE),
        ("Thread32First", [w.HANDLE, ctypes.POINTER(ThreadEntry)], w.BOOL),
        ("Thread32Next", [w.HANDLE, ctypes.POINTER(ThreadEntry)], w.BOOL),
        ("OpenThread", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
        ("ResumeThread", [w.HANDLE], w.DWORD),
        ("PeekNamedPipe", [w.HANDLE, w.LPVOID, w.DWORD, w.LPVOID, ctypes.POINTER(w.DWORD), w.LPVOID], w.BOOL),
    ):
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result

    def resume_process(pid):
        # Popen closes the primary thread handle. The suspended process has one thread.
        snapshot = kernel.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == w.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = ThreadEntry(size=ctypes.sizeof(ThreadEntry))
            found = kernel.Thread32First(snapshot, ctypes.byref(entry))
            while found:
                if entry.pid == pid:
                    thread = kernel.OpenThread(2, False, entry.tid)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if kernel.ResumeThread(thread) == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                        return
                    finally:
                        kernel.CloseHandle(thread)
                found = kernel.Thread32Next(snapshot, ctypes.byref(entry))
            raise RuntimeError("Codex primary thread was not found")
        finally:
            kernel.CloseHandle(snapshot)


class QueryProcess:
    def __init__(self, command):
        self.process = None
        self.job = None
        self.buffer = bytearray()
        try:
            options = {"start_new_session": True}
            if sys.platform == "win32":
                self.job = kernel.CreateJobObjectW(None, None)
                if not self.job:
                    raise ctypes.WinError(ctypes.get_last_error())
                limits = ExtendedLimits()
                limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                if not kernel.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                    raise ctypes.WinError(ctypes.get_last_error())
                options = {"creationflags": subprocess.CREATE_NO_WINDOW | 4}  # CREATE_SUSPENDED
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, bufsize=0, **options)
            if self.job:
                if not kernel.AssignProcessToJobObject(self.job, int(self.process._handle)):
                    raise ctypes.WinError(ctypes.get_last_error())
                # No launcher can create children before it belongs to our job.
                resume_process(self.process.pid)
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def send(self, data):
        self.process.stdin.write(data.encode("utf-8"))

    def readline(self, cancel, deadline):
        # Poll the pipe instead of leaving a blocking reader thread behind.
        while True:
            if cancel.is_set():
                raise RuntimeError("Codex 조회가 취소되었습니다.")
            if time.monotonic() >= deadline:
                raise TimeoutError("Codex 사용량 조회 시간이 초과되었습니다.")
            if b"\n" in self.buffer:
                line, _, self.buffer = self.buffer.partition(b"\n")
                return (line + b"\n").decode("utf-8")
            if sys.platform == "win32":
                import msvcrt
                available = w.DWORD()
                handle = msvcrt.get_osfhandle(self.process.stdout.fileno())
                if not kernel.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
                    error = ctypes.get_last_error()
                    if error == 109:  # ERROR_BROKEN_PIPE
                        return ""
                    raise ctypes.WinError(error)
                count = min(available.value, 65536)
            else:
                count = 65536 if select.select([self.process.stdout], [], [], 0)[0] else 0
            if count:
                chunk = os.read(self.process.stdout.fileno(), count)
                if not chunk:
                    return ""
                self.buffer.extend(chunk)
            else:
                cancel.wait(0.05)

    def close(self):
        if self.job:
            # Also kills descendants whose launcher already exited. Handle is not inherited.
            kernel.CloseHandle(self.job)
            self.job = None
        process = self.process
        if process is None:
            return
        try:
            if sys.platform != "win32":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()  # Covers failure to assign the still-suspended process.
            process.wait(timeout=2)
        finally:
            process.stdin.close()
            process.stdout.close()
            if sys.platform == "win32":
                process._handle.Close()
            self.process = None
