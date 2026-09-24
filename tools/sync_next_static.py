from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".html", ".htm", ".js", ".mjs", ".css", ".json", ".bin", ".txt", ""}
STATIC_SUFFIXES = {
    ".css", ".js", ".mjs", ".woff", ".woff2", ".ttf", ".otf",
    ".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".wasm", ".json"
}
PATTERN = re.compile(r'(?<![A-Za-z0-9])(?P<path>/_next/static/(?:css|chunks|media)/[^\s"\'<>\\)]+)')

def iter_text():
    for p in ROOT.rglob("*"):
        if not p.is_file() or ".git" in p.parts or "node_modules" in p.parts:
            continue
        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        if b"\0" in raw[:4096]:
            continue
        try:
            yield raw.decode("utf-8")
        except UnicodeDecodeError:
            continue

def refs():
    out = set()
    for text in iter_text():
        for m in PATTERN.finditer(text):
            path = m.group("path").split("?", 1)[0].split("#", 1)[0]
            path = unquote(path)
            if ".." in Path(path).parts:
                continue
            if Path(path).suffix.lower() not in STATIC_SUFFIXES:
                continue
            out.add(path)
    return out

def valid(p: Path):
    if not p.is_file():
        return False
    # Next can emit intentionally empty CSS chunks. Their presence is valid.
    if p.suffix.lower() == ".css":
        return True
    return p.stat().st_size > 0

def fetch(path: str):
    dest = ROOT / path.lstrip("/")
    if valid(dest):
        return {"status": "ok", "path": path}
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = "https://kota.co.uk" + quote(path, safe="/:@-._~!$&'()*+,;=%[]")
    tmp = dest.with_name(dest.name + ".download")
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 KOTA-localizer/1.0"})
        with urlopen(req, timeout=60) as response, tmp.open("wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        if not valid(tmp):
            raise OSError("empty download")
        tmp.replace(dest)
        return {"status": "downloaded", "path": path, "url": url, "bytes": dest.stat().st_size}
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        tmp.unlink(missing_ok=True)
        return {"status": "failed", "path": path, "url": url, "error": f"{type(e).__name__}: {e}"}

def main():
    references = sorted(refs())
    missing = [p for p in references if not valid(ROOT / p.lstrip("/"))]
    print(f"Referenced Next static files: {len(references)}")
    print(f"Missing Next static files: {len(missing)}")
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for result in as_completed([pool.submit(fetch, p) for p in missing]):
            r = result.result()
            results.append(r)
            print(r["status"].upper(), r["path"], r.get("error", ""))

    failed = [r for r in results if r["status"] == "failed"]
    report = {
        "referenced": len(references),
        "missing_before": len(missing),
        "downloaded": sum(r["status"] == "downloaded" for r in results),
        "failed": failed,
    }
    (ROOT / "next-static-sync-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if failed:
        raise SystemExit(f"Next static sync incomplete: {len(failed)} files failed")

if __name__ == "__main__":
    main()
