"""Run `python tests/test_rpc.py`; no Qt installation, Codex process, or account needed."""
import io
import json
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch


# Load only the stdlib RPC section so these checks also run without a display.
path = Path(__file__).resolve().parents[1] / "src/usage-dashboard.py"
sys.path.insert(0, str(path.parent))
module = types.ModuleType("dashboard_rpc")
module.__file__ = str(path)
exec(compile(path.read_text(encoding="utf-8").split("\nfrom PySide6.", 1)[0], str(path), "exec"), module.__dict__)


class FakeProcess:
    def __init__(self, replies, broken_pipe=False):
        self.stdout = io.StringIO("".join(
            (reply if isinstance(reply, str) else json.dumps(reply)) + "\n" for reply in replies))
        self.stdin = io.StringIO()
        self.handshake_read = False
        self.sent = []
        self.broken_pipe = broken_pipe

    def send(self, data):
        if self.broken_pipe:
            raise BrokenPipeError("closed")
        method = json.loads(data)["method"]
        assert method == "initialize" or self.handshake_read, "must await initialization"
        self.sent.append(method)
        return len(data)

    def readline(self, cancel, deadline):
        if time.monotonic() >= deadline:
            raise TimeoutError("시간이 초과")
        line = self.stdout.readline()
        try:
            response = json.loads(line)
            if isinstance(response, dict) and response.get("id") == 0:
                self.handshake_read = True
        except ValueError:
            pass
        return line

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stdin.close()
        self.stdout.close()


def check(replies, expected=None, error=None, ticks=None, **options):
    process = FakeProcess(replies, **options)

    with patch.object(module, "find_codex", return_value="fake-codex"), \
         patch.object(module, "QueryProcess", return_value=process), \
         patch.object(module.time, "monotonic", side_effect=ticks, return_value=0):
        try:
            result = module.read_usage()
        except (RuntimeError, OSError) as exc:
            assert error and error in str(exc), str(exc)
        else:
            assert error is None, "expected failure"
            assert result == expected, result
    assert process.stdin.closed and process.stdout.closed
    return process


if __name__ == "__main__":
    initialized = {"id": 0, "result": {}}
    account = {"id": 1, "result": {"account": None}}
    limits = {"id": 2, "result": {"rateLimits": {}}}
    usage = {"id": 3, "result": {"summary": {"lifetimeTokens": 123}}}
    expected = (account["result"], limits["result"], usage["result"])
    check(["not-json", [], initialized, usage, account, limits], expected)
    check([initialized, {"id": 3, "error": {"code": -32601}}, limits, account],
          (account["result"], limits["result"], {}))
    check([initialized, {"id": 3, "error": {"code": -32600,
          "message": "Invalid request: unknown variant `account/usage/read`, expected ..."}}, limits, account],
          (account["result"], limits["result"], {}))
    check([{"id": 0, "error": {"message": "init failed"}}], error="init failed")
    check([initialized, {"id": 2, "error": {"message": "quota failed"}}], error="quota failed")
    check([initialized, {"id": 3, "error": {"code": -32000, "message": "usage failed"}}], error="usage failed")
    check([initialized, {"id": 3, "error": {"code": -32600, "message": "invalid params"}}], error="invalid params")
    check([initialized, {"id": 1, "result": None}], error="응답 형식")
    check([], error="연결이 종료")
    check([initialized], error="closed", broken_pipe=True)
    check([initialized, {"method": "notification"}, {"method": "notification"}],
          error="시간이 초과", ticks=[0, 0, 1, 16])
    print("PASS: RPC handshake, compatibility, deadline, EOF, errors, and cleanup")
