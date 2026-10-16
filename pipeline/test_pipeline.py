"""추천 레시피 도구 테스트

실행: python3 -m unittest discover -s pipeline
"""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

import round as rnd
import validate as V

REPO = Path(__file__).resolve().parent.parent


def recipe(title):
    return {
        'title': title,
        'intro': '시험용 레시피예요.',
        'tags': ['반찬', '한식'],
        'servings': 2,
        'minutes': 20,
        'ingredients': [
            {'name': '두부', 'qty': 1, 'unit': '모'},
            {'name': '대파', 'qty': 0.5, 'unit': '대'},
            {'name': '소금', 'qty': None, 'unit': '약간'},
        ],
        'steps': [
            {'text': '두부는 한입 크기로 썬다.', 'timer': 0},
            {'text': '중불에서 10분 굽는다.', 'timer': 10},
        ],
        'tip': '',
    }


def round_obj(*titles, **extra):
    rd = {'title': '시험 판', 'note': '', 'recipes': [recipe(t) for t in titles]}
    rd.update(extra)
    return rd


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / 'data').mkdir()
        (self.root / 'pipeline').mkdir()
        (self.root / 'work').mkdir()
        self.n = 0

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, obj):
        p = self.root / rel
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        return str(p)

    def read(self, rel):
        return json.loads((self.root / rel).read_text(encoding='utf-8'))

    def run_cmd(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rnd.main(list(argv), root=self.root)
        return code, out.getvalue(), err.getvalue()

    def merge(self, rd, day, *extra):
        self.n += 1
        f = self.write(f'work/round{self.n}.json', rd)
        return self.run_cmd('merge', f, '--today', day, '--now', f'{day}T05:10:00+09:00', *extra)

    def snapshot(self):
        return {p.name: p.read_text(encoding='utf-8')
                for p in [self.root / 'data' / 'recommend.json', self.root / 'data' / 'version.json',
                          self.root / 'pipeline' / 'history.json', self.root / 'pipeline' / 'requests.json']
                if p.exists()}

    def errors_of(self, check, data, *args, **kw):
        rep = V.Report('t')
        check(rep, data, *args, **kw)
        return rep.errors


class ValidateTest(Base):
    def test_repo_data_passes(self):
        """저장소에 올라간 data/·pipeline/ 파일이 검증을 통과해요."""
        reps = V.check_paths([REPO / p for p in V.DEFAULT_PATHS])
        self.assertEqual([e for r in reps for e in r.errors], [])

    def test_valid_file_passes(self):
        code, _, err = self.merge(round_obj('두부구이', '감자조림', '시금치나물'), '2026-10-16')
        self.assertEqual(code, 0, err)
        reps = V.check_paths([self.root / p for p in V.DEFAULT_PATHS])
        self.assertEqual([e for r in reps for e in r.errors], [])

    def test_bad_unit_fails(self):
        r = recipe('두부구이')
        r['ingredients'][0]['unit'] = '스푼'
        errs = self.errors_of(V.check_recipe, r, 'r', need_id=False)
        self.assertTrue(any(e.startswith('r.ingredients[0].unit') for e in errs), errs)

    def test_yakgan_with_qty_fails(self):
        r = recipe('두부구이')
        r['ingredients'][2]['qty'] = 1
        errs = self.errors_of(V.check_recipe, r, 'r', need_id=False)
        self.assertTrue(any(e.startswith('r.ingredients[2].qty') for e in errs), errs)

    def test_missing_qty_fails(self):
        r = recipe('두부구이')
        r['ingredients'][0]['qty'] = None
        self.assertTrue(self.errors_of(V.check_recipe, r, '', need_id=False))
        r['ingredients'][0]['qty'] = 0
        self.assertTrue(self.errors_of(V.check_recipe, r, '', need_id=False))

    def test_lengths_emoji_url_unknown_key(self):
        r = recipe('두부구이')
        r['title'] = '가' * 21
        r['intro'] = '맛있어요 😀'
        r['tip'] = '자세한 내용은 https://example.com 에서'
        r['steps'][0]['time'] = 3
        r['steps'][1]['timer'] = 601
        errs = '\n'.join(self.errors_of(V.check_recipe, r, '', need_id=False))
        for key in ('title', 'intro', 'tip', 'steps[0].time', 'steps[1].timer'):
            self.assertIn(key, errs)

    def test_untrimmed_string_fails(self):
        r = recipe(' 두부구이')
        self.assertTrue(self.errors_of(V.check_recipe, r, '', need_id=False))

    def test_version_must_match(self):
        code, _, err = self.merge(round_obj('두부구이', '감자조림', '시금치나물'), '2026-10-16')
        self.assertEqual(code, 0, err)
        rec = self.read('data/recommend.json')
        ver = self.read('data/version.json')
        ver['recommend'] = '2026-10-15T05:10:00+09:00'
        ver['nextStart'] = '2026-10-20'
        errs = '\n'.join(self.errors_of(V.check_version, ver, rec))
        self.assertIn('recommend', errs)
        self.assertIn('nextStart', errs)


class MergeTest(Base):
    def test_merge_when_not_due_refuses(self):
        self.assertEqual(self.merge(round_obj('두부구이', '감자조림', '시금치나물'), '2026-10-16')[0], 0)
        before = self.snapshot()
        code, _, err = self.merge(round_obj('잡채', '불고기', '미역국'), '2026-10-18')
        self.assertEqual(code, 1)
        self.assertIn('추천 날이 아니에요', err)
        self.assertEqual(self.snapshot(), before)
        # 관리자가 원하면 --force로 새 판
        code, _, err = self.merge(round_obj('잡채', '불고기', '미역국'), '2026-10-18', '--force')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.read('data/version.json')['current'], 'r-261018')

    def test_merge_same_start_needs_force_and_replaces(self):
        self.assertEqual(self.merge(round_obj('두부구이', '감자조림', '시금치나물'), '2026-10-16')[0], 0)
        code, _, err = self.merge(round_obj('잡채', '불고기', '미역국', start='2026-10-16'), '2026-10-19')
        self.assertEqual(code, 1)
        # 같은 판을 고쳐 다시 넣을 때는 같은 제목도 돼요(바뀌는 판의 history는 빼고 봐요)
        code, _, err = self.merge(round_obj('두부구이', '불고기', '미역국', start='2026-10-16'), '2026-10-19',
                                  '--force')
        self.assertEqual(code, 0, err)
        rec = self.read('data/recommend.json')
        self.assertEqual(len(rec['rounds']), 1)
        self.assertEqual([r['title'] for r in rec['rounds'][0]['recipes']], ['두부구이', '불고기', '미역국'])
        hist = self.read('pipeline/history.json')['items']
        self.assertEqual([it['title'] for it in hist], ['두부구이', '불고기', '미역국'])

    def test_merge_appends_prunes_and_updates_version(self):
        import datetime
        day = datetime.date(2026, 1, 1)
        for i in range(12):
            rd = round_obj(f'요리{i}-1', f'요리{i}-2', f'요리{i}-3', title=f'판 {i}')
            code, _, err = self.merge(rd, day.isoformat())
            self.assertEqual(code, 0, err)
            last = day
            day += datetime.timedelta(days=3)
        rec = self.read('data/recommend.json')
        ver = self.read('data/version.json')
        self.assertEqual(len(rec['rounds']), 10)
        self.assertEqual(rec['rounds'][0]['title'], '판 2')
        self.assertEqual(rec['rounds'][-1]['id'], 'r-' + last.strftime('%y%m%d'))
        self.assertEqual(rec['rounds'][-1]['recipes'][2]['id'], 'rec-' + last.strftime('%y%m%d') + '-3')
        self.assertEqual(rec['updatedAt'], f'{last.isoformat()}T05:10:00+09:00')
        self.assertEqual(ver, {
            'recommend': rec['updatedAt'], 'checkedAt': rec['updatedAt'], 'current': rec['rounds'][-1]['id'],
            'nextStart': (last + datetime.timedelta(days=3)).isoformat(), 'intervalDays': 3})
        self.assertEqual(len(self.read('pipeline/history.json')['items']), 36)

    def test_history_repeat_refused(self):
        self.assertEqual(self.merge(round_obj('두부구이', '감자조림', '시금치나물'), '2026-10-16')[0], 0)
        before = self.snapshot()
        code, _, err = self.merge(round_obj('두부 구이', '불고기', '미역국'), '2026-10-19')
        self.assertEqual(code, 1)
        self.assertIn('두부 구이', err)
        self.assertEqual(self.snapshot(), before)

    def test_history_older_than_120_days_allowed(self):
        self.write('pipeline/history.json', {'items': [
            {'start': '2026-06-17', 'id': 'rec-260617-1', 'title': '두부구이'},
            {'start': '2026-06-18', 'id': 'rec-260618-1', 'title': '감자조림'}]})
        code, _, err = self.merge(round_obj('두부구이', '불고기', '미역국'), '2026-10-16')  # 121일 뒤
        self.assertEqual(code, 0, err)
        code, _, err = self.merge(round_obj('감자조림', '잡채', '미역줄기볶음'), '2026-10-19')  # 123일 뒤
        self.assertEqual(code, 0, err)
        code, _, err = self.merge(round_obj('감자 조림', '장조림', '어묵볶음'), '2026-10-22')  # 3일 전 추천
        self.assertEqual(code, 1)

    def test_requests_consumed(self):
        self.write('pipeline/requests.json', {'note': rnd.REQUESTS_NOTE, 'items': [
            {'title': '들기름 막국수', 'memo': '여름에 시원하게'}, {'title': '단호박죽'}]})
        code, out, err = self.merge(round_obj('들기름막국수', '감자조림', '시금치나물'), '2026-10-16')
        self.assertEqual(code, 0, err)
        self.assertIn('들기름 막국수', out)
        self.assertEqual(self.read('pipeline/requests.json')['items'], [{'title': '단호박죽'}])

    def test_invalid_round_writes_nothing(self):
        rd = round_obj('두부구이', '감자조림', '시금치나물')
        rd['recipes'][1]['ingredients'][0]['unit'] = '스푼'
        code, out, err = self.merge(rd, '2026-10-16')
        self.assertEqual(code, 1)
        self.assertIn('recipes[1].ingredients[0].unit', out)
        self.assertEqual(self.snapshot(), {})

    def test_merge_needs_three_recipes(self):
        code, _, err = self.merge(round_obj('두부구이', '감자조림'), '2026-10-16')
        self.assertEqual(code, 1)

    def test_status(self):
        self.assertEqual(self.merge(round_obj('두부구이', '감자조림', '시금치나물'), '2026-10-16')[0], 0)
        for day, due in (('2026-10-18', False), ('2026-10-19', True)):
            code, out, _ = self.run_cmd('status', '--today', day)
            st = json.loads(out)
            self.assertEqual(st['due'], due)
            self.assertEqual(st['lastStart'], '2026-10-16')
            self.assertEqual(st['nextStart'], '2026-10-19')
            self.assertEqual(st['recentTitles'], ['두부구이', '감자조림', '시금치나물'])
            self.assertEqual(st['month'], 10)


class AddTest(Base):
    def test_add_to_current_round(self):
        self.assertEqual(self.merge(round_obj('두부구이', '감자조림', '시금치나물'), '2026-10-16')[0], 0)
        f = self.write('work/add.json', [recipe('잡채')])
        code, _, err = self.run_cmd('add', f, '--today', '2026-10-17', '--now', '2026-10-17T20:00:00+09:00')
        self.assertEqual(code, 0, err)
        rec = self.read('data/recommend.json')
        self.assertEqual(rec['rounds'][-1]['recipes'][-1]['id'], 'rec-261016-4')
        self.assertEqual(self.read('data/version.json')['recommend'], '2026-10-17T20:00:00+09:00')
        # 한 판은 4개까지
        f = self.write('work/add2.json', copy.deepcopy([recipe('불고기')]))
        code, _, err = self.run_cmd('add', f, '--today', '2026-10-17', '--now', '2026-10-17T21:00:00+09:00')
        self.assertEqual(code, 1)
        self.assertIn('4개', err)

    def test_add_repeat_refused(self):
        self.assertEqual(self.merge(round_obj('두부구이', '감자조림', '시금치나물'), '2026-10-16')[0], 0)
        f = self.write('work/add.json', recipe('감자 조림'))
        code, _, _ = self.run_cmd('add', f, '--today', '2026-10-17', '--now', '2026-10-17T20:00:00+09:00')
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
