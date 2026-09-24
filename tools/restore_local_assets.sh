#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fetch_one() {
  local dest="$1"
  shift
  mkdir -p "$(dirname "$dest")"
  local tmp="${dest}.download"
  rm -f "$tmp"
  for url in "$@"; do
    echo "Fetching $url -> $dest"
    if curl --retry 3 --retry-delay 1 --connect-timeout 20 --max-time 180 -fL "$url" -o "$tmp"; then
      if [ -s "$tmp" ]; then
        mv "$tmp" "$dest"
        return 0
      fi
    fi
    rm -f "$tmp"
  done
  echo "ERROR: unable to fetch $dest" >&2
  return 1
}

fetch_one "_next/static/chunks/2827-f8fce45e8c1f0443.js" "https://kota.co.uk/_next/static/chunks/2827-f8fce45e8c1f0443.js"
fetch_one "_next/static/chunks/7765-2199a167410a4e62.js" "https://kota.co.uk/_next/static/chunks/7765-2199a167410a4e62.js"
fetch_one "_next/static/chunks/app/blog/[slug]/page-d99a465d7f04c801.js" "https://kota.co.uk/_next/static/chunks/app/blog/%5Bslug%5D/page-d99a465d7f04c801.js"
fetch_one "_next/static/chunks/app/contact/page-66896fc7dbdb22ec.js" "https://kota.co.uk/_next/static/chunks/app/contact/page-66896fc7dbdb22ec.js"
fetch_one "_next/static/chunks/app/culture/page-580d954c7a372e0a.js" "https://kota.co.uk/_next/static/chunks/app/culture/page-580d954c7a372e0a.js"
fetch_one "_next/static/chunks/app/faqs/page-c3da96667c39c053.js" "https://kota.co.uk/_next/static/chunks/app/faqs/page-c3da96667c39c053.js"
fetch_one "_next/static/chunks/app/newsletter/page-7f5544c8c220f7bf.js" "https://kota.co.uk/_next/static/chunks/app/newsletter/page-7f5544c8c220f7bf.js"
fetch_one "_next/static/chunks/app/privacy-policy/page-53ebfa010302763c.js" "https://kota.co.uk/_next/static/chunks/app/privacy-policy/page-53ebfa010302763c.js"
fetch_one "_next/static/chunks/app/start-your-project/page-3f3f314f0c1d89e4.js" "https://kota.co.uk/_next/static/chunks/app/start-your-project/page-3f3f314f0c1d89e4.js"
fetch_one "_next/static/chunks/app/work/page-5b3919766e28ce0e.js" "https://kota.co.uk/_next/static/chunks/app/work/page-5b3919766e28ce0e.js"

fetch_one "_next/static/css/77de916f6379b329.css" "https://kota.co.uk/_next/static/css/77de916f6379b329.css"
fetch_one "_next/static/css/435828e364f4b5ed.css" "https://kota.co.uk/_next/static/css/435828e364f4b5ed.css"
fetch_one "_next/static/css/d7552b378bb64018.css" "https://kota.co.uk/_next/static/css/d7552b378bb64018.css"
fetch_one "_next/static/css/decc77e58f025ef8.css" "https://kota.co.uk/_next/static/css/decc77e58f025ef8.css"

if [ -f "__external__/unpkg.com/@splinetool/runtime@1.9.37/build" ]; then
  rm -f "__external__/unpkg.com/@splinetool/runtime@1.9.37/build"
fi
mkdir -p "__external__/unpkg.com/@splinetool/runtime@1.9.37/build"
fetch_one "__external__/unpkg.com/@splinetool/runtime@1.9.37/build/navmesh.js" "https://unpkg.com/@splinetool/runtime@1.9.37/build/navmesh.js"
fetch_one "__external__/prod.spline.design/4asLCgiJDMkz7HAN/scene.splinecode" "https://prod.spline.design/4asLCgiJDMkz7HAN/scene.splinecode"
fetch_one "lottie/brand-pulse-outlines.json" "https://kota.co.uk/lottie/brand-pulse-outlines.json"

mkdir -p "_libraries"
cp "__external__/unpkg.com/@splinetool/runtime@1.9.37/build/navmesh.js" "_libraries/navmesh.js"
cp "__external__/unpkg.com/@splinetool/navmesh-wasm@1.9.37/build/navmesh.wasm" "_libraries/navmesh.wasm"

fetch_one "__external__/kota-content.b-cdn.net/app/uploads/2024/02/team-piper2.jpg" "https://kota-content.b-cdn.net/app/uploads/2024/02/team-piper2.jpg"
fetch_one "__external__/content.kota.co.uk/app/uploads/2024/05/hero.png" "https://content.kota.co.uk/app/uploads/2024/05/hero.png" "https://kota-content.b-cdn.net/app/uploads/2024/05/hero.png" || true
fetch_one "__external__/content.kota.co.uk/app/uploads/2024/11/Logo-Profile.png" "https://content.kota.co.uk/app/uploads/2024/11/Logo-Profile.png" "https://kota-content.b-cdn.net/app/uploads/2024/11/Logo-Profile.png" || true

mkdir -p "_assets/_videos"
python - <<'PY'
from pathlib import Path
import base64
p = Path("_assets/_videos/catThumb.png")
if not p.exists():
    p.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
PY

python - <<'PY'
from pathlib import Path

root = Path(".")
skip = {".git", "node_modules"}
text_suffixes = {".html", ".htm", ".js", ".mjs", ".css", ".json", ".bin", ".txt", ""}
replacements = [
    ("https://prod.spline.design/4asLCgiJDMkz7HAN/scene.splinecode",
     "/__external__/prod.spline.design/4asLCgiJDMkz7HAN/scene.splinecode"),
    ("https://kota-content.b-cdn.net/", "/__external__/kota-content.b-cdn.net/"),
    ("https://content.kota.co.uk/", "/__external__/content.kota.co.uk/"),
    ("https://kota.co.uk/_next/", "/_next/"),
    ("https://kota.co.uk/lottie/", "/lottie/"),
    ("https://www.googletagmanager.com/gtag/js?id=", "/__sitecloner/empty.js?gtag="),
    ("https://www.googletagmanager.com/gtm.js?id=", "/__sitecloner/empty.js?gtm="),
    ("https://static.hotjar.com/c/hotjar-", "/__sitecloner/empty.js?hotjar="),
    ("https://connect.facebook.net/en_US/fbevents.js", "/__sitecloner/empty.js?facebook=1"),
    ("https://snap.licdn.com/li.lms-analytics/insight.min.js", "/__sitecloner/empty.js?linkedin=1"),
    ("/prod.spline.design/4asLCgiJDMkz7HAN/scene.splinecode",
     "/__external__/prod.spline.design/4asLCgiJDMkz7HAN/scene.splinecode"),
    ("/__external__/__external__/", "/__external__/"),
]
changed = 0
for p in root.rglob("*"):
    if not p.is_file() or any(part in skip for part in p.parts):
        continue
    if p.suffix.lower() not in text_suffixes:
        continue
    try:
        raw = p.read_bytes()
        if b"\0" in raw[:4096]:
            continue
        s = raw.decode("utf-8")
    except Exception:
        continue
    original = s
    for a, b in replacements:
        s = s.replace(a, b)
    if s != original:
        p.write_text(s, encoding="utf-8")
        changed += 1
print(f"Localized runtime references in {changed} files")
PY

required=(
  "_next/static/chunks/2827-f8fce45e8c1f0443.js"
  "_next/static/chunks/app/contact/page-66896fc7dbdb22ec.js"
  "_next/static/chunks/app/culture/page-580d954c7a372e0a.js"
  "_next/static/css/77de916f6379b329.css"
  "_next/static/css/435828e364f4b5ed.css"
  "_next/static/css/d7552b378bb64018.css"
  "_next/static/css/decc77e58f025ef8.css"
  "__external__/unpkg.com/@splinetool/runtime@1.9.37/build/navmesh.js"
  "__external__/prod.spline.design/4asLCgiJDMkz7HAN/scene.splinecode"
  "lottie/brand-pulse-outlines.json"
  "_libraries/navmesh.js"
  "_libraries/navmesh.wasm"
)
for f in "${required[@]}"; do
  test -s "$f" || { echo "Missing required local file: $f" >&2; exit 1; }
done

echo "Runtime asset restoration complete"
