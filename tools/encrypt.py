#!/usr/bin/env python3
"""리버스톡 현황판 암호화 빌드.
사용: python3 encrypt.py <현황판.html> <출력 index.html>  (환경변수 BOARD_PASSWORD, BOARD_SALT 필요)
현황판 HTML 전체를 AES-256-GCM으로 암호화해 비밀번호 입력 화면 안에 넣는다.
비밀번호 없이는 내용(숫자·결과물 링크)을 읽을 수 없다."""
import sys, os, re, json, base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITER = 310000
src, out = sys.argv[1], sys.argv[2]
pw = os.environ['BOARD_PASSWORD'].encode()
salt = bytes.fromhex(os.environ['BOARD_SALT'])
html = open(src, encoding='utf-8').read()
# Claude 아티팩트용 본문 → 독립 페이지로
html = re.sub(r'<link rel="preconnect"[^>]*>\s*<link rel="stylesheet" href="https://fonts.googleapis.com[^>]*>',
  '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">', html)
if not html.lstrip().lower().startswith('<!doctype'):
    html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow"></head><body>' + html + '</body></html>')
iv = os.urandom(12)
AUTO = ('<script>(function(){var V="'+iv.hex()+'";function chk(){if(document.hidden)return;'
        'fetch(location.pathname+"?t="+Date.now(),{cache:"no-store"}).then(function(r){return r.text()})'
        '.then(function(t){var m=t.match(/"i": ?"([0-9a-f]+)"/);if(m&&m[1]!==V)location.reload()}).catch(function(){})}'
        'setInterval(chk,180000);document.addEventListener("visibilitychange",chk)})();</script>')
html = html.replace('</body>', AUTO + '</body>') if '</body>' in html else html + AUTO
key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pw)
ct = AESGCM(key).encrypt(iv, html.encode('utf-8'), None)
payload = json.dumps({'s': salt.hex(), 'i': iv.hex(), 'n': ITER, 'c': base64.b64encode(ct).decode()})

page = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>리버스톡 운영 현황판</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{--bg:#F6F4F1;--fg:#232327;--muted:#5F5E63;--line:#E2DDD6;--accent:#C3372B;--surface:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#18181B;--fg:#F2F0ED;--muted:#A6A3A0;--line:#34333A;--surface:#232327;--accent:#E0584B}}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--fg);font-family:'Pretendard',system-ui,sans-serif;display:flex;align-items:center;justify-content:center;padding:16px}
.box{width:100%;max-width:360px;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:32px 28px}
.eb{font-size:12px;font-weight:700;letter-spacing:.08em;color:var(--accent)}
h1{font-size:22px;margin:6px 0 4px}p{margin:0 0 20px;color:var(--muted);font-size:14px}
input{width:100%;font:inherit;font-size:16px;padding:12px 14px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--fg)}
input:focus{outline:2px solid var(--accent);outline-offset:1px}
label.r{display:flex;gap:8px;align-items:center;margin:12px 0 18px;font-size:14px;color:var(--muted)}
label.r input{width:auto}
button{width:100%;font:inherit;font-weight:700;font-size:15px;padding:12px;border:0;border-radius:10px;background:var(--fg);color:var(--bg);cursor:pointer}
.err{color:var(--accent);font-size:13px;min-height:18px;margin-top:10px}
</style></head><body>
<form class="box" id="f" autocomplete="on">
<div class="eb">REVERSETOK · 내부용</div>
<h1>운영 현황판</h1>
<p>공유받은 비밀번호를 입력하세요.</p>
<input type="text" name="username" value="reversetok" autocomplete="username" hidden>
<input id="pw" type="password" autocomplete="current-password" placeholder="비밀번호" required autofocus>
<label class="r"><input id="rm" type="checkbox" checked> 이 기기에서 로그인 유지</label>
<button id="b" type="submit">열기</button>
<div class="err" id="e" role="alert"></div>
</form>
<script id="enc" type="application/json">__PAYLOAD__</script>
<script>
(function(){
var P=JSON.parse(document.getElementById('enc').textContent),K='rt_board_key_'+P.s;
function hx(h){var a=new Uint8Array(h.length/2);for(var i=0;i<a.length;i++)a[i]=parseInt(h.substr(i*2,2),16);return a}
function b64(s){var b=atob(s),a=new Uint8Array(b.length);for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);return a}
function show(buf){var h=new TextDecoder().decode(buf);document.open();document.write(h);document.close()}
function dec(raw){return crypto.subtle.importKey('raw',raw,'AES-GCM',true,['decrypt']).then(function(k){return crypto.subtle.decrypt({name:'AES-GCM',iv:hx(P.i)},k,b64(P.c))})}
function get(){try{return localStorage.getItem(K)}catch(e){return null}}
function put(v){try{localStorage.setItem(K,v)}catch(e){}}
function del(){try{localStorage.removeItem(K)}catch(e){}}
var saved=get(),F=document.getElementById('f');
if(saved){F.style.visibility='hidden';dec(b64(saved)).then(show).catch(function(){del();F.style.visibility=''})}
document.getElementById('f').addEventListener('submit',function(ev){
  ev.preventDefault();var btn=document.getElementById('b'),er=document.getElementById('e');
  btn.disabled=true;btn.textContent='확인 중…';er.textContent='';
  crypto.subtle.importKey('raw',new TextEncoder().encode(document.getElementById('pw').value),'PBKDF2',false,['deriveBits'])
  .then(function(m){return crypto.subtle.deriveBits({name:'PBKDF2',hash:'SHA-256',salt:hx(P.s),iterations:P.n},m,256)})
  .then(function(bits){var raw=new Uint8Array(bits);return dec(raw).then(function(buf){
     if(document.getElementById('rm').checked){var s='';raw.forEach(function(x){s+=String.fromCharCode(x)});put(btoa(s))}
     show(buf)})})
  .catch(function(){btn.disabled=false;btn.textContent='열기';er.textContent='비밀번호가 맞지 않습니다.'});
});
})();
</script></body></html>'''
open(out, 'w', encoding='utf-8').write(page.replace('__PAYLOAD__', payload))
print('ok', out, len(page)+len(payload))
