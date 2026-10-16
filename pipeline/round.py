"""추천 레시피 판(round) 도구

사용
  python3 pipeline/round.py status [--today YYYY-MM-DD]
      오늘이 추천 날인지(due), 마지막 판, 다음 추천 날, 관리자 요청, 최근 120일 제목, 이번 달을 JSON으로 알려 줘요.
  python3 pipeline/round.py merge FILE [--today YYYY-MM-DD] [--now ISO] [--force]
      FILE(판 하나: {"title", "note", "recipes": [레시피 3개]})을 새 판으로 더해요.
      start를 비우면 오늘, id를 비우면 r-YYMMDD / rec-YYMMDD-n을 붙여요.
      추천 날이 아니거나 같은 start 판이 있으면 멈춰요. --force면 그래도 더하고, 같은 start 판은 바꿔요
      (그 판의 history 항목도 새 레시피로 바꿔요).
  python3 pipeline/round.py add FILE [--today YYYY-MM-DD] [--now ISO]
      FILE(레시피 1~2개 배열, 하나면 객체도 돼요)을 지금 판에 더해요. 한 판은 최대 4개.
  python3 pipeline/round.py checked [--now ISO]
      data/version.json의 checkedAt만 지금 시각으로 바꿔요.

- 시각은 한국 시간(+09:00 고정), 초는 00. --now는 정해진 시각으로 적을 때(씨앗 데이터·테스트)만 써요.
- merge·add는 data/recommend.json, data/version.json, pipeline/history.json, pipeline/requests.json을 함께 고쳐요.
  쓰기 전에 네 파일을 모두 검증하고, 하나라도 틀리면 아무 파일도 바꾸지 않아요(임시 파일에 쓴 뒤 바꿔치기).
- 최근 120일 history에 있는 요리 제목(띄어쓰기 무시)은 다시 쓰지 않아요. 판은 최근 10개만 남기고, history는 지우지 않아요.
- 관리자 요청(requests.json)에서 제목이 같은 요리는 더한 뒤 빼요.
"""
import argparse
import copy
import datetime
import json
import os
import sys
from pathlib import Path

import validate as V

ROOT = Path(__file__).resolve().parent.parent
KST = datetime.timezone(datetime.timedelta(hours=9))
REQUESTS_NOTE = '관리자가 추천받고 싶은 요리를 적어 두면 다음 추천 때 먼저 써요. title만 적어도 돼요.'


class Fail(Exception):
    pass


# ---------- 시각 ----------

def clock(today_arg=None, now_arg=None):
    """(today: date, now_iso: str)"""
    if now_arg:
        try:
            now = datetime.datetime.fromisoformat(now_arg)
        except ValueError:
            raise Fail(f'--now 형식이 틀렸어요: {now_arg} (예: 2026-10-16T09:00:00+09:00)')
        now = now.replace(tzinfo=KST) if now.tzinfo is None else now.astimezone(KST)
    else:
        now = datetime.datetime.now(KST)
    now = now.replace(second=0, microsecond=0)
    if today_arg:
        today = V.parse_date(today_arg)
        if not today:
            raise Fail(f'--today는 YYYY-MM-DD예요: {today_arg}')
    else:
        today = now.date()
    return today, now.isoformat()


# ---------- 파일 ----------

def paths(root):
    root = Path(root)
    return {
        'rec': root / 'data' / 'recommend.json',
        'ver': root / 'data' / 'version.json',
        'hist': root / 'pipeline' / 'history.json',
        'req': root / 'pipeline' / 'requests.json',
    }


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        if default is None:
            raise Fail(f'파일이 없어요: {path}')
        return default()
    except json.JSONDecodeError as e:
        raise Fail(f'JSON을 읽을 수 없어요: {path}: {e}')


def load_state(root):
    p = paths(root)
    return {
        'rec': read_json(p['rec'], lambda: {'app': V.APP, 'v': V.FORMAT_VERSION, 'updatedAt': '',
                                            'intervalDays': V.INTERVAL_DAYS, 'rounds': []}),
        'ver': read_json(p['ver'], lambda: {}),
        'hist': read_json(p['hist'], lambda: {'items': []}),
        'req': read_json(p['req'], lambda: {'note': REQUESTS_NOTE, 'items': []}),
    }


def to_json(obj, ind=0):
    """읽기 쉬운 JSON: 재료·단계·태그·history 항목처럼 값이 단순한 것은 한 줄로 써요."""
    pad, end = '  ' * (ind + 1), '  ' * ind
    if isinstance(obj, dict) and obj:
        if ind > 0 and all(not isinstance(v, (dict, list)) for v in obj.values()):
            return json.dumps(obj, ensure_ascii=False)
        body = ',\n'.join(f'{pad}{json.dumps(k, ensure_ascii=False)}: {to_json(v, ind + 1)}' for k, v in obj.items())
        return '{\n' + body + '\n' + end + '}'
    if isinstance(obj, list) and obj and any(isinstance(v, (dict, list)) for v in obj):
        return '[\n' + ',\n'.join(pad + to_json(v, ind + 1) for v in obj) + '\n' + end + ']'
    return json.dumps(obj, ensure_ascii=False)


def dump(obj):
    return to_json(obj) + '\n'


def write_all(pairs):
    """모두 임시 파일에 쓴 뒤 한꺼번에 바꿔치기해요."""
    tmps = []
    try:
        for path, obj in pairs:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + '.tmp')
            tmp.write_text(dump(obj), encoding='utf-8')
            tmps.append((tmp, path))
        for tmp, path in tmps:
            os.replace(tmp, path)
    finally:
        for tmp, _ in tmps:
            if tmp.exists():
                tmp.unlink()


# ---------- 계산 ----------

def last_start(rec):
    rounds = rec.get('rounds') or []
    return V.parse_date(rounds[-1]['start']) if rounds else None


def is_due(rec, today):
    last = last_start(rec)
    return last is None or today >= last + datetime.timedelta(days=V.INTERVAL_DAYS)


def next_start(rec, today):
    last = last_start(rec)
    return (last + datetime.timedelta(days=V.INTERVAL_DAYS)) if last else today


def make_version(rec, checked_at):
    rounds = rec.get('rounds') or []
    if rounds:
        last = rounds[-1]
        current = last['id']
        nxt = (V.parse_date(last['start']) + datetime.timedelta(days=V.INTERVAL_DAYS)).isoformat()
    else:
        current, nxt = '', ''
    return {'recommend': rec['updatedAt'], 'checkedAt': checked_at, 'current': current,
            'nextStart': nxt, 'intervalDays': V.INTERVAL_DAYS}


def recent_titles(hist, since_exclusive, skip_start=None):
    """history에서 since_exclusive보다 늦은 start의 제목(순서 유지, 중복 없이)"""
    out = []
    for it in hist.get('items') or []:
        d = V.parse_date(it.get('start'))
        if not d or d <= since_exclusive or it.get('start') == skip_start:
            continue
        if it.get('title') not in out:
            out.append(it.get('title'))
    return out


def ordered_recipe(r):
    out = {k: r[k] for k in V.RECIPE_KEYS if k in r}
    out.update({k: v for k, v in r.items() if k not in out})  # 모르는 칸은 검증에서 걸러요
    return out


def ordered_round(rd):
    out = {k: rd[k] for k in V.ROUND_KEYS if k in rd}
    out.update({k: v for k, v in rd.items() if k not in out})
    return out


def assign_ids(recipes, code, used):
    """id가 없는 레시피에 rec-{code}-n을 붙여요(used에 있는 번호는 피해요)."""
    taken = set(used)
    for r in recipes:
        m = V.RECIPE_ID_RE.match(r['id']) if isinstance(r.get('id'), str) else None
        if m:
            taken.add(int(m.group(2)))
    n = 1
    for r in recipes:
        if 'id' in r:
            continue
        while n in taken:
            n += 1
        r['id'] = f'rec-{code}-{n}'
        taken.add(n)


def fail_on(rep):
    if rep.errors:
        V.print_reports([rep])
        raise Fail(f'{rep.label}에 오류가 {len(rep.errors)}개 있어요. 고친 뒤 다시 해요')


def check_repeats(new_recipes, hist, window_end, skip_start=None, label='새 레시피'):
    """최근 120일 history와 제목이 겹치면 멈춰요."""
    since = window_end - datetime.timedelta(days=V.REPEAT_DAYS)
    recent = {V.norm_title(t): t for t in recent_titles(hist, since, skip_start)}
    hits = [r['title'] for r in new_recipes if V.norm_title(r.get('title', '')) in recent]
    if hits:
        raise Fail(f"{label} 중 최근 {V.REPEAT_DAYS}일 안에 추천한 요리가 있어요: {', '.join(hits)}. 다른 요리로 바꿔요")


def consume_requests(req, titles):
    names = {V.norm_title(t) for t in titles}
    keep, used = [], []
    for it in req.get('items') or []:
        if isinstance(it, dict) and V.norm_title(it.get('title', '')) in names:
            used.append(it.get('title'))
        else:
            keep.append(it)
    out = dict(req)
    out['items'] = keep
    return out, used


def commit_state(root, state, new_state):
    reps = V.check_state(new_state['rec'], new_state['ver'], new_state['hist'], new_state['req'])
    if any(r.errors for r in reps):
        V.print_reports([r for r in reps if r.errors or r.warnings])
        raise Fail('검증에 걸려서 아무 파일도 바꾸지 않았어요')
    p = paths(root)
    pairs = [(p[k], new_state[k]) for k in ('rec', 'ver', 'hist', 'req')
             if k in ('rec', 'ver') or new_state[k] != state[k] or not p[k].exists()]
    write_all(pairs)


def verify_disk(root):
    """쓴 파일을 디스크에서 다시 읽어 검사하고 결과를 짧게 보여 줘요."""
    if V.run(root=root):
        raise Fail('쓴 뒤 검증에서 오류가 났어요. git checkout -- data pipeline 으로 되돌려요')
    return 0


# ---------- 명령 ----------

def cmd_status(root, today):
    st = load_state(root)
    rec, hist, req = st['rec'], st['hist'], st['req']
    last = last_start(rec)
    rounds = rec.get('rounds') or []
    out = {
        'today': today.isoformat(),
        'due': is_due(rec, today),
        'lastStart': last.isoformat() if last else None,
        'nextStart': next_start(rec, today).isoformat(),
        'requests': req.get('items') or [],
        'recentTitles': recent_titles(hist, today - datetime.timedelta(days=V.REPEAT_DAYS)),
        'month': today.month,
        'yymmdd': V.yymmdd(today),
        'recentRounds': [
            {'start': rd['start'], 'title': rd['title'],
             'recipes': [f"{r['title']}({', '.join(r.get('tags') or [])})" for r in rd['recipes']]}
            for rd in rounds[-3:]
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_merge(root, file, today, now_iso, force):
    st = load_state(root)
    rec = st['rec']
    rd = read_json(file)
    if not isinstance(rd, dict):
        raise Fail('판 파일은 {"title", "note", "recipes": [...]} 객체예요')
    rd = copy.deepcopy(rd)
    start = rd.get('start') or today.isoformat()
    start_d = V.parse_date(start)
    if not start_d:
        raise Fail(f'start는 YYYY-MM-DD 날짜예요: {start!r}')
    if start_d > today:
        raise Fail(f'start({start})가 오늘({today})보다 늦어요')
    code = V.yymmdd(start_d)
    if 'id' in rd and rd['id'] != f'r-{code}':
        raise Fail(f"판 id는 start에 맞춰 'r-{code}'이어야 해요(지금 {rd['id']!r}). 비워 두면 붙여 줘요")
    rd['id'], rd['start'] = f'r-{code}', start
    recipes = rd.get('recipes')
    if not isinstance(recipes, list) or len(recipes) != 3:
        n = len(recipes) if isinstance(recipes, list) else 0
        raise Fail(f'새 판은 레시피 3개예요(지금 {n}개). 지금 판에 더할 때는 add를 써요')
    if not all(isinstance(r, dict) for r in recipes):
        raise Fail('recipes에는 레시피 객체만 넣어요')
    rounds = rec.get('rounds') or []
    existing = next((i for i, x in enumerate(rounds) if x.get('start') == start), None)
    last = last_start(rec)
    if not force:
        if not is_due(rec, today):
            raise Fail(f'아직 추천 날이 아니에요(마지막 판 {last}, 다음 추천 {next_start(rec, today)}). '
                       '관리자가 새 판을 원할 때만 --force')
        if existing is not None:
            raise Fail(f'{start} 판이 이미 있어요. 바꾸려면 --force')
        if last and start_d <= last:
            raise Fail(f'start({start})는 마지막 판({last})보다 늦어야 해요')
    replaced = start if existing is not None else None
    # 바꾸는 판이 아니면, 예전에 같은 날짜로 나간 레시피 번호(history)는 피해요
    taken = [] if replaced else [int(it['id'].rsplit('-', 1)[1]) for it in st['hist'].get('items') or []
                                 if isinstance(it.get('id'), str) and it['id'].startswith(f'rec-{code}-')]
    assign_ids(recipes, code, taken)
    rd['recipes'] = [ordered_recipe(r) for r in recipes]
    rd = ordered_round(rd)

    rep = V.Report(str(file))
    V.check_round(rep, rd, '', need_ids=True)
    fail_on(rep)
    check_repeats(rd['recipes'], st['hist'], start_d, skip_start=replaced)

    new_rounds = [x for x in rounds if x.get('start') != start] + [rd]
    new_rounds.sort(key=lambda x: x['start'])
    dropped = new_rounds[:-V.MAX_ROUNDS]
    new_rounds = new_rounds[-V.MAX_ROUNDS:]
    new_rec = {'app': V.APP, 'v': V.FORMAT_VERSION, 'updatedAt': now_iso,
               'intervalDays': V.INTERVAL_DAYS, 'rounds': new_rounds}
    items = [it for it in st['hist'].get('items') or [] if it.get('start') != replaced]
    items += [{'start': start, 'id': r['id'], 'title': r['title']} for r in rd['recipes']]
    items.sort(key=lambda it: it.get('start', ''))
    new_hist = dict(st['hist'])
    new_hist['items'] = items
    new_req, used = consume_requests(st['req'], [r['title'] for r in rd['recipes']])
    new_state = {'rec': new_rec, 'ver': make_version(new_rec, now_iso), 'hist': new_hist, 'req': new_req}
    commit_state(root, st, new_state)

    print(f"{'바꿨어요' if replaced else '더했어요'}: {rd['id']} '{rd['title']}' "
          f"({' · '.join(r['title'] for r in rd['recipes'])})")
    print(f"updatedAt {now_iso}, 판 {len(new_rounds)}개, 다음 추천 {new_state['ver']['nextStart']}")
    if dropped:
        print(f"오래된 판을 뺐어요: {', '.join(x['id'] for x in dropped)} (history에는 남아요)")
    if used:
        print(f"관리자 요청에서 뺐어요: {', '.join(used)}")
    return verify_disk(root)


def cmd_add(root, file, today, now_iso):
    st = load_state(root)
    rec = st['rec']
    items = read_json(file)
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list) or not (1 <= len(items) <= 2) or not all(isinstance(r, dict) for r in items):
        raise Fail('add 파일은 레시피 1~2개(배열, 하나면 객체도 돼요)예요')
    items = copy.deepcopy(items)
    rounds = rec.get('rounds') or []
    if not rounds:
        raise Fail('아직 판이 없어요. merge로 첫 판을 먼저 만들어요')
    cur = copy.deepcopy(rounds[-1])
    if len(cur['recipes']) + len(items) > V.MAX_RECIPES_PER_ROUND:
        raise Fail(f"지금 판({cur['id']})에는 레시피가 {len(cur['recipes'])}개라 {len(items)}개를 더하면 "
                   f'{V.MAX_RECIPES_PER_ROUND}개를 넘어요. requests.json에 넣어 다음 판에서 쓰거나, '
                   '관리자가 원하면 merge --force로 새 판을 만들어요')
    code = cur['id'][2:]
    used = [int(r['id'].rsplit('-', 1)[1]) for r in cur['recipes']]
    used += [int(it['id'].rsplit('-', 1)[1]) for it in st['hist'].get('items') or []
             if isinstance(it.get('id'), str) and it['id'].startswith(f'rec-{code}-')]
    for r in items:
        if 'id' in r and not str(r['id']).startswith(f'rec-{code}-'):
            raise Fail(f"지금 판에 더하는 레시피 id는 'rec-{code}-n'이에요(비워 두면 붙여 줘요)")
    assign_ids(items, code, used)
    items = [ordered_recipe(r) for r in items]
    rep = V.Report(str(file))
    for i, r in enumerate(items):
        V.check_recipe(rep, r, V.join('', i), round_code=code, need_id=True)
    fail_on(rep)
    check_repeats(items, st['hist'], max(today, V.parse_date(cur['start'])), label='더할 레시피')

    cur['recipes'] = cur['recipes'] + items
    new_rec = dict(rec)
    new_rec['rounds'] = rounds[:-1] + [cur]
    new_rec['updatedAt'] = now_iso
    new_hist = dict(st['hist'])
    new_hist['items'] = (st['hist'].get('items') or []) + [
        {'start': cur['start'], 'id': r['id'], 'title': r['title']} for r in items]
    new_req, used_req = consume_requests(st['req'], [r['title'] for r in items])
    new_state = {'rec': new_rec, 'ver': make_version(new_rec, now_iso), 'hist': new_hist, 'req': new_req}
    commit_state(root, st, new_state)

    print(f"지금 판 {cur['id']} '{cur['title']}'에 더했어요: {' · '.join(r['title'] for r in items)} "
          f"(이제 {len(cur['recipes'])}개)")
    print(f'updatedAt {now_iso}')
    if used_req:
        print(f"관리자 요청에서 뺐어요: {', '.join(used_req)}")
    return verify_disk(root)


def cmd_checked(root, now_iso):
    st = load_state(root)
    if not st['ver']:
        raise Fail('data/version.json이 없어요. merge로 첫 판을 먼저 만들어요')
    ver = dict(st['ver'])
    ver['checkedAt'] = now_iso
    new_state = dict(st)
    new_state['ver'] = ver
    commit_state(root, st, new_state)
    print(f'checkedAt {now_iso}')
    return verify_disk(root)


def main(argv=None, root=ROOT):
    ap = argparse.ArgumentParser(prog='round.py', description='추천 레시피 판 도구')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('status')
    s.add_argument('--today')
    m = sub.add_parser('merge')
    m.add_argument('file')
    m.add_argument('--today')
    m.add_argument('--now')
    m.add_argument('--force', action='store_true')
    a = sub.add_parser('add')
    a.add_argument('file')
    a.add_argument('--today')
    a.add_argument('--now')
    c = sub.add_parser('checked')
    c.add_argument('--now')
    args = ap.parse_args(argv)
    try:
        today, now_iso = clock(getattr(args, 'today', None), getattr(args, 'now', None))
        if args.cmd == 'status':
            return cmd_status(root, today)
        if args.cmd == 'merge':
            return cmd_merge(root, args.file, today, now_iso, args.force)
        if args.cmd == 'add':
            return cmd_add(root, args.file, today, now_iso)
        return cmd_checked(root, now_iso)
    except Fail as e:
        print(f'멈췄어요: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
