# 레시피 저장소 추천 레시피 절차 (예약 작업 '레시피 추천', 매일 05:10)

목표: 3일마다 제철 레시피 3개로 새 판을 만들어 `data/recommend.json`에 더하고 main에 올린다. 추천 날이 아닌 날(대부분)은 아무것도 바꾸지 않고 끝낸다.
앱은 `https://raw.githubusercontent.com/woos-lee94/recipe-store-data/main/data/version.json`을 자주 받아 보고, `recommend` 값이 바뀌면 `data/recommend.json`을 새로 받는다(올린 뒤 5분 안팎이면 반영).

## 0. 원칙
- 사용자에게 질문하지 않는다. 판단이 갈리면 보수적으로(덜 짜게, 충분히 익게, 확인이 안 되면 다른 요리로) 하고 마지막 보고에 적는다.
- 공개 저장소다. 개인 정보·비밀 키·메모리 내용을 파일에 쓰지 않는다.
- 검증(validate.py)을 통과하지 못하면 올리지 않는다. data 파일은 손으로 고치거나 비우지 않고 `round.py`로만 바꾼다.
- 추천 날이 아니면 커밋·푸시하지 않는다(`round.py checked`도 쓰지 않는다).
- 아래에서 `{REPO}`는 클론한 저장소의 절대 경로다.
- 목표 시간 30분 안팎. 작성 에이전트는 WebSearch 6회 이내, 검토 에이전트는 3회 이내.

## 1. 추천 날인지 보기
```
python3 {REPO}/pipeline/round.py status
```
- `due`가 false면 아무것도 바꾸지 말고 "오늘은 추천 날이 아니에요 (다음 추천: M월 D일)"(nextStart)라고 보고하고 끝낸다.
- true면 today, yymmdd, month, requests, recentTitles, recentRounds를 기억하고 `mkdir -p {REPO}/work` 한다.

## 2. 요리 3개 정하기
1. requests(관리자 요청)를 앞에서부터 먼저 쓴다(최대 3개). memo가 있으면 그 뜻을 따른다. recentTitles와 겹치는 요청은 빼고 7단계 보고에 적는다.
2. 남은 자리는 `{REPO}/pipeline/recipe_spec.md`의 '1. 무엇을 고를까'와 '7. 제철 재료'의 {month}월 줄을 보고 고른다.
3. 순서와 구성: 1번 국·찌개 또는 메인, 2번 반찬·볶음, 3번 면·밥 / 간식 / 양식 / 손님상. 요청 요리도 이 자리에 맞춰 넣는다.
4. 한 판 안에서 주재료가 겹치지 않고, recentRounds와 분류·조리법이 겹치지 않게 한다. recentTitles의 요리(이름만 다른 같은 요리 포함)는 고르지 않는다.
5. 요리마다 한 줄로 정리한다: 요리 이름, tags, 주재료, 왜 지금인지(또는 관리자 memo).

## 3. 조사·작성: 요리마다 에이전트 1개, 3개를 한 메시지에서 동시에 띄운다
각 에이전트(general-purpose)에게 보낼 지시(중괄호를 채운다, N은 1·2·3):
```
너는 '레시피 저장소' 앱의 요리 연구가야. 오늘은 {today}({month}월) 한국 시간이야.
1) {REPO}/pipeline/recipe_spec.md 를 먼저 읽고 그대로 따라.
2) 맡은 요리: {요리 이름} / tags {tags} / 주재료 {주재료} / 메모 {왜 지금인지 또는 관리자 memo}
3) 믿을 만한 자료 2곳 이상에서 분량·불 세기·시간을 교차 확인해(WebSearch 6회 이내, 필요하면 검색 결과의 주소를 WebFetch로 열어 원문 확인).
   문장은 베끼지 말고 네 말로 새로 써.
4) 2인분 레시피 하나를 {REPO}/work/rec_{N}.json 에 저장해(레시피 객체 하나, id는 넣지 마).
5) 검증: python3 {REPO}/pipeline/validate.py {REPO}/work/rec_{N}.json → 오류 0, 경고도 되도록 0.
6) 마지막 답변은 짧게: 제목, 참고한 자료 이름 2~3개, 자신 없는 점(분량·시간 등).
```
- 에이전트가 요리를 쓰지 못했으면(자료 부족·검증 실패) 같은 자리에 맞는 다른 요리로 그 에이전트만 다시 띄운다.

## 4. 검토: 세 에이전트가 모두 끝나면 검토 에이전트 1개
```
너는 '레시피 저장소' 앱의 레시피 검수자야. 오늘은 {today} 한국 시간이야. {REPO}/pipeline/recipe_spec.md 를 먼저 읽어.
{REPO}/work/rec_1.json, rec_2.json, rec_3.json 을 하나씩 보고 그 파일만 고쳐(칸 구조는 그대로).
볼 것: ① 분량이 2인분에 맞는지(물·간장·소금·설탕이 지나치지 않은지) ② 단계에 쓰인 재료가 모두 목록에 있고 목록의 재료가 모두 쓰이는지
③ 단계마다 불 세기와 다 된 표시가 있는지 ④ timer가 기다리는 단계에만 있고 글의 시간과 같은지, minutes가 맞는지
⑤ 고기·닭·해산물이 속까지 익는지, 날달걀·뜨거운 기름·시럽 주의가 있는지 ⑥ 단위 16개·재료 이름 규칙(짧고 일반적, 상표 없음)
⑦ 세 요리의 분류·주재료가 겹치지 않는지 ⑧ 자료 문장을 그대로 옮긴 듯한 문장 ⑨ 맞춤법·띄어쓰기, intro·tip 해요체.
의심스러운 분량·시간은 WebSearch 3회 이내로 확인하고, 확인이 안 되면 더 안전한 쪽으로 고쳐.
끝나면 python3 {REPO}/pipeline/validate.py {REPO}/work/rec_1.json {REPO}/work/rec_2.json {REPO}/work/rec_3.json → 오류 0.
보고는 짧게: 고친 곳을 파일별 한 줄, 여전히 자신 없는 점.
```

## 5. 판 만들고 합치기
1. 판 제목·한마디를 정한다(recipe_spec.md '8. 판 제목과 한마디'). 따옴표(" ')는 쓰지 않는다.
2. `work/round.json`을 만들고 검증한 뒤 합친다.
```
cd {REPO}
python3 -c "import json; r=[json.load(open('work/rec_%d.json' % i, encoding='utf-8')) for i in (1, 2, 3)]; json.dump({'title': '{판 제목}', 'note': '{한마디}', 'recipes': r}, open('work/round.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)"
python3 pipeline/validate.py work/round.json
python3 pipeline/round.py merge work/round.json
```
- merge는 start(오늘)·id를 붙이고 data/recommend.json, data/version.json, pipeline/history.json, pipeline/requests.json(쓴 요청 빼기)을 함께 고친 뒤 전체 검증 결과를 보여 준다. 판은 최근 10개만 남는다.
- 최근 120일 요리와 겹친다고 멈추면 그 요리만 다른 요리로 바꿔 3·4단계를 다시 한다.
- 검증 오류로 멈추면 work 파일을 고쳐 다시 한다(merge는 실패하면 아무 파일도 바꾸지 않는다). 끝내 못 고치면 올리지 않고 보고한다.

## 6. 올리기
```
cd {REPO}
git add data pipeline/history.json pipeline/requests.json
git commit -m "추천 레시피 {today}: {제목1} · {제목2} · {제목3}"
git fetch origin main && git rebase origin/main
git push origin HEAD:main
```
- work/ 폴더는 올리지 않는다(.gitignore).
- rebase가 충돌로 멈추면(다른 작업이 먼저 올라감): `git rebase --abort && git reset --hard origin/main` 뒤 1단계 status부터 다시 본다.
  due가 false가 됐으면(오늘 판이 이미 올라감) 보고하고 끝낸다. true면 work 파일이 그대로 남아 있으니 5단계부터 다시 한다.
- push가 거절되면 fetch·rebase 후 한 번만 다시 한다. 그래도 main에 못 올리면 `claude/recipe-{yymmdd}` 브랜치로 올리고, main에 못 올린 이유를 보고한다.

## 7. 마지막 보고(사용자에게 보이는 짧은 메시지)
- 판 제목, 레시피 3개 제목(tags)
- 관리자 요청에서 쓴 요리, 쓰지 못한 요청과 이유(있을 때만)
- 자신 없는 점 1~3줄
- 커밋 해시

---

## 관리자가 바로 넣고 싶을 때 ("이 요리를 추천에 넣어 줘")
관리자가 그 세션에서 직접 부탁했을 때만 한다. 관리자 세션에서는 꼭 필요하면 물어봐도 된다.
1. `python3 {REPO}/pipeline/round.py status` → recentRounds 마지막 판이 지금 판이다. recentTitles에 있는 요리면 그렇다고 알리고 멈춘다.
2. recipe_spec.md대로 조사·작성해 `{REPO}/work/add.json`에 저장한다(레시피 1~2개 배열, id 없이). 3·4단계처럼 에이전트를 써도 되고 직접 써도 된다.
   검증: `python3 {REPO}/pipeline/validate.py {REPO}/work/add.json` → 오류 0.
3. 지금 판에 더한다(한 판 최대 4개):
```
cd {REPO}
python3 pipeline/round.py add work/add.json
git add data pipeline/history.json pipeline/requests.json
git commit -m "추천 레시피 추가 {today}: {제목}"
git fetch origin main && git rebase origin/main
git push origin HEAD:main
```
- 지금 판이 꽉 찼다고(4개) 멈추면 `pipeline/requests.json`에 넣어 다음 판에서 먼저 쓰게 하고(아래), 관리자에게 그렇게 했다고 알린다. 지금 바로 보여야 한다고 하면 '지금 새 추천 만들기'로 간다.

### 다음 추천에 넣기 ("이 요리를 다음 추천에 넣어 줘")
- `pipeline/requests.json`의 items 끝에 `{"title": "요리 이름", "memo": "관리자가 한 말 요약"}`을 더한다(title 20자, memo 80자 이내, memo는 없어도 된다).
```
cd {REPO}
python3 pipeline/validate.py pipeline/requests.json
git add pipeline/requests.json
git commit -m "추천 요청: {요리 이름}"
git fetch origin main && git rebase origin/main
git push origin HEAD:main
```

## 지금 새 추천 만들기 ("지금 새 추천 만들어 줘")
- 관리자가 그 세션에서 분명히 새 판을 부탁했을 때만 한다. 예약 실행(질문 없이 도는 작업)이나 "예약 작업 지금 실행해 줘"에서는 하지 않는다. 그때는 1단계 status 결과를 그대로 따른다.
- 2~4단계를 그대로 하고, 5단계 merge에 `--force`를 붙인다:
```
cd {REPO}
python3 pipeline/round.py merge work/round.json --force
```
- 오늘 날짜 판이 이미 있으면 `--force`가 그 판을 바꾼다(그 판의 history 항목도 새 레시피로 바뀐다). 오늘 판을 바꾸는 게 맞는지 관리자에게 먼저 확인한다.
- 다음 추천 날은 새 판 start + 3일로 다시 정해진다.
- 6단계처럼 올리되 커밋 메시지는 `추천 레시피 {today}(관리자 요청): {제목1} · {제목2} · {제목3}`.
