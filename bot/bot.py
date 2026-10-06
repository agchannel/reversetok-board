#!/usr/bin/env python3
"""리버스톡 그로스 매니저 텔레그램 봇 (Mac Studio 상시 실행)
- 평일 08:30  업계 뉴스(라이브·AI 챗봇·마케팅·정책) 최대 6개
- 평일 10:50  일일 보고 요약 (현황판이 오늘 갱신됐는지 확인, 안 됐으면 11:30·12:30 재시도)
- 아무 때나   질문하면 그로스 매니저가 답함 (Claude Code CLI 사용)
비밀번호(/start 비밀번호)로 등록한 채팅방에만 응답한다."""
import os, re, json, time, base64, subprocess, threading, datetime, traceback
import requests
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = os.path.dirname(os.path.abspath(__file__))
def load_env():
    p = os.path.join(HERE, '.env')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())
load_env()
TOKEN = os.environ['TELEGRAM_TOKEN']
PASSWORD = os.environ['BOARD_PASSWORD']
BOARD_URL = os.environ.get('BOARD_URL', 'https://agchannel.github.io/reversetok-board/')
CLAUDE = os.environ.get('CLAUDE_BIN', 'claude')
API = f'https://api.telegram.org/bot{TOKEN}/'
KST = datetime.timezone(datetime.timedelta(hours=9))
ALLOWED_F = os.path.join(HERE, 'allowed.json')
STATE_F = os.path.join(HERE, 'state.json')
def _load_prompt():
    p = json.load(open(os.path.join(HERE, 'growth_prompt.enc'), encoding='utf-8'))
    k = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=bytes.fromhex(p['s']), iterations=p['n']).derive(PASSWORD.encode())
    return AESGCM(k).decrypt(bytes.fromhex(p['i']), base64.b64decode(p['c']), None).decode('utf-8')
GROWTH_PROMPT = _load_prompt()
HISTORY = {}  # chat_id -> [(q, a)]
LOCK = threading.Lock()
SLOCK = threading.Lock()

def jload(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d
def jsave(p, v): json.dump(v, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
def set_state(k, v):
    with SLOCK:
        st = jload(STATE_F, {}); st[k] = v; jsave(STATE_F, st)
def now(): return datetime.datetime.now(KST)
def log(*a): print(now().strftime('%m-%d %H:%M:%S'), *a, flush=True)

# ---------- Telegram ----------
def tg(method, **params):
    r = requests.post(API + method, json=params, timeout=70)
    return r.json()
def send(chat, text):
    text = text.strip() or '(빈 답변)'
    while text:
        part, text = text[:3900], text[3900:]
        tg('sendMessage', chat_id=chat, text=part, disable_web_page_preview=True)
def broadcast(text):
    for c in jload(ALLOWED_F, []): send(c, text)

# ---------- 현황판 데이터 ----------
def load_board():
    html = requests.get(BOARD_URL + '?t=' + str(int(time.time())), timeout=30).text
    p = json.loads(re.search(r'<script id="enc" type="application/json">(.*?)</script>', html, re.S).group(1))
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=bytes.fromhex(p['s']), iterations=p['n']).derive(PASSWORD.encode())
    page = AESGCM(key).decrypt(bytes.fromhex(p['i']), base64.b64decode(p['c']), None).decode('utf-8')
    m = re.search(r'<script id="dash-data" type="application/json">(.*?)</script>', page, re.S)
    return json.loads(m.group(1).replace('<\\/', '</'))
def growth_of(d): return next(s for s in d['staff'] if s['key'] == 'growth')
def won(v): return '-' if v is None else f'{round(v):,}원'
def num(v): return '-' if v is None else f'{round(v):,}'

def daily_text(d):
    g = growth_of(d); days = d.get('days') or []
    t = [f"[그로스 일일 보고] {g.get('last_report') or ''}", g.get('note') or '']
    if days:
        k, dt = days[0].get('kpi') or {}, days[0]['date']
        pk = (days[1].get('kpi') or {}) if len(days) > 1 else {}
        def ch(a, b): return '' if not a or not b else f" ({(a-b)/b*100:+.0f}%)"
        t += ['', f'■ {dt} 집행 기준',
              f"광고비 {won(k.get('spend'))}{ch(k.get('spend'),pk.get('spend'))}",
              f"설치 {num(k.get('installs'))}{ch(k.get('installs'),pk.get('installs'))} · 가입 {num(k.get('signups'))}{ch(k.get('signups'),pk.get('signups'))}",
              f"설치당 {won(k.get('cpi'))} · 가입당 {won(k.get('cpa'))}{ch(k.get('cpa'),pk.get('cpa'))}"]
    if g.get('highlights'): t += ['', '■ 핵심'] + ['· ' + h for h in g['highlights']]
    if g.get('decisions'): t += ['', '■ 대표님 결정 필요'] + [f'{i+1}. {x}' for i, x in enumerate(g['decisions'])]
    if days and days[0].get('anomalies'): t += ['', '■ 이상 신호'] + ['· ' + a for a in days[0]['anomalies']]
    late = [r for r in g.get('requests', []) if r.get('status') not in ('제출 완료',) and r.get('due') and r['due'] < now().strftime('%Y-%m-%d')]
    if late: t += ['', '■ 미제출'] + [f"· {r['who']} — {r['item']} (마감 {r['due']})" for r in late]
    res = (g.get('results') or [])
    if res: t += ['', f"보고서: {res[0].get('url')}"]
    t += [f'현황판: {BOARD_URL}', '', '궁금한 건 여기 바로 물어보세요.']
    return '\n'.join(x for x in t if x is not None)

# ---------- Claude ----------
def ask_claude(prompt, tools='WebSearch,WebFetch', timeout=300):
    r = subprocess.run([CLAUDE, '-p', '--allowedTools', tools, '--output-format', 'text'],
                       input=prompt, capture_output=True, text=True, timeout=timeout, cwd=HERE)
    out = (r.stdout or '').strip()
    if r.returncode != 0 and not out: raise RuntimeError((r.stderr or 'claude 실행 실패')[-500:])
    return out

def answer(chat, q):
    try:
        d = load_board(); g = growth_of(d)
        ctx = {'updated_at': d.get('updated_at'), 'growth': g, 'days': (d.get('days') or [])[:30]}
    except Exception as e:
        ctx = {'error': f'현황판 데이터를 못 읽음: {e}'}
    hist = HISTORY.get(chat, [])[-6:]
    h = '\n'.join(f'대표님: {a}\n그로스 매니저: {b}' for a, b in hist)
    prompt = (GROWTH_PROMPT + '\n\n[지금 상황]\n- 텔레그램 대화다. 마크다운 표·굵은 글씨 없이 짧은 줄글과 "·" 목록으로 답한다. 최대 15줄.\n'
              '- 아래 현황판 데이터(JSON)가 최신 숫자다. 여기 없는 숫자는 모른다고 말하고 추측하지 않는다. 계산은 정확히 하고 계산식을 짧게 보여준다.\n'
              '- 시장·경쟁사·뉴스 질문은 웹 검색으로 확인하고 출처 링크를 붙인다.\n'
              f'- 오늘: {now():%Y-%m-%d %H:%M} (한국 시간)\n\n[현황판 데이터]\n{json.dumps(ctx, ensure_ascii=False)}\n\n'
              f'[이전 대화]\n{h or "(없음)"}\n\n[대표님 질문]\n{q}\n')
    a = ask_claude(prompt)
    HISTORY[chat] = (hist + [(q, a)])[-6:]
    return a

NEWS_PROMPT = """너는 리버스톡 그로스 매니저다. 리버스톡은 두 가지 서비스를 한다: (1) 틱톡 라이브 같은 모바일 라이브 스트리밍(크리에이터=리톡커, 시청자 코인 후원 매출) (2) AI 챗봇 서비스. 유입은 리워드 앱 광고(CPE·CPA)로 한다.
웹 검색으로 최근 24~48시간 안에 나온 기사만 골라 대표님께 아침 뉴스 브리핑을 쓴다. 국내 기사를 우선하고, 해외는 국내에 영향이 큰 것만 넣는다.
카테고리(각 1~2개, 전체 최대 6개):
[라이브] 틱톡 라이브·유튜브 라이브·SOOP·치지직 등 라이브 스트리밍·숏폼, 후원(별풍선·치즈 등)·크리에이터 수익 구조, 경쟁 서비스 출시·변경
[AI 챗봇] AI 챗봇·AI 캐릭터·AI 컴패니언 서비스(캐릭터닷에이아이, 제타, 뤼튼 등), 신기능·이용자 지표·수익모델, AI 관련 규제(AI 기본법, 청소년 보호)
[마케팅] 앱 마케팅·리워드 광고·유저 획득 비용·앱스플라이어 등 측정, 광고 정책 변경
[정책] 앱마켓 인앱결제 수수료, 플랫폼·방송 규제, 결제·환불 관련
형식(텔레그램, 마크다운 금지):
[업계 뉴스 YYYY-MM-DD]
1. [카테고리] 제목 — 한 줄 요약
   → 리버스톡에 주는 의미 한 줄
   링크
날짜가 확인 안 되거나 오래된 기사, 보도자료 재탕은 넣지 않는다. 해당 카테고리에 새 소식이 없으면 그 카테고리는 건너뛴다. 전부 없으면 "주목할 새 소식 없음"."""

# ---------- 스케줄 ----------
def scheduler():
    while True:
        try:
            n = now()
            with SLOCK: st = jload(STATE_F, {})
            today = n.strftime('%Y-%m-%d'); hm = n.strftime('%H:%M')
            if n.weekday() < 5:
                if hm >= '08:30' and st.get('news') != today:
                    st['news'] = today; set_state('news', today)
                    broadcast(ask_claude(NEWS_PROMPT.replace('YYYY-MM-DD', today)))
                for slot in ('10:50', '11:30', '12:30'):
                    if hm >= slot and st.get('daily') != today and st.get('daily_try_' + slot) != today:
                        st['daily_try_' + slot] = today; set_state('daily_try_' + slot, today)
                        d = load_board(); g = growth_of(d)
                        if (g.get('last_report') or '') == today:
                            st['daily'] = today; set_state('daily', today); broadcast(daily_text(d))
                        elif slot == '12:30':
                            st['daily'] = today; set_state('daily', today)
                            broadcast(f'[그로스 일일 보고] {today} 아직 현황판이 갱신되지 않았습니다. 대행사 파일 제출 여부나 10:29 자동 작업 결과를 확인해 주세요.\n{BOARD_URL}')
        except Exception:
            log('scheduler error', traceback.format_exc()[-800:])
        time.sleep(60)

# ---------- 메시지 처리 ----------
MEMBERS_F = os.path.join(HERE, 'members.json')

def chat_name(msg):
    c = msg['chat']
    if c.get('type') in ('group', 'supergroup'): return '그룹: ' + (c.get('title') or str(c['id']))
    f = msg.get('from') or {}
    return ' '.join(x for x in [f.get('first_name'), f.get('last_name')] if x) or f.get('username') or str(c['id'])

def handle(msg):
    chat = msg['chat']['id']; text = (msg.get('text') or '').strip()
    cmd, arg = '', text
    if text.startswith('/'):
        first, _, rest = text.partition(' ')
        cmd, arg = first.split('@')[0].lower(), rest.strip()
    allowed = jload(ALLOWED_F, [])
    members = jload(MEMBERS_F, {})
    if cmd == '/start':
        if arg == PASSWORD:
            if chat not in allowed: allowed.append(chat); jsave(ALLOWED_F, allowed)
            members[str(chat)] = chat_name(msg); jsave(MEMBERS_F, members)
            send(chat, '등록됐습니다. 평일 08:30 업계 뉴스, 10:50 그로스 일일 보고를 보내드립니다.\n궁금한 건 그냥 물어보세요.\n/report 오늘 보고 · /news 뉴스 지금 받기\n(비밀번호가 담긴 메시지는 삭제해 주세요)')
            if allowed and allowed[0] != chat:
                send(allowed[0], f'새 사용자 등록: {members[str(chat)]}')
        else:
            send(chat, '"/start 비밀번호" 형식으로 보내 주세요.')
        return
    if chat not in allowed: return
    owner = allowed and allowed[0] == chat
    if cmd == '/members':
        lines = [f"{i+1}. {members.get(str(c), c)}{' (관리자)' if i == 0 else ''}" for i, c in enumerate(allowed)]
        send(chat, '등록된 사용자\n' + '\n'.join(lines) + ('\n\n빼려면 /remove 번호' if owner else '')); return
    if cmd == '/remove':
        if not owner: send(chat, '관리자만 할 수 있습니다.'); return
        try:
            i = int(arg) - 1; assert 0 < i < len(allowed)
        except Exception:
            send(chat, '/members 에 나온 번호로 "/remove 2" 처럼 보내 주세요. (1번 관리자는 뺄 수 없습니다)'); return
        gone = allowed.pop(i); jsave(ALLOWED_F, allowed)
        name = members.pop(str(gone), gone); jsave(MEMBERS_F, members)
        send(chat, f'뺐습니다: {name}'); return
    if cmd == '/report':
        send(chat, daily_text(load_board())); return
    if cmd == '/news':
        tg('sendChatAction', chat_id=chat, action='typing')
        send(chat, ask_claude(NEWS_PROMPT.replace('YYYY-MM-DD', now().strftime('%Y-%m-%d')))); return
    if cmd or not text: return
    if msg['chat'].get('type') in ('group', 'supergroup'):
        text = re.sub(r'@\w+bot\b', '', text, flags=re.I).strip()
    tg('sendChatAction', chat_id=chat, action='typing')
    def work():
        with LOCK:
            try: send(chat, answer(chat, text))
            except Exception as e:
                log('answer error', traceback.format_exc()[-800:]); send(chat, f'답변 중 오류가 났습니다: {str(e)[:200]}')
    threading.Thread(target=work, daemon=True).start()

def main():
    log('bot start')
    threading.Thread(target=scheduler, daemon=True).start()
    offset = jload(STATE_F, {}).get('offset', 0)
    while True:
        try:
            r = tg('getUpdates', offset=offset, timeout=50)
            for u in r.get('result', []):
                offset = u['update_id'] + 1
                set_state('offset', offset)
                if 'message' in u: handle(u['message'])
        except Exception:
            log('poll error', traceback.format_exc()[-500:]); time.sleep(5)

if __name__ == '__main__':
    main()
