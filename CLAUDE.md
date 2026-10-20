# 레시피 저장소 데이터 저장소

아이폰 앱 '레시피 저장소'가 읽는 '추천 레시피' 데이터예요. 앱에는 관리자 기능이 없어요. 앱은 `data/version.json`을 자주 받아 보고, `recommend` 값이 바뀌면 `data/recommend.json`을 raw.githubusercontent.com에서 다시 받아 가요.

- 예약 작업 '레시피 추천'(매일 05:10, 실제 추천은 3일마다): `pipeline/RUNBOOK.md` 순서를 그대로 따라요. 추천 날이 아니면 아무것도 커밋하지 않고 끝내요.
  - 이 저장소가 처음부터 붙은 전용 세션을 매일 깨우는 방식이에요(2026-10-20). 예약 실행 세션 안에서 add_repo로 저장소를 붙이는 방식은 도구가 없어 실패했어요. 다시 만들 때도 저장소가 붙은 세션으로 돌게 해요.
- 레시피 작성 규칙·제철 재료·단위·예시: `pipeline/recipe_spec.md`.
- 도구: `python3 pipeline/round.py status|merge|add|checked`. 판 더하기, 지금 판에 레시피 더하기, version.json·history.json·requests.json 갱신을 한꺼번에 해요. data 파일은 손으로 고치지 말고 round.py로 바꿔요.
- 검증: `python3 pipeline/validate.py` (오류 0이어야 올려요). `validate.py work/rec_1.json`처럼 레시피 하나·판 하나 파일도 검사해요.
- 테스트: `python3 -m unittest discover -s pipeline`. 도구를 고치면 꼭 돌려요.
- 형식을 바꾸지 마세요. 앱이 `data/recommend.json`, `data/version.json`의 칸 이름·단위 16개를 그대로 읽어요. 바꿔야 하면 앱과 함께 바꾸고 `v`를 올려요.
- 관리자 요청: 다음 판에 먼저 쓰기 `pipeline/requests.json`, 지금 판에 바로 넣기 `round.py add`, 새 판 앞당기기 `round.py merge --force`(관리자가 그 세션에서 분명히 부탁했을 때만). RUNBOOK 아래쪽에 있어요.
- `pipeline/history.json`은 지금까지 추천한 모든 레시피예요. 지우지 않아요(120일 안에 같은 요리를 다시 추천하지 않으려고 써요).
- 공개 저장소예요. 개인 정보·비밀 키·메모리 내용을 올리지 마세요. 레시피는 여러 자료를 교차 확인해 우리 말로 새로 써요(문장 베끼기 금지).
- 파이썬 표준 라이브러리만 써요. 시각은 한국 시간(+09:00 고정), `--today`·`--now`로 날짜를 정해 돌려 볼 수 있어요.
- 작업 파일은 `work/`에 둬요(올리지 않아요).
