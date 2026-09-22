from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "__sitecloner"

TRANSITION_STYLE = 'style="position:fixed;z-index:50;width:100vw;height:100vh;background:#efefef"'
TRANSITION_STYLE_FIXED = 'style="position:fixed;z-index:50;width:100vw;height:100vh;background:#efefef;clip-path:polygon(0 100%, 100% 100%, 100% 100%, 0 100%);pointer-events:none;opacity:0"'


def read(path):
    return path.read_text(encoding="utf-8", errors="ignore")


def write_support_files():
    SITE.mkdir(exist_ok=True)
    (SITE / "empty.js").write_text("/* intentionally empty local analytics stub */\n", encoding="utf-8")
    (SITE / "runtime.js").write_text(
        '(()=>{"use strict";window.__sitecloner={local:true};})();\n',
        encoding="utf-8",
    )
    (SITE / "fixes.css").write_text(
        """/* Local clone compatibility fixes. */
body > div[style*="position:fixed"][style*="z-index:50"][style*="width:100vw"][style*="height:100vh"][style*="background:#efefef"] {
  clip-path: polygon(0 100%, 100% 100%, 100% 100%, 0 100%) !important;
  pointer-events: none !important;
  opacity: 0 !important;
  visibility: hidden !important;
}
""",
        encoding="utf-8",
    )


def repair_html():
    changed = []
    for path in ROOT.rglob("*.html"):
        if ".git" in path.parts:
            continue
        html = read(path)
        original = html

        # A previous injector replaced the opening head tag with the literal text \1.
        html = html.replace(
            '\\1<meta http-equiv="Content-Security-Policy"',
            '<head><meta http-equiv="Content-Security-Policy"',
            1,
        )

        # Remove the old browser monkeypatch and restrictive CSP. Static assets are
        # already local, so neither is required and both can interfere with hydration.
        html = re.sub(
            r'<meta\s+http-equiv=["\']Content-Security-Policy["\'][^>]*>',
            "",
            html,
            flags=re.I,
        )
        html = re.sub(
            r'<script\s+src=["\']/__sitecloner/runtime\.js["\']\s*></script>',
            "",
            html,
            flags=re.I,
        )

        # Remove automatic external analytics preloads. Analytics is also neutralised
        # inside the layout chunk below.
        html = re.sub(
            r'<link\s+rel=["\']preload["\']\s+href=["\']https://www\.googletagmanager\.com/[^"\']+["\']\s+as=["\']script["\']\s*/?>',
            "",
            html,
            flags=re.I,
        )

        # Guarantee a valid head element even if an older malformed clone is repaired.
        if not re.search(r'<head(?:\s[^>]*)?>', html, flags=re.I):
            html = re.sub(
                r'(<html[^>]*>)',
                lambda m: m.group(1) + "<head>",
                html,
                count=1,
                flags=re.I,
            )

        # Hide the SSR route transition curtain immediately. The client chunk is also
        # patched so React agrees with this state after hydration.
        html = html.replace(TRANSITION_STYLE, TRANSITION_STYLE_FIXED)

        # A tiny stylesheet is enough for a fail-safe without mutating DOM prototypes.
        fixes_tag = '<link rel="stylesheet" href="/__sitecloner/fixes.css" data-local-fix="true"/>'
        html = html.replace(fixes_tag, "")
        html = re.sub(
            r'(<head(?:\s[^>]*)?>)',
            lambda m: m.group(1) + fixes_tag,
            html,
            count=1,
            flags=re.I,
        )

        if html != original:
            path.write_text(html, encoding="utf-8")
            changed.append(path.relative_to(ROOT).as_posix())
    return changed


def patch_layout_chunk():
    chunks = sorted((ROOT / "_next/static/chunks/app").glob("layout-*.js"))
    if not chunks:
        raise SystemExit("layout chunk not found")

    changed = []
    for path in chunks:
        js = read(path)
        original = js

        # The original transition curtain starts fully visible and only GSAP hides it
        # in useEffect. Start it hidden instead, so hydration can never leave a white
        # full-screen panel over the site.
        js = js.replace(
            'style:{position:"fixed",zIndex:50,width:"100vw",height:"100vh",background:"#efefef"}',
            'style:{position:"fixed",zIndex:50,width:"100vw",height:"100vh",background:"#efefef",clipPath:"polygon(0 100%, 100% 100%, 100% 100%, 0 100%)",pointerEvents:"none",opacity:0}',
        )

        # Static hosting does not provide the Next server required by client RSC route
        # transitions. Use normal document navigation so every captured page hydrates
        # from its own local HTML instead of getting stuck behind the transition curtain.
        js = js.replace(
            'i=async e=>{a("PENDING"),n.prefetch(e),setTimeout(()=>{window.scrollTo(0,-100),n.push(e,{scroll:!0})},1e3)}',
            'i=async e=>{window.location.assign(e)}',
        )

        # Keep analytics from creating live network requests after hydration.
        js = js.replace(
            'https://www.googletagmanager.com/gtag/js?id=',
            '/__sitecloner/empty.js?gtag=',
        )
        js = js.replace(
            'https://www.googletagmanager.com/gtm.js?id=',
            '/__sitecloner/empty.js?gtm=',
        )

        if js != original:
            path.write_text(js, encoding="utf-8")
            changed.append(path.relative_to(ROOT).as_posix())
    return changed


def validate():
    problems = []
    html_files = list(ROOT.rglob("*.html"))
    for path in html_files:
        if ".git" in path.parts:
            continue
        html = read(path)
        rel = path.relative_to(ROOT).as_posix()
        if not re.search(r'<head(?:\s[^>]*)?>', html, flags=re.I):
            problems.append({"file": rel, "issue": "missing head"})
        if '\\1<meta http-equiv="Content-Security-Policy"' in html:
            problems.append({"file": rel, "issue": "literal backreference remains"})
        if 'http-equiv="Content-Security-Policy"' in html:
            problems.append({"file": rel, "issue": "legacy CSP remains"})
        if '<script src="/__sitecloner/runtime.js"></script>' in html:
            problems.append({"file": rel, "issue": "legacy runtime injection remains"})
        if TRANSITION_STYLE in html:
            problems.append({"file": rel, "issue": "visible transition curtain remains"})

    layout_files = list((ROOT / "_next/static/chunks/app").glob("layout-*.js"))
    for path in layout_files:
        js = read(path)
        if 'style:{position:"fixed",zIndex:50,width:"100vw",height:"100vh",background:"#efefef"}' in js:
            problems.append({"file": path.relative_to(ROOT).as_posix(), "issue": "client transition curtain still starts visible"})
        if 'https://www.googletagmanager.com/gtag/js?id=' in js or 'https://www.googletagmanager.com/gtm.js?id=' in js:
            problems.append({"file": path.relative_to(ROOT).as_posix(), "issue": "live analytics URL remains"})

    report = {
        "html_files_checked": len(html_files),
        "layout_files_checked": len(layout_files),
        "problem_count": len(problems),
        "problems": problems,
    }
    (ROOT / "hydration-repair-validation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    if problems:
        raise SystemExit(f"hydration repair validation failed: {len(problems)} problems")


def main():
    write_support_files()
    html_changed = repair_html()
    layout_changed = patch_layout_chunk()
    validate()
    print(json.dumps({"html_changed": html_changed, "layout_changed": layout_changed}, indent=2))


if __name__ == "__main__":
    main()
