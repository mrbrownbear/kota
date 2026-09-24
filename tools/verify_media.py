from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import subprocess

from sync_local_assets import ROOT, discover_refs, download_one

VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov", ".webm"}

def probe(path: Path):
    proc = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=codec_type,codec_name,width,height",
            "-of", "json",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        return False, [], proc.stderr.strip()
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        return False, [], f"invalid ffprobe JSON: {exc}"
    streams = data.get("streams") or []
    videos = [s for s in streams if s.get("codec_type") == "video"]
    if not videos:
        return False, streams, "no video stream found"
    return True, streams, ""

def main():
    refs = sorted(
        (host, path)
        for host, path in discover_refs()
        if Path(path).suffix.lower() in VIDEO_SUFFIXES
    )

    failures = []
    repaired = []
    codecs = Counter()

    for host, rel in refs:
        path = ROOT / "__external__" / host / rel
        ok, streams, error = probe(path) if path.is_file() else (False, [], "missing file")

        if not ok:
            result = download_one((host, rel))
            if result.get("status") in {"downloaded", "ok"} and path.is_file():
                ok, streams, error = probe(path)
                if ok:
                    repaired.append(str(path.relative_to(ROOT)))

        if ok:
            for stream in streams:
                if stream.get("codec_type") == "video":
                    codecs[stream.get("codec_name") or "unknown"] += 1
        else:
            failures.append({
                "path": str(path.relative_to(ROOT)),
                "error": error,
            })

    report = {
        "referenced_video_files": len(refs),
        "repaired": repaired,
        "codec_summary": dict(sorted(codecs.items())),
        "failure_count": len(failures),
        "failures": failures,
    }
    (ROOT / "media-validation-report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))

    if failures:
        raise SystemExit(f"media validation failed: {len(failures)} files")

if __name__ == "__main__":
    main()
