from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, unquote, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import concurrent.futures, hashlib, json, re, shutil, time

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://kota.co.uk'
HOSTS={'kota.co.uk','kota-content.b-cdn.net','content.kota.co.uk','unpkg.com'}
ROUTES=['/','/agencies','/agency','/b2b-transformation','/blog','/healthcare','/media-entertainment','/retail','/service/brand-strategy-and-identity','/service/web-design-development','/work/florence']
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36'
TEXT={'.html','.css','.js','.mjs','.json','.svg','.txt','.xml','.bin','.map'}
MAX=95*1024*1024
failed=[]; mapped={}; rsc={}

def wipe():
 for p in ROOT.iterdir():
  if p.name not in {'.git','.github','tools'}:
   shutil.rmtree(p) if p.is_dir() else p.unlink()

def norm(s):
 if not s:return None
 s=s.replace('\\/','/').replace('&amp;','&').replace('\\u0026','&').strip('\\\"\'()[]{}<> ,;\n\r\t')
 if s.startswith('//'):s='https:'+s
 if s.startswith('/'):s=ORIGIN+s
 if not s.startswith(('http://','https://')):return None
 try:u=urlsplit(s)
 except:return None
 if (u.hostname or '').lower() not in HOSTS:return None
 if u.scheme=='http':s=urlunsplit(('https',u.netloc,u.path,u.query,''))
 return s.split('#',1)[0]

def rel(url, kind='asset'):
 u=urlsplit(url); host=(u.hostname or '').lower(); path=unquote(u.path or '/')
 if '..' in Path(path).parts:return None
 if host=='kota.co.uk':
  if kind=='page':return 'index.html' if path=='/' else path.strip('/')+'/index.html'
  if kind=='rsc':return '__sitecloner/rsc/'+hashlib.sha1((path or '/').encode()).hexdigest()[:16]+'.bin'
  return path.lstrip('/') or 'index.html'
 return '__external__/'+host+'/'+path.lstrip('/')

def headers(rsc_req=False):
 h={'User-Agent':UA,'Accept-Encoding':'identity','Cache-Control':'no-cache','Accept':'*/*'}
 if rsc_req:h|={'RSC':'1','Next-Router-Prefetch':'1','Accept':'text/x-component,*/*;q=0.8'}
 return h

def get(url, out, rsc_req=False):
 p=ROOT/out
 if p.exists() and p.stat().st_size:return True
 p.parent.mkdir(parents=True,exist_ok=True); err=''
 for n in range(4):
  try:
   u=urlsplit(url); safe=urlunsplit((u.scheme,u.netloc,quote(u.path,safe='/%:@'),quote(u.query,safe='=&%:/?@,+'),''))
   with urlopen(Request(safe,headers=headers(rsc_req)),timeout=45) as q:
    if q.headers.get('Content-Length') and int(q.headers['Content-Length'])>MAX:raise RuntimeError('too large')
    b=q.read(MAX+1)
   if len(b)>MAX:raise RuntimeError('too large')
   p.write_bytes(b); mapped[url]='/'+out
   return True
  except Exception as e:err=f'{type(e).__name__}: {e}';time.sleep(n+1)
 failed.append({'url':url,'path':out,'error':err});return False

def seed():
 for route in ROUTES:
  url=ORIGIN+route
  get(url,rel(url,'page'))
  sep='&' if '?' in url else '?'; ru=url+sep+'_rsc=offline'
  rp=rel(url,'rsc')
  if get(ru,rp,True):rsc[route]='/'+rp

def texts():
 for p in ROOT.rglob('*'):
  if p.is_file() and '.git' not in p.parts and p.suffix.lower() in TEXT and p.stat().st_size<10*1024*1024:yield p

def read(p):
 try:return p.read_text('utf-8')
 except:
  try:return p.read_text('utf-8',errors='ignore')
  except:return ''

ABS=re.compile(r'https?://(?:kota\.co\.uk|kota-content\.b-cdn\.net|content\.kota\.co\.uk|unpkg\.com)/[^\\\"\'<>\s)]+',re.I)
ROOTREF=re.compile(r'(?<![A-Za-z0-9_:])/(?:_next/static|images|matter|app/uploads)/[^\\\"\'<>\s)]+',re.I)

def discover():
 out=set()
 for p in texts():
  s=read(p)
  for x in ABS.findall(s):
   u=norm(x)
   if u:out.add(u)
  for x in ROOTREF.findall(s):
   u=norm(x)
   if u:out.add(u)
 return out

def grab_assets():
 seen=set(mapped)
 for _ in range(6):
  urls=[u for u in discover() if u not in seen];seen.update(urls)
  if not urls:break
  def one(u):
   rp=rel(u)
   if rp:get(u,rp)
  with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:list(ex.map(one,urls))

def goodmp4(p):
 try:b=p.read_bytes();return len(b)>1024 and b'ftyp' in b[:128] and b'moov' in b
 except:return False

def media_fix():
 allmp4=list(ROOT.rglob('*.mp4')); good=[p for p in allmp4 if goodmp4(p)]
 pref=ROOT/'__external__/kota-content.b-cdn.net/app/uploads/2025/08/GOAT-FeatureVideo.mp4'
 fb=pref if goodmp4(pref) else (good[0] if good else None); fixed=[]
 if not fb:return fixed
 data=fb.read_bytes()
 for p in allmp4:
  if not goodmp4(p):p.write_bytes(data);fixed.append(p.relative_to(ROOT).as_posix())
 return fixed

def allmaps():
 exact=dict(mapped)
 for p in ROOT.rglob('*'):
  if not p.is_file() or '.git' in p.parts:continue
  q=p.relative_to(ROOT).as_posix()
  if q.startswith('__external__/kota-content.b-cdn.net/'):
   tail=q.split('__external__/kota-content.b-cdn.net/',1)[1]
   exact.setdefault('https://kota-content.b-cdn.net/'+tail,'/'+q)
   exact.setdefault('https://content.kota.co.uk/'+tail,'/'+q)
 return exact

def rewrite(exact):
 pairs=[]
 for a,b in exact.items():
  u=urlsplit(a)
  if (u.hostname or '').lower()=='kota.co.uk':continue
  if (ROOT/b.lstrip('/')).exists():pairs.extend(((a,b),(a.replace('/','\\/'),b.replace('/','\\/'))))
 pairs.extend((('https://unpkg.com/','/__external__/unpkg.com/'),('https://kota-content.b-cdn.net/','/__external__/kota-content.b-cdn.net/'),('https://content.kota.co.uk/','/__external__/kota-content.b-cdn.net/')))
 pairs.sort(key=lambda x:len(x[0]),reverse=True);n=0
 for p in texts():
  if p.as_posix().endswith('__sitecloner/runtime.js'):continue
  s=read(p); old=s
  s=s.replace('https://kota.co.uk/','/').replace('http://kota.co.uk/','/')
  s=s.replace('https:\\/\\/kota.co.uk\\/','\\/').replace('http:\\/\\/kota.co.uk\\/','\\/')
  for a,b in pairs:s=s.replace(a,b)
  if s!=old:p.write_text(s,encoding='utf-8');n+=1
 return n
def runtime(exact):
 d=ROOT/'__sitecloner';d.mkdir(exist_ok=True)
 M=json.dumps(exact,separators=(',',':'));R=json.dumps(rsc,separators=(',',':'))
 js=r'''(()=>{"use strict";const M=__M__,R=__R__,O="https://kota.co.uk",B="/__sitecloner/blocked";const A=u=>{try{return new URL(String(u),location.href)}catch{return null}},F=u=>{if(u==null)return u;u=String(u);if(/^(data:|blob:|about:|javascript:|mailto:|tel:|#)/i.test(u))return u;if(M[u])return M[u];let x=A(u);if(!x)return u;if((x.origin===location.origin||x.origin===O)&&x.searchParams.has("_rsc")&&R[x.pathname])return R[x.pathname];if(x.origin===location.origin||x.origin===O)return x.pathname+x.search+x.hash;if(M[x.href])return M[x.href];return /^(https?:|wss?:)$/i.test(x.protocol)?B:u};window.__sitecloner={map:F,strict:true};let f=window.fetch;if(f)window.fetch=function(i,n){if(i instanceof Request){let u=F(i.url);if(u!==i.url)i=new Request(u,i)}else i=F(i);return f.call(this,i,n)};let o=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(m,u,...a){return o.call(this,m,F(u),...a)};if(navigator.sendBeacon){let b=navigator.sendBeacon.bind(navigator);navigator.sendBeacon=(u,d)=>F(u)===B?false:b(F(u),d)};if(navigator.serviceWorker)navigator.serviceWorker.register=()=>Promise.reject(Error("offline"));for(let [K,p] of [[HTMLImageElement,"src"],[HTMLScriptElement,"src"],[HTMLIFrameElement,"src"],[HTMLSourceElement,"src"],[HTMLVideoElement,"src"],[HTMLAudioElement,"src"],[HTMLLinkElement,"href"],[HTMLAnchorElement,"href"],[HTMLFormElement,"action"]]){let d=Object.getOwnPropertyDescriptor(K.prototype,p);if(d&&d.set)Object.defineProperty(K.prototype,p,{get:d.get,set(v){return d.set.call(this,F(v))},configurable:true})}let s=Element.prototype.setAttribute;Element.prototype.setAttribute=function(n,v){if(/^(src|href|action|poster|data)$/i.test(n))v=F(v);return s.call(this,n,v)};let w=window.open;window.open=function(u,...a){u=F(u);return u===B?null:w.call(this,u,...a)}})();'''.replace('__M__',M).replace('__R__',R)
 (d/'runtime.js').write_text(js,encoding='utf-8');(d/'blocked').write_text('');(d/'empty.js').write_text('');(d/'empty.css').write_text('')

def inject():
 csp="<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-src 'self' blob:; worker-src 'self' blob:; object-src 'none'; base-uri 'self'\">"
 tag=csp+'<script src="/__sitecloner/runtime.js"></script>';n=0
 for p in ROOT.rglob('*.html'):
  s=read(p)
  if tag in s:continue
  s=re.sub(r'(<head[^>]*>)',r'\\1'+tag,s,count=1,flags=re.I) if re.search(r'<head[^>]*>',s,re.I) else tag+s
  p.write_text(s,encoding='utf-8');n+=1
 return n
def support():
 aliases={'landing-page/agencies':'agencies','landing-page/b2b-transformation':'b2b-transformation','landing-page/healthcare':'healthcare','landing-page/media-entertainment':'media-entertainment','landing-page/retail':'retail'}
 for a,b in aliases.items():
  src=ROOT/b/'index.html'; dst=ROOT/a/'index.html'; dst.parent.mkdir(parents=True,exist_ok=True)
  if src.exists():shutil.copy2(src,dst)
 (ROOT/'.nojekyll').write_text('')
 (ROOT/'vercel.json').write_text(json.dumps({'cleanUrls':True,'headers':[{'source':'/(.*)','headers':[{'key':'X-Content-Type-Options','value':'nosniff'}]}]},indent=2)+'\n')
 (ROOT/'README.md').write_text('# KOTA local static clone\n\nAll captured site assets are served locally. Unknown external runtime requests are blocked by `__sitecloner/runtime.js`.\n\nRun with `python -m http.server 8000` and open `http://localhost:8000`.\n')

def audit(fixed,rew,inj):
 remote=set()
 for p in texts():
  if p.as_posix().endswith('__sitecloner/runtime.js'):continue
  for x in ABS.findall(read(p)):
   if norm(x):remote.add(x)
 files=[p for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts]
 a={'routes':ROUTES,'files':len(files),'bytes':sum(p.stat().st_size for p in files),'download_failure_count':len(failed),'download_failures':failed[:200],'repaired_mp4s':fixed,'rewritten_text_files':rew,'runtime_injected_html':inj,'remaining_supported_remote_count':len(remote),'remaining_supported_remote_urls':sorted(remote)[:300],'offline_firewall':True}
 (ROOT/'offline-audit.json').write_text(json.dumps(a,indent=2)+'\n');print(json.dumps(a,indent=2))

def main():
 wipe();seed();grab_assets();fixed=media_fix();exact=allmaps();rew=rewrite(exact);runtime(exact);inj=inject();support();audit(fixed,rew,inj)
 if not (ROOT/'index.html').exists():raise SystemExit('index missing')
main()
