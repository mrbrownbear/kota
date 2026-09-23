from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "__sitecloner"
HOME = ROOT / "_next/static/chunks/app/(home)/page-b58f77e3dc47742c.js"

SAFE_KICK = """(()=>{
  const kick=()=>{
    try{window.dispatchEvent(new Event('scroll'));}catch(e){}
  };
  const run=()=>{
    kick();
    requestAnimationFrame(()=>requestAnimationFrame(kick));
    setTimeout(kick,500);
    if(document.fonts&&document.fonts.ready)document.fonts.ready.then(kick).catch(()=>{});
    document.querySelectorAll('img,video').forEach(el=>{
      el.addEventListener('load',kick,{once:true});
      el.addEventListener('loadedmetadata',kick,{once:true});
    });
  };
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',run,{once:true}):run();
  window.addEventListener('load',run,{once:true});
})();
"""

OLD_HERO = 'let e=s.p8.timeline({duration:1,ease:"power3.out"}),t=document.querySelector(".rebelLetters").getBBox().height,n=document.querySelector(".againstLetters").getBBox().height,r=document.querySelector(".boringLetters").getBBox().height;e.set'
NEW_HERO = 'let e=s.p8.timeline({duration:1,ease:"power3.out"}),t=(()=>{try{return document.querySelector(".rebelLetters").getBBox().height}catch(e){return 166.8}})(),n=(()=>{try{return document.querySelector(".againstLetters").getBBox().height}catch(e){return 231}})(),r=(()=>{try{return document.querySelector(".boringLetters").getBBox().height}catch(e){return 231.7}})();e.set'


def main():
    SITE.mkdir(exist_ok=True)
    (SITE / "animation-kick.js").write_text(SAFE_KICK, encoding="utf-8")

    if not HOME.exists():
        raise SystemExit("homepage bundle missing")

    js = HOME.read_text(encoding="utf-8", errors="ignore")
    original = js
    if OLD_HERO in js:
        js = js.replace(OLD_HERO, NEW_HERO, 1)
    elif NEW_HERO not in js:
        raise SystemExit("native hero timeline signature not found; refusing broad patch")

    # Safety checks: preserve the original hero SVG groups, masks and video module.
    required = (
        'className:"rebelLetters"',
        'className:"againstLetters"',
        'className:"boringLetters"',
        'className:"rebelMask"',
        'className:"againstMask"',
        'className:"boringMask"',
        'video:"HeroVideo_video__OoWDY"',
    )
    missing = [marker for marker in required if marker not in js]
    if missing:
        raise SystemExit(f"hero asset markers missing after patch: {missing}")

    if js != original:
        HOME.write_text(js, encoding="utf-8")

    kick = (SITE / "animation-kick.js").read_text(encoding="utf-8")
    if "new Event('resize')" in kick:
        raise SystemExit("synthetic resize still present")

    print("Native KOTA animation repair applied without altering hero assets")


if __name__ == "__main__":
    main()
