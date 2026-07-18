"""Launch AutoSignCAPAM and synchronized safe monitor in one diagnostic session."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
from pathlib import Path

from tools.common import create_run_dir, write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=300)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--output-root", default="artifacts/diagnostics")
    parser.add_argument("--capam-ip", default="10.64.213.188")
    args = parser.parse_args(argv)

    run_dir = create_run_dir(args.output_root)
    session_id = f"{run_dir.name}-{uuid.uuid4().hex[:8]}"
    timeline = run_dir / "flow-timeline.jsonl"
    env = os.environ.copy()
    env["AUTOMATION_SESSION_ID"] = session_id
    env["AUTOMATION_TIMELINE_PATH"] = str(timeline.resolve())
    write_json(
        run_dir / "debug-session.json",
        {
            "schema_version": 1,
            "session_id": session_id,
            "timeline": str(timeline),
            "duration": args.duration,
            "interval": args.interval,
            "contains_sensitive_data": False,
        },
    )

    creationflags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    monitor = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tools.monitor_flow",
            "--duration",
            str(args.duration),
            "--interval",
            str(args.interval),
            "--output",
            str(timeline),
            "--capam-ip",
            args.capam_ip,
        ],
        env=env,
        creationflags=creationflags,
    )
    gui_python = Path(sys.executable).with_name("pythonw.exe") if os.name == "nt" else Path(sys.executable)
    app = subprocess.Popen(
        [str(gui_python if gui_python.exists() else sys.executable), "main.py"],
        env=env,
        creationflags=creationflags,
    )
    print(run_dir)
    try:
        return app.wait()
    except KeyboardInterrupt:
        app.terminate()
        return 130
    finally:
        if monitor.poll() is None:
            monitor.terminate()
            try:
                monitor.wait(timeout=5)
            except subprocess.TimeoutExpired:
                monitor.kill()


if __name__ == "__main__":
    raise SystemExit(main())
