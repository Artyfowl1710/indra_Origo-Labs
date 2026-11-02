"""Build the standalone GitHub Pages handbook. No external runtime CDN."""
from pathlib import Path
import json,re,shutil,html,posixpath
import markdown

ROOT=Path(__file__).resolve().parents[1]
BOOK=ROOT/'docs/handbook'
OUT=ROOT/'site'
REPO='https://github.com/Artyfowl1710/indra_Origo-Labs'

CSS='''
:root{color-scheme:dark;--bg:#071f22;--panel:#102e32;--ink:#f5eadb;--muted:#b5cecb;--accent:#60ddd0;--line:#315359}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 80% 0,#134448,transparent 55%),var(--bg);color:var(--ink);font:16px/1.75 system-ui,sans-serif}a{color:var(--accent);text-underline-offset:4px}header{height:78px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 32px;position:sticky;top:0;background:#071f22f2;z-index:2}header a{color:var(--ink);text-decoration:none}.brand{font-size:24px;font-weight:800}.brand small{font-size:10px;letter-spacing:3px;margin-left:12px;color:var(--accent)}.layout{display:grid;grid-template-columns:255px minmax(0,880px);gap:48px;max-width:1270px;margin:auto;padding:36px 28px}aside{position:sticky;top:110px;height:calc(100vh - 145px);overflow:auto}nav a{display:block;padding:7px 12px;color:var(--muted);text-decoration:none;border-radius:8px;font-size:14px}nav a[aria-current]{background:#285356;color:#fff;border-left:3px solid var(--accent)}nav a:hover{background:#173c40;color:#fff}input{width:100%;padding:12px;border-radius:8px;background:var(--panel);color:var(--ink);border:1px solid var(--line);margin-bottom:16px}h1{font-size:clamp(30px,4vw,48px);line-height:1.15;letter-spacing:-1.5px;margin:0 0 30px}h2{font-size:26px;margin-top:42px;line-height:1.3}h3{font-size:20px}p,li{color:var(--muted)}strong{color:var(--ink)}main{min-width:0}img,video{display:block;max-width:100%;height:auto;border:1px solid var(--line);border-radius:15px;margin:24px 0}pre{overflow:auto;padding:22px;border:1px solid var(--line);border-radius:12px;background:#05191c;line-height:1.6}code{font-family:ui-monospace,Consolas,monospace;font-size:.88em}p code,li code,td code{background:#204248;padding:2px 5px;border-radius:4px;color:#e4fdf8}table{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow:auto}td,th{padding:13px;text-align:left;border:1px solid var(--line);vertical-align:top}th{background:var(--panel)}blockquote{border-left:3px solid var(--accent);padding-left:20px}footer{border-top:1px solid var(--line);margin-top:60px;padding:22px 0;font-size:13px;color:var(--muted)}.eyebrow{color:var(--accent);letter-spacing:3px;font-size:11px;font-weight:700;margin-bottom:16px}.next{display:flex;justify-content:space-between;margin-top:48px;gap:20px}.search-results{display:none}.search-results a{display:block;padding:8px 0}.search-results p{font-size:13px}.show{display:block}@media(max-width:800px){header{padding:0 18px}.brand small{display:none}.layout{display:block;padding:24px 18px}aside{position:relative;top:0;height:auto;margin-bottom:28px}nav{display:flex;overflow:auto;gap:6px}nav a{white-space:nowrap}h1{letter-spacing:-1px}header .repo{font-size:13px}}@media(prefers-color-scheme:light){:root{color-scheme:light;--bg:#f5f8f4;--panel:#eaf1ed;--ink:#12383b;--muted:#375a5c;--accent:#006f68;--line:#b9cdca}body{background:var(--bg)}header{background:#f5f8f4f5}nav a[aria-current]{background:#d6eae2;color:#12383b}nav a:hover{background:#d6eae2;color:#12383b}pre{background:#edf4ef;color:#12383b}p code,li code,td code{background:#e1ece6;color:#12383b}}
'''

def rewrite(content,source):
 def link(m):
  attr,url=m.group(1),html.unescape(m.group(2))
  if re.match(r'^(https?:|mailto:|#|data:)',url):return m.group(0)
  filename,sep,anchor=url.partition('#')
  target=(source.parent/filename).resolve()
  if target.parent==BOOK.resolve() and target.suffix=='.md':result=target.stem+'.html'
  elif target.is_relative_to((ROOT/'docs/media').resolve()):result='media/'+target.relative_to(ROOT/'docs/media').as_posix()
  elif target.is_relative_to(ROOT):result=REPO+'/blob/main/'+target.relative_to(ROOT).as_posix()
  else:result=url
  return f'{attr}="{html.escape(result+(sep+anchor if sep else ""),quote=True)}"'
 return re.sub(r'(href|src)="([^"]+)"',link,content)

def main():
 OUT.mkdir(exist_ok=True)
 shutil.copytree(ROOT/'docs/media',OUT/'media',dirs_exist_ok=True)
 city=ROOT/'indra/SIH-26/hermes-agent/web/public/media/indra-city.mp4'
 if city.exists():shutil.copyfile(city,OUT/'media/indra-city.mp4')
 (OUT/'.nojekyll').write_text('')
 hero_css='''.city-hero{margin:24px 0 30px;position:relative;height:440px;overflow:hidden;border:1px solid var(--line);border-radius:20px;background:#062126}.city-hero video{margin:0;border:0;border-radius:0;width:100%;height:100%;object-fit:cover;opacity:.82}.hero-copy{position:absolute;inset:0;padding:36px;background:linear-gradient(90deg,#041c20df,transparent 95%);display:flex;flex-direction:column;justify-content:center}.hero-copy span{font-size:11px;letter-spacing:3px;color:#71e5d2;font-weight:800}.hero-copy h2{font-size:clamp(30px,4vw,49px);letter-spacing:-1.5px;line-height:1.12;color:#fff2de;margin:20px 0}.hero-copy p{color:#d6e6dc;font-size:15px;max-width:360px}.city-hero button{position:absolute;right:18px;bottom:18px;background:#062126df;color:#fff2de;border:1px solid #85bcb4;border-radius:20px;padding:8px 15px;cursor:pointer}@media(max-width:600px){.city-hero{height:350px}.hero-copy{padding:22px}.hero-copy p{max-width:240px;font-size:13px}}'''
 (OUT/'style.css').write_text(CSS+hero_css,encoding='utf-8')
 (OUT/'hero.js').write_text('''(()=>{const v=document.querySelector('#city-hero-video'),b=document.querySelector('#hero-motion');if(!v||!b)return;const reduced=matchMedia('(prefers-reduced-motion: reduce)');let allowed=!reduced.matches;const sync=()=>{if(allowed&&!document.hidden)v.play().catch(()=>{});else v.pause();b.textContent=allowed?'Pause scene':'Play scene'};b.addEventListener('click',()=>{allowed=!allowed;sync()});reduced.addEventListener('change',e=>{allowed=!e.matches;sync()});document.addEventListener('visibilitychange',sync);sync()})();''',encoding='utf-8')
 order=['index','installation','judges','projects','providers','knowledge','artifacts','phone','voice','audit','architecture','development','testing','release','troubleshooting','limitations','evidence']
 pages=[]
 for slug in order:
  source=BOOK/(slug+'.md');text=source.read_text(encoding='utf-8');title=text.splitlines()[0].lstrip('# ')
  pages.append({'slug':slug,'title':title,'source':source,'text':text})
 search=[{'title':p['title'],'url':p['slug']+'.html','text':re.sub(r'[#`*\[\]()]',' ',p['text'])} for p in pages]
 (OUT/'search.json').write_text(json.dumps(search,ensure_ascii=False),encoding='utf-8')
 (OUT/'search.js').write_text('''let pages;const input=document.querySelector('#search'),results=document.querySelector('#results');input.addEventListener('input',async()=>{const q=input.value.trim().toLowerCase();results.replaceChildren();results.classList.toggle('show',q.length>1);if(q.length<2)return;pages??=await fetch('search.json').then(r=>r.json());for(const p of pages.filter(p=>(p.title+' '+p.text).toLowerCase().includes(q)).slice(0,8)){const a=document.createElement('a');a.href=p.url;a.textContent=p.title;results.append(a)}});''')
 # Keep local-file search working without a network/CORS exception.
 search_script=OUT/'search.js'
 search_script.write_text(search_script.read_text(encoding='utf-8').replace('let pages;','let pages='+json.dumps(search,ensure_ascii=True)+';'),encoding='utf-8')
 for i,p in enumerate(pages):
  nav=''.join(f'<a href="{x["slug"]}.html"'+(' aria-current="page"' if x==p else '')+'>'+html.escape(x['title'])+'</a>' for x in pages)
  content=rewrite(markdown.markdown(p['text'],extensions=['fenced_code','tables','toc','sane_lists']),p['source'])
  previous=f'<a href="{pages[i-1]["slug"]}.html">← {html.escape(pages[i-1]["title"])}</a>' if i else '<span></span>'
  following=f'<a href="{pages[i+1]["slug"]}.html">{html.escape(pages[i+1]["title"])} →</a>' if i+1<len(pages) else ''
  document=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Indra by Origo Labs: the native agent workstation handbook."><title>{html.escape(p['title'])} · Indra</title><link rel="stylesheet" href="style.css"></head><body><header><a class="brand" href="index.html">◉ Indra <small>ORIGO LABS</small></a><a class="repo" href="{REPO}">Source & releases ↗</a></header><div class="layout"><aside><label for="search">Search the handbook</label><input id="search" type="search" placeholder="Projects, models, phone…"><div id="results" class="search-results" aria-live="polite"></div><nav aria-label="Handbook">{nav}</nav></aside><main><div class="eyebrow">INDRA / USER & DEVELOPER GUIDE</div>{content}<div class="next">{previous}{following}</div><footer>Indra · Origo Labs · 1.8.0-rc.1<br>Local-first agent workstation. Original upstream notices retained in the source.<br><a href="{REPO}/blob/main/{p['source'].relative_to(ROOT).as_posix()}">Edit this page</a> · <a href="{REPO}/blob/main/HACKATHON.md">Contribution boundary</a></footer></main></div><script src="search.js" defer></script></body></html>'''
  document=document.replace('</body>','<script src="hero.js" defer></script></body>')
  (OUT/(p['slug']+'.html')).write_text(document,encoding='utf-8')
 print(json.dumps({'pages':len(pages),'output':str(OUT)}))

if __name__=='__main__':main()
