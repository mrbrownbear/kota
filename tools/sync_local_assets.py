from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import re
import time

ROOT = Path(__file__).resolve().parents[1]
HOSTS = ("kota-content.b-cdn.net", "content.kota.co.uk")
TEXT_SUFFIXES = {".html", ".htm", ".js", ".mjs", ".css", ".json", ".bin", ".txt", ""}
PATTERN = re.compile(
    r'(?:https?:)?//(?P<host>kota-content\.b-cdn\.net|content\.kota\.co\.uk)/(?P<path>[^\s"\'<>\\)]+)',
    re.I,
)
LOCAL_PATTERN = re.compile(
    r'/__external__/(?P<host>kota-content\.b-cdn\.net|content\.kota\.co\.uk)/(?P<path>[^\s"\'<>\\)]+)',
    re.I,
)

def iter_text_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if ".git" in p.parts or "node_modules" in p.parts:
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
            yield p, raw.decode("utf-8")
        except UnicodeDecodeError:
            continue

def normalize_ref(host: str, path: str):
    path = unescape(path).replace("\\u0026", "&")
    path = path.split("#", 1)[0].split("?", 1)[0]
    path = unquote(path).lstrip("/")
    if not path or ".." in Path(path).parts:
        return None
    return host.lower(), path

def discover_refs():
    refs = set()
    for _, text in iter_text_files():
        for rx in (PATTERN, LOCAL_PATTERN):
            for m in rx.finditer(text):
                item = normalize_ref(m.group("host"), m.group("path"))
                if item:
                    refs.add(item)
    return refs

def valid_file(p: Path) -> bool:
    if not p.is_file() or p.stat().st_size < 8:
        return False
    ext = p.suffix.lower()
    try:
        head = p.read_bytes()[:4096]
    except OSError:
        return False
    if ext in {".jpg", ".jpeg"}:
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == ".svg":
        low = head.lower()
        return b"<svg" in low
    if ext in {".mp4", ".m4v", ".mov"}:
        return b"ftyp" in head[:64]
    if ext == ".webm":
        return head.startswith(b"\x1a\x45\xdf\xa3")
    if ext == ".woff2":
        return head.startswith(b"wOF2")
    if ext == ".woff":
        return head.startswith(b"wOFF")
    if ext == ".json":
        try:
            json.loads(p.read_text("utf-8"))
            return True
        except Exception:
            return False
    return True

def remote_urls(host: str, path: str):
    encoded = quote(path, safe="/:@-._~!$&'()*+,;=")
    ordered = [host] + [h for h in HOSTS if h != host]
    return [f"https://{h}/{encoded}" for h in ordered]

def download_one(item):
    host, path = item
    dest = ROOT / "__external__" / host / path
    if valid_file(dest):
        return {"status": "ok", "path": str(dest.relative_to(ROOT))}

    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for url in remote_urls(host, path):
        tmp = dest.with_name(dest.name + ".download")
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 KOTA-localizer/1.0"})
            with urlopen(req, timeout=60) as response, tmp.open("wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            if valid_file(tmp):
                tmp.replace(dest)
                return {
                    "status": "downloaded",
                    "path": str(dest.relative_to(ROOT)),
                    "url": url,
                    "bytes": dest.stat().st_size,
                }
            last_error = f"invalid downloaded file from {url}"
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            last_error = f"{type(e).__name__}: {e}"
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        time.sleep(0.15)
    return {"status": "failed", "path": str(dest.relative_to(ROOT)), "error": last_error}

def mirror_hosts(refs):
    copied = 0
    for host, path in refs:
        src = ROOT / "__external__" / host / path
        if not valid_file(src):
            continue
        for other in HOSTS:
            dst = ROOT / "__external__" / other / path
            if other == host or valid_file(dst):
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                dst.write_bytes(src.read_bytes())
                copied += 1
            except OSError:
                pass
    return copied

def main():
    refs = discover_refs()
    todo = [r for r in refs if not valid_file(ROOT / "__external__" / r[0] / r[1])]
    print(f"Referenced CDN assets: {len(refs)}")
    print(f"Missing or invalid before repair: {len(todo)}")

    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(download_one, item) for item in todo]
        for fut in as_completed(futures):
            result = fut.result()
            results.append(result)
            if result["status"] == "failed":
                print("FAILED", result["path"], result.get("error", ""))
            else:
                print(result["status"].upper(), result["path"])

    copied = mirror_hosts(refs)
    failed = [x for x in results if x["status"] == "failed"]
    report = {
        "referenced_assets": len(refs),
        "repair_candidates": len(todo),
        "downloaded": sum(x["status"] == "downloaded" for x in results),
        "mirrored_between_cdn_hosts": copied,
        "failed": failed,
    }
    (ROOT / "asset-sync-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

    # Some references are optional historical cards, but every referenced visual
    # or media asset must exist locally for an offline clone.
    remaining = []
    for host, path in refs:
        p = ROOT / "__external__" / host / path
        if not valid_file(p):
            remaining.append(str(p.relative_to(ROOT)))
    if remaining:
        print("Still missing or invalid:")
        for p in remaining[:200]:
            print(p)
        raise SystemExit(f"asset sync incomplete: {len(remaining)} referenced files remain invalid")

if __name__ == "__main__":
    main()
