from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PROCESSORS = ROOT / "scripts" / "processors"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


def _builtins() -> list[dict[str, str]]:
    return [
        {"id": p.stem, "name": p.name, "source": "COJ processor"}
        for p in sorted(PROCESSORS.glob("*_processor.py"))
    ]


def _script_path(script_id: str) -> Path:
    candidates = {p.stem: p for p in PROCESSORS.glob("*_processor.py")}
    path = candidates.get(script_id)
    if path is None:
        abort(404, description="Unknown processor")
    return path


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/scripts")
def scripts():
    return jsonify(_builtins())


@app.get("/api/scripts/<script_id>/settings")
def script_settings(script_id: str):
    script = _script_path(script_id)
    proc = subprocess.run(
        [sys.executable, str(HERE / "worker.py"), "inspect", str(script)],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )
    if proc.returncode:
        return jsonify({"error": proc.stderr or proc.stdout}), 400
    return jsonify(json.loads(proc.stdout))


@app.post("/api/run")
def run_script():
    payload = request.get_json(force=True)
    script = _script_path(str(payload.get("script", "")))
    settings = payload.get("settings", {})
    if not isinstance(settings, dict):
        abort(400, description="settings must be an object")

    run_id = uuid.uuid4().hex[:12]
    run_dir = RUNS / run_id
    (run_dir / "data").mkdir(parents=True)
    shutil.copytree(ROOT / "data" / "xml" / "text", run_dir / "data" / "text")
    shutil.copytree(ROOT / "data" / "xml" / "dict", run_dir / "data" / "dict")
    (run_dir / "output").mkdir()
    config = run_dir / "config.json"
    config.write_text(json.dumps(settings), encoding="utf-8")

    try:
        proc = subprocess.run(
            [sys.executable, str(HERE / "worker.py"), "run", str(script),
             str(run_dir), str(config)],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        return jsonify({"error": "Processor exceeded the 120 second limit.",
                        "console": (exc.stdout or "")}), 408

    result_file = run_dir / "result.json"
    if not result_file.exists():
        return jsonify({"error": "Processor failed", "console": proc.stdout,
                        "details": proc.stderr}), 400
    result = json.loads(result_file.read_text(encoding="utf-8"))
    result["run_id"] = run_id
    result["console"] = proc.stdout
    if proc.stderr:
        result["warnings"] = proc.stderr
    return jsonify(result), (200 if proc.returncode == 0 else 400)


@app.get("/api/runs/<run_id>/files/<path:name>")
def run_file(run_id: str, name: str):
    if not run_id.isalnum():
        abort(404)
    base = (RUNS / run_id / "output").resolve()
    path = (base / name).resolve()
    if base not in path.parents or not path.is_file():
        abort(404)
    return path.read_text(encoding="utf-8", errors="replace"), 200, {
        "Content-Type": "text/plain; charset=utf-8"
    }


if __name__ == "__main__":
    RUNS.mkdir(exist_ok=True)
    app.run(debug=True, port=5001)
