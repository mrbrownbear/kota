from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "__sitecloner"

TRANSITION_STYLE = 'style="position:fixed;z-index:50;width:100vw;height:100vh;background:#efefef"'
TRANSITION_STYLE_FIXED = 'style="position:fixed;z-index:50;width:100vw;height:100vh;background:#efefef;clip-path:polygon(0 100%, 100% 100%, 100% 100%, 0 100%);pointer-events:none;opacity:0"'
TRANSITION_JS = 'style:{position:"fixed",zIndex:50,width:"100vw",height:"100vh",background:"#efefef"}'
TRANSITION_JS_FIXED = 'style:{position:"fixed",zIndex:50,width:"100vw",height:"100vh",background:"#efefef",clipPath:"polygon(0 100%, 100% 100%, 100% 100%, 0 100%)",pointerEvents:"none",opacity:0}'


def read(path):
    return path.read_text(encoding="utf-8", errors="ignore")


def write_support_files():
    SITE.mkdir(exist_ok=True)
    (SITE / "empty.js").write_text(
        "window.dataLayer=window.dataLayer||[];window.gtag=window.gtag||function(){window.dataLayer.push(arguments)};\n",
        encoding="utf-8",
    )
    (SITE / "runtime.js").write_text(
        '(()=>{"use strict";window.__sitecloner={local:true};})();\n',
        encoding="utf-8",
    )
    (SITE / "fixes.css").write_text(
        """/* Local clone compatibility fixes. Keep the original React DOM unchanged. */
body > div[style="position:fixed;z-index:50;width:100vw;height:100vh;background:#efefef"] {
  clip-path: polygon(0 100%, 100% 100%, 100% 100%, 0 100%) !important;
  pointer-events: none !important;
  opacity: 0 !important;
  visibility: hidden !important;
}
""",
        encoding="utf-8",
    )
    (SITE / "animation-kick.js").write_text(
        """(()=>{
  const kick=()=>{
    try{window.dispatchEvent(new Event('resize'));}catch(e){}
    try{window.dispatchEvent(new Event('scroll'));}catch(e){}
  };
  const run=()=>{
    kick();
    requestAnimationFrame(()=>requestAnimationFrame(kick));
    setTimeout(kick,120);
    setTimeout(kick,500);
    setTimeout(kick,1200);
    if(document.fonts&&document.fonts.ready)document.fonts.ready.then(kick).catch(()=>{});
    document.querySelectorAll('img,video').forEach(el=>{
      el.addEventListener('load',kick,{once:true});
      el.addEventListener('loadedmetadata',kick,{once:true});
    });
  };
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',run,{once:true}):run();
  window.addEventListener('load',run,{once:true});
})();
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

        # Repair the malformed head introduced by the first reconstruction pass.
        html = html.replace(
            '\\1<meta http-equiv="Content-Security-Policy"',
            '<head><meta http-equiv="Content-Security-Policy"',
            1,
        )
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
        html = re.sub(
            r'<link\s+rel=["\']preload["\']\s+href=["\']https://www\.googletagmanager\.com/[^"\']+["\']\s+as=["\']script["\']\s*/?>',
            "",
            html,
            flags=re.I,
        )

        if not re.search(r'<head(?:\s[^>]*)?>', html, flags=re.I):
            html = re.sub(
                r'(<html[^>]*>)',
                lambda m: m.group(1) + "<head>",
                html,
                count=1,
                flags=re.I,
            )

        # Critical hydration fix: the DOM emitted by React must be byte-for-byte
        # compatible with the captured SSR markup. Undo the previous inline-style
        # mutation and use CSS alone to keep the route curtain visually hidden.
        html = html.replace(TRANSITION_STYLE_FIXED, TRANSITION_STYLE)

        fixes_tag = '<link rel="stylesheet" href="/__sitecloner/fixes.css" data-local-fix="true"/>'
        kick_tag = '<script src="/__sitecloner/animation-kick.js" defer data-local-animation-kick="true"></script>'
        html = html.replace(fixes_tag, "").replace(kick_tag, "")
        html = re.sub(
            r'(<head(?:\s[^>]*)?>)',
            lambda m: m.group(1) + fixes_tag + kick_tag,
            html,
            count=1,
            flags=re.I,
        )

        if html != original:
            path.write_text(html, encoding="utf-8")
            changed.append(path.relative_to(ROOT).as_posix())
    return changed


def patch_all_client_chunks():
    changed = []
    chunks = list((ROOT / "_next/static/chunks").rglob("*.js"))
    if not chunks:
        raise SystemExit("client chunks not found")

    for path in chunks:
        js = read(path)
        original = js

        # Restore the original React-rendered transition style everywhere. The
        # fail-safe stylesheet hides it without creating a hydration mismatch.
        js = js.replace(TRANSITION_JS_FIXED, TRANSITION_JS)

        # The same NavigationContext module is duplicated in several chunks. Patch
        # every copy so asynchronous script order cannot resurrect RSC navigation.
        js = js.replace(
            'i=async e=>{a("PENDING"),n.prefetch(e),setTimeout(()=>{window.scrollTo(0,-100),n.push(e,{scroll:!0})},1e3)}',
            'i=async e=>{window.location.assign(e)}',
        )
        js = js.replace(
            's=async e=>{i("PENDING"),n.prefetch(e),setTimeout(()=>{window.scrollTo(0,-100),n.push(e,{scroll:!0})},1e3)}',
            's=async e=>{window.location.assign(e)}',
        )

        # Analytics must remain local, but the local stub defines gtag so consent
        # effects cannot throw after hydration.
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
    html_files = [p for p in ROOT.rglob("*.html") if ".git" not in p.parts]
    for path in html_files:
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
        if TRANSITION_STYLE_FIXED in html:
            problems.append({"file": rel, "issue": "hydration-breaking transition style remains"})
        if '/__sitecloner/animation-kick.js' not in html:
            problems.append({"file": rel, "issue": "animation kick missing"})

    chunk_files = list((ROOT / "_next/static/chunks").rglob("*.js"))
    stale_transition = []
    stale_navigation = []
    for path in chunk_files:
        js = read(path)
        rel = path.relative_to(ROOT).as_posix()
        if TRANSITION_JS_FIXED in js:
            stale_transition.append(rel)
        if 'n.prefetch(e),setTimeout(()=>{window.scrollTo(0,-100),n.push(e,{scroll:!0})},1e3)' in js:
            stale_navigation.append(rel)
    for rel in stale_transition:
        problems.append({"file": rel, "issue": "hydration-breaking client transition style remains"})
    for rel in stale_navigation:
        problems.append({"file": rel, "issue": "stale Next RSC navigation remains"})

    homepage = ROOT / "_next/static/chunks/app/(home)/page-b58f77e3dc47742c.js"
    if homepage.exists():
        h = read(homepage)
        for marker in ('scrollTrigger:', 'IntersectionObserver', 'SplitText'):
            if marker not in h:
                problems.append({"file": homepage.relative_to(ROOT).as_posix(), "issue": f"animation marker missing: {marker}"})
    else:
        problems.append({"file": str(homepage.relative_to(ROOT)), "issue": "homepage animation chunk missing"})

    report = {
        "html_files_checked": len(html_files),
        "client_chunks_checked": len(chunk_files),
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
    chunks_changed = patch_all_client_chunks()
    validate()
    print(json.dumps({"html_changed": html_changed, "client_chunks_changed": chunks_changed}, indent=2))


if __name__ == "__main__":
    main()
