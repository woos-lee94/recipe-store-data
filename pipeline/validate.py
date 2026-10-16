"""레시피 저장소 '추천 레시피' 검증기

사용
  python3 pipeline/validate.py                    data/recommend.json, data/version.json, pipeline/history.json, pipeline/requests.json을 함께 검사해요
  python3 pipeline/validate.py 파일 [파일2 ...]    파일을 하나씩 검사해요
- 파일 이름이 recommend.json / version.json / history.json / requests.json이면 그 형식으로 봐요.
  그 밖의 파일은 모양으로 알아봐요: 레시피 하나(work/rec_1.json), 레시피 배열(add용), 판 하나(work/round.json).
  work 파일은 id·start를 비워 둬도 돼요(round.py가 붙여요).
- 오류(ERROR)가 하나라도 있으면 종료 코드 1이에요. 경고(WARN)는 되도록 고쳐요.
- 오류마다 어디가 틀렸는지 경로(예: rounds[0].recipes[1].ingredients[2].unit)를 붙여요.
"""
import datetime
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = 'recipe-store'
FORMAT_VERSION = 1
INTERVAL_DAYS = 3
MAX_ROUNDS = 10
MAX_RECIPES_PER_ROUND = 4
REPEAT_DAYS = 120
UNITS = ['g', 'kg', 'ml', 'L', '큰술', '작은술', '컵', '개', '쪽', '대', '모', '줌', '장', '포기', '꼬집', '약간']
TAGS = ['찌개·국', '볶음', '면·밥', '반찬', '한식', '양식', '손님상', '간식']
# 재료 이름에 쓰지 않는 상표 이름(경고만 해요)
BRANDS = ['백설', '청정원', '오뚜기', '샘표', '다시다', '미원', '해찬들', '풀무원', '비비고', '동원', '사조', '농심',
          '삼양', '롯데', '미림', '연두', 'CJ', '스팸', '맛선생']

RECIPE_KEYS = ['id', 'title', 'intro', 'tags', 'servings', 'minutes', 'ingredients', 'steps', 'tip']
ROUND_KEYS = ['id', 'start', 'title', 'note', 'recipes']
RECOMMEND_KEYS = ['app', 'v', 'updatedAt', 'intervalDays', 'rounds']
VERSION_KEYS = ['recommend', 'checkedAt', 'current', 'nextStart', 'intervalDays']
DEFAULT_PATHS = ['data/recommend.json', 'data/version.json', 'pipeline/history.json', 'pipeline/requests.json']

DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
STAMP_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$')
ROUND_ID_RE = re.compile(r'^r-(\d{6})$')
RECIPE_ID_RE = re.compile(r'^rec-(\d{6})-([1-9]\d*)$')
EMOJI_RE = re.compile('[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿️‍\U000E0020-\U000E007F]')
URL_RE = re.compile(r'https?://|www\.|\.(com|net|org|kr|io)\b', re.I)
CONTROL_RE = re.compile(r'[\x00-\x1f\x7f]')


class Report:
    def __init__(self, label):
        self.label = label
        self.errors = []
        self.warnings = []

    def err(self, path, msg):
        self.errors.append(f'{path or "(전체)"}: {msg}')

    def warn(self, path, msg):
        self.warnings.append(f'{path or "(전체)"}: {msg}')


def join(path, key):
    if isinstance(key, int):
        return f'{path}[{key}]'
    return f'{path}.{key}' if path else key


def norm_title(s):
    """제목 비교용: 띄어쓰기를 무시해요('고등어 무조림' = '고등어무조림')."""
    return re.sub(r'\s+', '', str(s))


def parse_date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return None
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def parse_stamp(s):
    if not isinstance(s, str) or not STAMP_RE.match(s):
        return None
    try:
        return datetime.datetime.fromisoformat(s)
    except ValueError:
        return None


def yymmdd(d):
    return d.strftime('%y%m%d')


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def is_number(x):
    return (isinstance(x, (int, float)) and not isinstance(x, bool)) and math.isfinite(x)


# ---------- 공통 검사 ----------

def check_strings(rep, obj, path):
    """모든 글자: 앞뒤 공백 없음, 이모지·주소·줄바꿈 없음"""
    if isinstance(obj, str):
        if obj != obj.strip():
            rep.err(path, '앞뒤 공백을 지워요')
        if EMOJI_RE.search(obj):
            rep.err(path, '이모지는 쓰지 않아요')
        if URL_RE.search(obj):
            rep.err(path, '주소(URL)는 쓰지 않아요')
        if CONTROL_RE.search(obj):
            rep.err(path, '줄바꿈·탭 같은 제어 문자는 쓰지 않아요')
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            check_strings(rep, x, join(path, i))
    elif isinstance(obj, dict):
        for k, x in obj.items():
            check_strings(rep, x, join(path, k))


def check_text(rep, obj, key, path, lo, hi):
    p = join(path, key)
    if key not in obj:
        rep.err(p, '칸이 없어요')
        return
    v = obj[key]
    if not isinstance(v, str):
        rep.err(p, '글자(string)여야 해요')
        return
    n = len(v.strip())
    if n < lo or n > hi:
        rep.err(p, f'{lo}~{hi}자여야 해요(지금 {n}자)')


def check_keys(rep, obj, path, allowed, required):
    for k in obj:
        if k not in allowed:
            rep.err(join(path, k), f"알 수 없는 칸이에요(쓸 수 있는 칸: {', '.join(allowed)})")
    for k in required:
        if k not in obj:
            rep.err(join(path, k), '칸이 없어요')


# ---------- 레시피 ----------

def timer_in_text(text, minutes):
    """timer 분이 단계 글에 그대로 적혀 있는지(예: 20 → '20분', 60 → '1시간', 90 → '1시간 30분')"""
    if re.search(rf'(?<!\d){minutes}분', text):
        return True
    h, m = divmod(minutes, 60)
    if h and m == 0 and re.search(rf'(?<!\d){h}시간', text):
        return True
    if h and m and re.search(rf'(?<!\d){h}시간 ?{m}분', text):
        return True
    return False


def check_ingredient(rep, ing, path):
    if not isinstance(ing, dict):
        rep.err(path, '재료는 {name, qty, unit} 객체여야 해요')
        return None
    check_keys(rep, ing, path, ['name', 'qty', 'unit'], ['name', 'qty', 'unit'])
    check_text(rep, ing, 'name', path, 1, 20)
    name = ing.get('name') if isinstance(ing.get('name'), str) else ''
    if re.search(r'[()\[\],/]|\d', name):
        rep.warn(join(path, 'name'), f"재료 이름은 짧고 일반적으로(괄호·숫자·쉼표 없이): '{name}'")
    for b in BRANDS:
        if b in name:
            rep.warn(join(path, 'name'), f"상표 이름 같아요('{b}'). 일반 이름으로 써요")
    unit = ing.get('unit')
    qty = ing.get('qty')
    if 'unit' in ing:
        if unit not in UNITS:
            rep.err(join(path, 'unit'), f"단위 '{unit}'은(는) 쓸 수 없어요(쓸 수 있는 단위: {', '.join(UNITS)})")
    if 'qty' in ing and unit in UNITS:
        if unit == '약간':
            if qty is not None:
                rep.err(join(path, 'qty'), "단위가 '약간'이면 qty는 null이어야 해요")
        elif qty is None:
            rep.err(join(path, 'qty'), f"단위가 '{unit}'이면 qty에 양수를 적어요(양을 정하기 어려우면 단위를 '약간'으로)")
        elif not is_number(qty) or qty <= 0 or qty > 10000:
            rep.err(join(path, 'qty'), f'qty는 0보다 크고 10000 이하인 숫자여야 해요(지금 {qty!r})')
        elif round(qty, 2) != qty:
            rep.warn(join(path, 'qty'), f'qty는 소수 둘째 자리까지만 써요(지금 {qty})')
    return name


def check_step(rep, st, path):
    if not isinstance(st, dict):
        rep.err(path, '단계는 {text, timer} 객체여야 해요')
        return 0
    check_keys(rep, st, path, ['text', 'timer'], ['text', 'timer'])
    check_text(rep, st, 'text', path, 5, 200)
    timer = st.get('timer')
    if 'timer' in st and (not is_int(timer) or timer < 0 or timer > 600):
        rep.err(join(path, 'timer'), f'timer는 0~600 사이 정수(분)여야 해요(지금 {timer!r})')
        return 0
    text = st.get('text') if isinstance(st.get('text'), str) else ''
    if is_int(timer) and timer > 0 and not timer_in_text(text, timer):
        rep.warn(join(path, 'timer'), f"timer {timer}분이 단계 글에 없어요(글에 '{timer}분'처럼 같은 시간을 적어요)")
    return timer if is_int(timer) else 0


def check_recipe(rep, r, path, round_code=None, need_id=True):
    """레시피 하나. round_code는 그 판의 YYMMDD(있으면 id와 맞춰 봐요)."""
    if not isinstance(r, dict):
        rep.err(path, '레시피는 객체여야 해요')
        return
    required = RECIPE_KEYS if need_id else [k for k in RECIPE_KEYS if k != 'id']
    check_keys(rep, r, path, RECIPE_KEYS, required)
    if 'id' in r:
        m = RECIPE_ID_RE.match(str(r['id'])) if isinstance(r['id'], str) else None
        if not m:
            rep.err(join(path, 'id'), f"id는 'rec-YYMMDD-n' 형식이어야 해요(지금 {r['id']!r})")
        elif round_code and m.group(1) != round_code:
            rep.err(join(path, 'id'), f"id의 날짜가 판 날짜와 달라요(rec-{round_code}-n 이어야 해요)")
    check_text(rep, r, 'title', path, 1, 20)
    check_text(rep, r, 'intro', path, 1, 60)
    check_text(rep, r, 'tip', path, 0, 120)

    tags = r.get('tags')
    if 'tags' in r:
        if not isinstance(tags, list) or not (1 <= len(tags) <= 3):
            rep.err(join(path, 'tags'), '태그는 1~3개 배열이어야 해요')
        else:
            seen = set()
            for i, t in enumerate(tags):
                tp = join(join(path, 'tags'), i)
                if not isinstance(t, str) or not (1 <= len(t.strip()) <= 12):
                    rep.err(tp, '태그는 1~12자 글자여야 해요')
                    continue
                if t in seen:
                    rep.err(tp, f"태그 '{t}'가 겹쳐요")
                seen.add(t)
                if t not in TAGS:
                    rep.warn(tp, f"태그 '{t}'는 앱 기본 분류가 아니에요(되도록 {', '.join(TAGS)} 중에서)")

    servings = r.get('servings')
    if 'servings' in r and (not is_int(servings) or not (1 <= servings <= 20)):
        rep.err(join(path, 'servings'), f'servings는 1~20 사이 정수여야 해요(지금 {servings!r})')
    minutes = r.get('minutes')
    if 'minutes' in r and (not is_int(minutes) or not (1 <= minutes <= 999)):
        rep.err(join(path, 'minutes'), f'minutes는 1~999 사이 정수여야 해요(지금 {minutes!r})')

    ings = r.get('ingredients')
    if 'ingredients' in r:
        ip = join(path, 'ingredients')
        if not isinstance(ings, list) or not (2 <= len(ings) <= 30):
            rep.err(ip, '재료는 2~30개 배열이어야 해요')
        if isinstance(ings, list):
            names = {}
            for i, ing in enumerate(ings):
                name = check_ingredient(rep, ing, join(ip, i))
                if name:
                    if name in names:
                        rep.warn(join(join(ip, i), 'name'), f"재료 '{name}'가 {names[name]}번째와 겹쳐요(한 줄로 합쳐요)")
                    names.setdefault(name, i)

    steps = r.get('steps')
    if 'steps' in r:
        sp = join(path, 'steps')
        if not isinstance(steps, list) or not (2 <= len(steps) <= 12):
            rep.err(sp, '단계는 2~12개 배열이어야 해요')
        if isinstance(steps, list):
            total = sum(check_step(rep, st, join(sp, i)) for i, st in enumerate(steps))
            if is_int(minutes) and total > minutes:
                rep.warn(join(path, 'minutes'), f'단계 timer를 더하면 {total}분인데 minutes는 {minutes}분이에요')
    check_strings(rep, r, path)


# ---------- 판(round) ----------

def check_round(rep, rd, path, need_ids=True):
    if not isinstance(rd, dict):
        rep.err(path, '판은 객체여야 해요')
        return
    required = ROUND_KEYS if need_ids else ['title', 'note', 'recipes']
    check_keys(rep, rd, path, ROUND_KEYS, required)
    code = None
    if 'start' in rd:
        d = parse_date(rd['start'])
        if not d:
            rep.err(join(path, 'start'), f"start는 YYYY-MM-DD 날짜여야 해요(지금 {rd['start']!r})")
        else:
            code = yymmdd(d)
    if 'id' in rd:
        if not isinstance(rd['id'], str) or not ROUND_ID_RE.match(rd['id']):
            rep.err(join(path, 'id'), f"판 id는 'r-YYMMDD' 형식이어야 해요(지금 {rd['id']!r})")
        elif code and rd['id'] != f'r-{code}':
            rep.err(join(path, 'id'), f"판 id는 start에 맞춰 'r-{code}'이어야 해요")
    check_text(rep, rd, 'title', path, 1, 30)
    check_text(rep, rd, 'note', path, 0, 80)
    for k in ('id', 'start'):
        if k in rd:
            check_strings(rep, rd[k], join(path, k))
    for k in ('title', 'note'):
        if k in rd:
            check_strings(rep, rd[k], join(path, k))
    recs = rd.get('recipes')
    if 'recipes' not in rd:
        return
    rp = join(path, 'recipes')
    if not isinstance(recs, list) or not (1 <= len(recs) <= MAX_RECIPES_PER_ROUND):
        rep.err(rp, f'판의 레시피는 1~{MAX_RECIPES_PER_ROUND}개 배열이어야 해요(보통 3개)')
    if not isinstance(recs, list):
        return
    ids, titles = {}, {}
    for i, r in enumerate(recs):
        p = join(rp, i)
        check_recipe(rep, r, p, round_code=code, need_id=need_ids)
        if isinstance(r, dict):
            if isinstance(r.get('id'), str):
                if r['id'] in ids:
                    rep.err(join(p, 'id'), f"id '{r['id']}'가 겹쳐요")
                ids[r['id']] = i
            t = norm_title(r.get('title', ''))
            if t and t in titles:
                rep.err(join(p, 'title'), f"같은 판에 같은 요리 '{r.get('title')}'가 있어요")
            titles[t] = i


# ---------- 파일 ----------

def check_recommend(rep, data):
    if not isinstance(data, dict):
        rep.err('', 'recommend.json은 객체여야 해요')
        return
    check_keys(rep, data, '', RECOMMEND_KEYS, RECOMMEND_KEYS)
    if 'app' in data and data['app'] != APP:
        rep.err('app', f"app은 '{APP}'이어야 해요")
    if 'v' in data and (not is_int(data['v']) or data['v'] != FORMAT_VERSION):
        rep.err('v', f'v는 {FORMAT_VERSION}이어야 해요')
    if 'updatedAt' in data and not parse_stamp(data['updatedAt']):
        rep.err('updatedAt', "updatedAt은 'YYYY-MM-DDTHH:MM:SS+09:00' 형식이어야 해요")
    if 'intervalDays' in data and (not is_int(data['intervalDays']) or data['intervalDays'] != INTERVAL_DAYS):
        rep.err('intervalDays', f'intervalDays는 {INTERVAL_DAYS}이어야 해요')
    rounds = data.get('rounds')
    if 'rounds' not in data:
        return
    if not isinstance(rounds, list):
        rep.err('rounds', '판 배열이어야 해요')
        return
    if not rounds:
        rep.warn('rounds', '아직 판이 없어요')
    if len(rounds) > MAX_ROUNDS:
        rep.err('rounds', f'판은 최대 {MAX_ROUNDS}개까지 둬요(지금 {len(rounds)}개)')
    round_ids, recipe_ids, titles = {}, {}, {}
    prev = None
    for i, rd in enumerate(rounds):
        p = join('rounds', i)
        check_round(rep, rd, p, need_ids=True)
        if not isinstance(rd, dict):
            continue
        rid = rd.get('id')
        if isinstance(rid, str):
            if rid in round_ids:
                rep.err(join(p, 'id'), f"판 id '{rid}'가 rounds[{round_ids[rid]}]와 겹쳐요")
            round_ids[rid] = i
        d = parse_date(rd.get('start'))
        if d and prev:
            if d <= prev:
                rep.err(join(p, 'start'), f'판은 start 오름차순이고 하루 이상 떨어져야 해요({prev} 다음이 {d})')
        if d:
            prev = d
        for j, r in enumerate(rd.get('recipes') or []):
            if not isinstance(r, dict):
                continue
            rp = join(join(p, 'recipes'), j)
            if isinstance(r.get('id'), str):
                if r['id'] in recipe_ids:
                    rep.err(join(rp, 'id'), f"레시피 id '{r['id']}'가 {recipe_ids[r['id']]}와 겹쳐요")
                else:
                    recipe_ids[r['id']] = rp
            t = norm_title(r.get('title', ''))
            if t:
                if t in titles and titles[t].split('.recipes')[0] != p:
                    rep.err(join(rp, 'title'), f"같은 요리 '{r.get('title')}'가 {titles[t]}에도 있어요")
                titles.setdefault(t, rp)


def check_version(rep, v, rec=None):
    if not isinstance(v, dict):
        rep.err('', 'version.json은 객체여야 해요')
        return
    check_keys(rep, v, '', VERSION_KEYS, VERSION_KEYS)
    for k in ('recommend', 'checkedAt'):
        if k in v and not parse_stamp(v[k]):
            rep.err(k, f"{k}는 'YYYY-MM-DDTHH:MM:SS+09:00' 형식이어야 해요")
    if 'intervalDays' in v and (not is_int(v['intervalDays']) or v['intervalDays'] != INTERVAL_DAYS):
        rep.err('intervalDays', f'intervalDays는 {INTERVAL_DAYS}이어야 해요')
    a, b = parse_stamp(v.get('recommend')), parse_stamp(v.get('checkedAt'))
    if a and b and b < a:
        rep.err('checkedAt', 'checkedAt이 recommend보다 빨라요')
    if 'current' in v and not isinstance(v['current'], str):
        rep.err('current', '판 id 글자여야 해요')
    if 'nextStart' in v and v['nextStart'] != '' and not parse_date(v['nextStart']):
        rep.err('nextStart', 'nextStart는 YYYY-MM-DD 날짜여야 해요')
    if not isinstance(rec, dict):
        return
    if v.get('recommend') != rec.get('updatedAt'):
        rep.err('recommend', f"recommend.json의 updatedAt({rec.get('updatedAt')})과 같아야 해요")
    rounds = [r for r in (rec.get('rounds') or []) if isinstance(r, dict)]
    if rounds:
        last = rounds[-1]
        if v.get('current') != last.get('id'):
            rep.err('current', f"마지막 판 id({last.get('id')})여야 해요")
        d = parse_date(last.get('start'))
        if d:
            want = (d + datetime.timedelta(days=INTERVAL_DAYS)).isoformat()
            if v.get('nextStart') != want:
                rep.err('nextStart', f'마지막 판 start + {INTERVAL_DAYS}일({want})이어야 해요')
    else:
        if v.get('current') != '' or v.get('nextStart') != '':
            rep.err('current', "판이 없으면 current와 nextStart는 빈 글자('')예요")


def check_history(rep, h, rec=None):
    if not isinstance(h, dict) or not isinstance(h.get('items'), list):
        rep.err('items', 'history.json은 {"items": [...]} 형식이어야 해요')
        return
    check_keys(rep, h, '', ['items'], ['items'])
    ids = {}
    for i, it in enumerate(h['items']):
        p = join('items', i)
        if not isinstance(it, dict):
            rep.err(p, '{start, id, title} 객체여야 해요')
            continue
        check_keys(rep, it, p, ['start', 'id', 'title'], ['start', 'id', 'title'])
        d = parse_date(it.get('start'))
        if not d:
            rep.err(join(p, 'start'), 'start는 YYYY-MM-DD 날짜여야 해요')
        m = RECIPE_ID_RE.match(it['id']) if isinstance(it.get('id'), str) else None
        if not m:
            rep.err(join(p, 'id'), "id는 'rec-YYMMDD-n' 형식이어야 해요")
        else:
            if d and m.group(1) != yymmdd(d):
                rep.err(join(p, 'id'), 'id의 날짜가 start와 달라요')
            if it['id'] in ids:
                rep.err(join(p, 'id'), f"id '{it['id']}'가 items[{ids[it['id']]}]와 겹쳐요")
            ids[it['id']] = i
        check_text(rep, it, 'title', p, 1, 20)
        check_strings(rep, it, p)
    if not isinstance(rec, dict):
        return
    by_id = {it.get('id'): it for it in h['items'] if isinstance(it, dict)}
    for i, rd in enumerate(rec.get('rounds') or []):
        if not isinstance(rd, dict):
            continue
        for j, r in enumerate(rd.get('recipes') or []):
            if not isinstance(r, dict):
                continue
            it = by_id.get(r.get('id'))
            where = f"rounds[{i}].recipes[{j}]"
            if not it:
                rep.err('items', f"{where}({r.get('id')})가 history에 없어요")
            elif it.get('title') != r.get('title') or it.get('start') != rd.get('start'):
                rep.err('items', f"{where}({r.get('id')})의 제목·start가 history와 달라요")


def check_requests(rep, q):
    if not isinstance(q, dict) or not isinstance(q.get('items'), list):
        rep.err('items', 'requests.json은 {"note": "...", "items": [...]} 형식이어야 해요')
        return
    check_keys(rep, q, '', ['note', 'items'], ['items'])
    if 'note' in q and not isinstance(q['note'], str):
        rep.err('note', '글자여야 해요')
    seen = {}
    for i, it in enumerate(q['items']):
        p = join('items', i)
        if not isinstance(it, dict):
            rep.err(p, '{"title": "...", "memo": "..."} 객체여야 해요')
            continue
        check_keys(rep, it, p, ['title', 'memo'], ['title'])
        check_text(rep, it, 'title', p, 1, 20)
        if 'memo' in it:
            check_text(rep, it, 'memo', p, 0, 80)
        t = norm_title(it.get('title', ''))
        if t and t in seen:
            rep.warn(join(p, 'title'), f'items[{seen[t]}]와 같은 요리예요')
        seen.setdefault(t, i)
        check_strings(rep, it, p)


def check_state(rec, ver, hist, req):
    """네 파일을 함께 검사해요(round.py가 쓰기 전에 불러요). [Report, ...]"""
    reps = []
    for label, data, fn in (('data/recommend.json', rec, lambda r, d: check_recommend(r, d)),
                            ('data/version.json', ver, lambda r, d: check_version(r, d, rec)),
                            ('pipeline/history.json', hist, lambda r, d: check_history(r, d, rec)),
                            ('pipeline/requests.json', req, lambda r, d: check_requests(r, d))):
        rep = Report(label)
        fn(rep, data)
        reps.append(rep)
    return reps


# ---------- 파일 읽기와 실행 ----------

def kind_of(path, data):
    name = Path(path).name
    if name in ('recommend.json', 'version.json', 'history.json', 'requests.json'):
        return name.split('.')[0]
    if isinstance(data, list):
        return 'recipes'
    if isinstance(data, dict):
        if 'rounds' in data:
            return 'recommend'
        if 'recipes' in data:
            return 'round'
        if 'ingredients' in data or 'steps' in data:
            return 'recipe'
        if 'nextStart' in data or 'current' in data:
            return 'version'
        if 'items' in data:
            return 'requests' if 'note' in data else 'history'
    return None


def check_paths(paths):
    loaded, reps = [], []
    for p in paths:
        rep = Report(str(p))
        try:
            data = json.loads(Path(p).read_text(encoding='utf-8'))
        except FileNotFoundError:
            rep.err('', '파일이 없어요')
            reps.append(rep)
            continue
        except json.JSONDecodeError as e:
            rep.err('', f'JSON을 읽을 수 없어요: {e}')
            reps.append(rep)
            continue
        loaded.append((rep, kind_of(p, data), data))
        reps.append(rep)
    by_kind = {k: d for _, k, d in loaded}
    rec = by_kind.get('recommend')
    for rep, kind, data in loaded:
        if kind == 'recommend':
            check_recommend(rep, data)
        elif kind == 'version':
            check_version(rep, data, rec)
        elif kind == 'history':
            check_history(rep, data, rec)
        elif kind == 'requests':
            check_requests(rep, data)
        elif kind == 'round':
            check_round(rep, data, '', need_ids=False)
            if isinstance(data, dict) and isinstance(data.get('recipes'), list) and len(data['recipes']) != 3:
                rep.warn('recipes', f"새 판은 레시피 3개예요(지금 {len(data['recipes'])}개)")
        elif kind == 'recipe':
            check_recipe(rep, data, '', need_id=False)
        elif kind == 'recipes':
            if not (1 <= len(data) <= 2):
                rep.err('', 'add용 레시피 배열은 1~2개예요')
            for i, r in enumerate(data):
                check_recipe(rep, r, join('', i), need_id=False)
        else:
            rep.err('', '어떤 파일인지 알 수 없어요(레시피·판·recommend·version·history·requests)')
    return reps


def print_reports(reps):
    total = 0
    for rep in reps:
        total += len(rep.errors)
        print(f'== {rep.label}: 오류 {len(rep.errors)}개, 경고 {len(rep.warnings)}개')
        for m in rep.errors:
            print('ERROR', m)
        for m in rep.warnings:
            print('WARN ', m)
    return total


def run(paths=None, root=ROOT):
    if paths:
        return print_reports(check_paths(paths))
    reps = check_paths([Path(root) / p for p in DEFAULT_PATHS])
    for rep, label in zip(reps, DEFAULT_PATHS):
        rep.label = label
    return print_reports(reps)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    return 1 if run(args) else 0


if __name__ == '__main__':
    sys.exit(main())
