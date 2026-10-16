# 레시피 저장소 데이터

아이폰 앱 **레시피 저장소**가 받아 가는 '추천 레시피' 파일이에요. 앱 레시피 탭 맨 아래에 3일마다 새로 고른 제철 레시피 3개가 나오고, 마음에 드는 레시피는 내 레시피로 저장할 수 있어요.
앱에는 관리자 기능이 없고, 모든 사람이 같은 파일을 받아요.

| 파일 | 내용 | 바뀌는 때 |
|---|---|---|
| `data/recommend.json` | 추천 레시피 판(최근 10판, 판마다 보통 3개) | 3일마다 새벽 5시 10분쯤, 관리자가 레시피를 더할 때 |
| `data/version.json` | recommend.json이 바뀐 시각, 지금 판, 다음 추천 날 | recommend.json이 바뀔 때마다 |
| `pipeline/history.json` | 지금까지 추천한 모든 레시피(지우지 않아요). 120일 안에 같은 요리를 다시 추천하지 않으려고 써요 | 레시피가 더해질 때 |
| `pipeline/requests.json` | 관리자가 추천받고 싶은 요리 목록 | 관리자가 적을 때, 추천에 쓰이면 빠져요 |

- 앱은 `https://raw.githubusercontent.com/woos-lee94/recipe-store-data/main/data/`에서 파일을 받아요.
- 앱은 작은 `version.json`만 자주 받아 보고, `recommend` 값이 바뀌었을 때만 `recommend.json`을 새로 받아요.
- 요리를 고르고 레시피를 쓰는 일은 개발자 계정의 Claude(AI) 예약 작업 '레시피 추천'이 해요. 매일 새벽 5시 10분에 확인하고, 3일마다 새 판을 올려요. 추천 날이 아니면 아무것도 바꾸지 않아요.
  - 절차: `pipeline/RUNBOOK.md`, 레시피 작성 규칙·제철 재료·단위: `pipeline/recipe_spec.md`
- 레시피는 여러 자료(레시피 사이트, 공공기관 자료, 요리 채널 등)에서 분량·불 세기·시간을 교차 확인한 뒤 우리 말로 새로 써요. 다른 글의 문장을 그대로 옮기지 않아요.
- 앱은 AI를 부르지 않고, 사용자 정보도 이 저장소로 오지 않아요. 이 저장소에는 개인 정보가 없어요.

## 관리자가 요리를 넣고 싶을 때 (개발자만)
- 다음 추천에 넣기: `pipeline/requests.json`의 items에 `{ "title": "들기름 막국수", "memo": "여름에 시원하게" }`처럼 적어요(title만 적어도 돼요). 다음 추천 때 먼저 쓰고, 쓰고 나면 목록에서 빠져요. Claude에게 "이 요리를 다음 추천에 넣어 줘"라고 해도 돼요.
- 지금 판에 바로 넣기: Claude에게 "이 요리를 추천에 넣어 줘"라고 하면 레시피를 써서 지금 판에 더해요(한 판 최대 4개).
- 예약 작업 바로 돌리기: Claude에게 "레시피 추천 예약 작업 지금 실행해 줘"라고 하면 바로 확인해요. 추천 날이면 새 판을 만들고, 아니면 그냥 끝나요.
- 추천 날이 아닌데 새 판이 필요하면 Claude에게 "지금 새 추천 만들어 줘"라고 분명히 말해요. 그때만 새 판을 앞당겨 만들어요.
- 앱에는 이런 단추나 관리자 화면이 없어요. 저장소에는 비밀 키가 필요 없어요.

## 형식 요약
- `recommend.json`: `{ "app": "recipe-store", "v": 1, "updatedAt", "intervalDays": 3, "rounds": [판...] }`
  - 판: `{ "id": "r-YYMMDD", "start": "YYYY-MM-DD", "title", "note", "recipes": [레시피...] }`
  - 레시피: `{ "id": "rec-YYMMDD-n", "title", "intro", "tags", "servings", "minutes", "ingredients", "steps", "tip" }`
  - 재료 `{ "name", "qty", "unit" }`: 단위는 g, kg, ml, L, 큰술, 작은술, 컵, 개, 쪽, 대, 모, 줌, 장, 포기, 꼬집, 약간 중 하나예요. '약간'이면 qty는 null이에요.
  - 단계 `{ "text", "timer" }`: timer는 분이고, 0이면 타이머가 없어요.
- `version.json`: `{ "recommend", "checkedAt", "current", "nextStart", "intervalDays" }`. `recommend`는 recommend.json의 updatedAt과 같아요.
- 시각은 모두 한국 시간(+09:00)이에요.

## 도구 (파이썬 3 표준 라이브러리만)
- `python3 pipeline/round.py status` 오늘이 추천 날인지, 다음 추천 날, 관리자 요청, 최근 120일 요리
- `python3 pipeline/round.py merge work/round.json` 새 판 더하기 / `add work/add.json` 지금 판에 레시피 더하기
- `python3 pipeline/validate.py` 데이터 검증(오류 0이어야 올려요)
- `python3 -m unittest discover -s pipeline` 도구 테스트
