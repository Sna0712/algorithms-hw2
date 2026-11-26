# 구현 계획: URL 단축기와 해시 테이블

## 목표와 제약

- `SPEC.md`를 기능과 동작의 기준으로 삼는다. 이 계획은 요구사항을 구체적인 작업 순서와 파일 구조로 나누며, 명세의 기본값·오류·이론식·산출물 경로를 변경하지 않는다.
- Python 표준 라이브러리만 사용한다. 해시 테이블 자료구조는 버킷 배열과 체인/슬롯을 직접 관리하며 `dict`, `set`, 내장 `hash()`에 의존하지 않는다.
- `Makefile`의 기존 인터페이스를 유지한다: `make test`, `make serve PORT=8000`, `make experiment` (`experiments/probe_experiment.py` 실행).
- 각 기능은 테스트를 먼저 작성하고, 실패를 확인한 뒤 최소 구현과 리팩터링을 진행하는 TDD 방식으로 만든다.
- 현재 `src/base62.py`와 `tests/test_base62.py`는 이미 존재한다. 작업 첫 단계에서 이 테스트를 기준선으로 확인하고, 그 이후 기능은 각각 테스트를 먼저 추가한다.

## 파일 및 디렉터리 구조

```text
.
├── README.md                         # 과제 소개 및 실행 안내 (기존, 이 계획에서 수정하지 않음)
├── SPEC.md                           # 기능·오류·실험의 요구사항 원본 (기존, 기준 문서)
├── PLAN.md                           # 단계별 구현 계획
├── REPORT.md                         # 최종 구현·실험 결과 보고서 (통합 단계에서 작성)
├── Makefile                          # test/serve/experiment 명령 (기존 인터페이스 유지)
├── .github/
│   └── copilot-instructions.md       # 프로젝트 구현·테스트 규칙
├── src/
│   ├── base62.py                     # Base62 변환 (기존 구현)
│   ├── hash_table.py                 # Horner 해시와 separate chaining 테이블
│   ├── linear_probing.py             # 최종 과제: linear probing 테이블
│   ├── shortener.py                  # URL 검증, 단축 및 복원
│   ├── server.py                     # 표준 라이브러리 HTTP 서버와 API
│   └── templates/
│       └── index.html                # 브라우저 입력 폼 및 결과/시각화 UI
├── tests/
│   ├── test_base62.py                # Base62 테스트 (기존 테스트)
│   ├── test_hash_table.py            # Horner 해시 및 separate chaining 테스트
│   ├── test_shortener.py             # URL 단축/복원 테스트
│   ├── test_server.py                # HTTP API 및 브라우저 UI 테스트
│   ├── test_linear_probing.py        # Linear probing 테스트
│   └── test_experiment.py            # 통계, CSV, SVG 테스트
├── experiments/
│   ├── probe_experiment.py           # 두 충돌 처리 방식의 실험 실행기 (Makefile 진입점)
│   ├── results.csv                   # make experiment가 생성하는 측정/이론값
│   └── results.svg                   # make experiment가 생성하는 그래프
└── tools/
    └── catchup.sh                    # 수업 따라잡기 스크립트 (기존, 이 계획에서 수정하지 않음)
```

`results.csv`와 `results.svg`는 실험 실행 시 생성되는 결과물이며 소스 파일이 아니다. 기존의 설정 파일과 컨테이너 파일은 이 작업 범위에서 변경하지 않는다.

## 모듈별 설계

### Base62 — `src/base62.py`

기존 API와 동작을 유지한다.

- `encode_base62(number: int) -> str`: 0 이상의 정수를 지정된 `0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ` 알파벳으로 인코딩한다. 0은 `"0"`이다. `bool`을 포함한 정수가 아닌 입력은 `TypeError`, 음수는 `ValueError`.
- `decode_base62(code: str) -> int`: Base62 문자열을 정수로 디코딩한다. 문자열이 아닌 입력은 `TypeError`, 빈 문자열과 허용 알파벳 밖의 문자는 `ValueError`.
- 문자 숫자값은 기존처럼 알파벳의 `index()`로 찾는다. 새 의존성이나 `dict` 기반 문자표는 추가하지 않는다.

### Horner 해시 및 separate chaining — `src/hash_table.py`

- `HashStep` 데이터 클래스: 해시 계산의 한 단계에 대해 `character`, `codepoint`, `previous_hash`, `current_hash`를 보관한다.
- `LookupTrace` 데이터 클래스: `steps`, `bucket_index`, `bucket_entries`, `found`, `value`, `comparisons`를 보관해 조회 과정과 충돌을 화면에 전달한다.
- `HashTable(initial_capacity: int = 8, max_load: float | None = 0.75)`: 용량 크기의 버킷 리스트를 초기화한다. 각 버킷은 `(key, value)` 항목의 체인이다. 핵심 저장소와 인덱스는 리스트로 관리한다.
- `hash_trace(key: str, capacity: int | None = None) -> tuple[int, list[HashStep]]`: 초기 해시값을 0으로 두고 왼쪽부터 문자별로 `h = (h * 31 + ord(character)) % capacity`를 계산한다. 각 문자와 `ord` 값, 모듈로 적용 후 해시를 기록하고 최종 버킷 인덱스와 단계를 반환한다.
- `hash_index(key: str) -> int`: 현재 용량에 대한 최종 버킷 인덱스를 반환한다. `hash_trace`와 같은 Horner 계산을 사용한다.
- `put(key: str, value: object) -> None`: 해당 버킷 체인에서 같은 키를 찾으면 값을 교체하고 항목 수를 유지한다. 새 키면 체인에 추가한다. 삽입 후 적재율이 `max_load`를 초과하면 용량을 두 배로 늘려 모든 항목을 재해싱한다. `max_load=None`이면 자동 확장을 하지 않는다.
- `get(key: str) -> object | None`: 체인을 순회해 값을 반환하고, 없는 키는 `None`을 반환한다.
- `get_with_comparisons(key: str) -> tuple[object | None, int]`: `get`과 같은 결과와 실제 저장 키 동등성 비교 횟수를 반환한다. 체인이 비어 있으면 비교 횟수는 0이다.
- `inspect_lookup(key: str) -> LookupTrace`: 해시 단계, 선택 버킷의 체인, 비교 결과 및 비교 횟수를 묶어 반환한다. 브라우저 충돌 시각화에 사용한다.
- `__len__() -> int`, `load_factor() -> float`, `bucket_items(index: int) -> list[tuple[str, object]]`: 항목 수, 적재율, 해당 버킷의 항목을 조회한다. 체인 외부 변경을 허용하지 않도록 실제 내부 리스트 대신 복사본을 반환한다.
- 확장 시에는 새 용량으로 각 키의 Horner 해시를 다시 계산한다. 기존 키의 업데이트는 확장이나 항목 수 증가를 유발하지 않도록 한다.

### URL 단축 및 복원 — `src/shortener.py`

- `validate_url(url: str) -> str`: `urllib.parse.urlsplit`로 입력을 검사한다. 비어 있지 않은 문자열이며 절대 URL이고 scheme이 `http` 또는 `https`이며 hostname을 가져야 한다. 정규화·공백 제거를 하지 않고 잘못된 입력은 `ValueError`로 처리한다.
- `URLShortener`: URL→코드와 코드→URL 인덱스로 두 개의 `HashTable` 인스턴스를 사용하고, 새 ID를 1부터 발급한다.
- `shorten(url: str) -> str`: URL을 검증하고 이미 저장된 URL이면 기존 코드를 돌려준다. 새 URL이면 다음 ID를 `encode_base62`로 인코딩하고 양방향 인덱스에 저장한다.
- `shorten_with_status(url: str) -> tuple[str, bool]`: HTTP 응답에 필요한 생성 여부까지 반환한다. 두 번째 값은 새 URL이면 `True`, 기존 URL이면 `False`다. `shorten`과 같은 검증과 저장 경로를 공유한다.
- `expand(code: str) -> str`: 저장된 원래 URL을 반환하고, 미등록 코드는 `KeyError`로 처리한다.
- `inspect_url_lookup(url: str) -> LookupTrace`: URL 인덱스에 대한 조회 과정을 반환해 서버의 해시 시각화 경로에서 사용한다.

### HTTP 서버와 브라우저 — `src/server.py`, `src/templates/index.html`

- `run_server(port: int) -> None`: 표준 라이브러리 `http.server`로 서버를 실행하고 하나의 `URLShortener` 인스턴스를 요청 간 공유한다. CLI에서 `--port`를 받아 Makefile의 기존 `PORT` 인자와 연결한다.
- `BaseHTTPRequestHandler` 하위 클래스의 `do_GET()`은 `/`에 브라우저 페이지를 제공하고 `/<code>`를 302 리다이렉트한다. 알 수 없는 코드는 404다.
- `do_POST()`의 `/shorten`은 JSON의 문자열 `url` 필드를 검증하고 단축한다. 새 URL은 201, 중복 URL은 200이며 응답 JSON에 `code`와 `short_url`을 포함한다. 잘못된 JSON·필드·URL은 400이다.
- `/visualize`는 JSON 문자열 `key`를 받아 URL 인덱스의 `LookupTrace`를 JSON으로 반환한다. 응답은 문자별 해시 단계, 버킷 인덱스, 버킷 체인, 키 비교 결과와 횟수를 포함한다.
- `index.html`은 URL 제출 폼과 해시 시각화 입력 폼을 제공한다. 표준 브라우저 JavaScript의 `fetch`로 기존 `/shorten` API와 `/visualize`를 호출하고 같은 페이지에 결과를 표시한다. 동적 텍스트는 HTML로 실행하지 않고 텍스트로 삽입한다.
- `tests/test_server.py`는 임시 포트의 로컬 서버에 표준 라이브러리 `urllib.request`로 요청을 보내 API 상태·헤더·JSON과 HTML 페이지를 확인한다. 브라우저 직접 확인도 완료 조건에 포함한다.

### 적재율 실험 및 출력 — `experiments/probe_experiment.py`

- Makefile이 이미 이 파일을 실행하므로 `make experiment`의 진입점과 명령은 유지한다.
- 재현 가능한 키 목록을 만들고, 적재율별 항목 수를 `n = round(alpha * capacity)`로 정한다. 각 실행은 고정 용량 및 `max_load=None`으로 테이블을 구성해 확장을 막고, 실제 적재율 `n / capacity`를 기록한다. 성공 조회는 저장한 키, 실패 조회는 저장되지 않은 고정 키를 사용한다.
- separate chaining은 `get_with_comparisons`로 키 비교 횟수를 측정한다. 각 적재율에 대해 성공/실패 조회를 각각 수행하고 평균 비교 횟수를 계산한다.
- 이론값은 SPEC.md의 식 그대로 사용한다. `alpha = n / m`에 대해 separate chaining 실패는 `alpha`, 성공은 `1 + (n - 1) / (2m)`이다. Linear probing 실패는 `1/2 × (1 + 1/(1-alpha)^2)`, 성공은 `1/2 × (1 + 1/(1-alpha))`의 근사값으로 기록한다. 식의 가정과 실측치 차이는 결과 해석에서 분명히 한다.
- `LinearProbingHashTable`에도 같은 키와 조회 집합을 사용한다. Linear probing의 관측 단위는 키 등가 비교가 아니라 확인한 슬롯 수이며, 실패 탐색을 끝내는 빈 슬롯도 포함한다. CSV의 `measurement_unit` 필드로 chaining의 `key_comparisons`와 probing의 `slot_probes`를 구분한다.
- CSV는 표준 `csv` 모듈로 `experiments/results.csv`에 쓴다. 열에는 방식, 용량, 키 수, 적재율, 탐색 종류, 탐색 수, 관측 단위, 실제 평균 횟수, 이론 평균 횟수를 포함한다.
- SVG는 표준 라이브러리만으로 `experiments/results.svg`에 생성한다. 적재율을 x축, 평균 횟수를 y축으로 하고 방식·성공/실패·실측/이론선을 구별해 표시한다. XML 문자를 이스케이프하고, CSV와 SVG의 데이터가 동일한 실험 결과에서 나오도록 한다.
- 실험 계산과 파일 쓰기는 테스트 가능한 함수로 분리한다. 예: `collect_results(capacity, target_loads)`, `write_csv(results, path)`, `write_svg(results, path)`, `main()`. 결과 행은 `ExperimentResult` 데이터 클래스로 표현한다.

### Linear probing — `src/linear_probing.py`

- `LinearProbingHashTable(initial_capacity: int = 8, max_load: float | None = 0.75)`: separate chaining과 같은 Horner 해시, 초기 용량, 적재율 확장 정책과 `max_load=None` 동작을 사용하되, 충돌 시 다음 인덱스를 순서대로 확인하는 슬롯 배열을 구현한다.
- `put(key: str, value: object) -> None`: 시작 버킷에서 선형으로 빈 슬롯 또는 같은 키를 찾는다. 같은 키 업데이트는 항목 수를 유지한다. 자동 확장 시 모든 키를 새 슬롯 배열에 재삽입한다. 고정 용량 실험은 `alpha < 1` 범위로 수행하며, 가득 찬 테이블에서는 무한 순회를 하지 않고 명시적인 오류를 반환한다.
- `get(key: str) -> object | None`, `get_with_probes(key: str) -> tuple[object | None, int]`: 값/미스와 함께 확인한 슬롯 수를 제공한다. 실패 시 탐색 종료에 사용한 빈 슬롯을 슬롯 확인 횟수에 포함한다.
- 성공 탐색·실패 탐색의 슬롯 확인 횟수는 chaining의 키 비교 횟수와 서로 다른 측정 단위임을 CSV, 그래프 범례, 결과 설명에 표시한다.

## TDD 작업 순서, 의존성 및 완료 조건

| 단계 | 선행 조건 | 테스트 우선 작업 | 구현 작업 및 완료 조건 | 검증 방법 |
| --- | --- | --- | --- | --- |
| 1. 기존 Base62 테스트 확인 | 없음 | 기존 `tests/test_base62.py`를 변경 없이 읽고 기준선 테스트로 사용한다. | `src/base62.py`의 API·오류 동작과 SPEC.md가 일치하는지 확인한다. 이 단계에서는 Base62 구현을 다시 작성하지 않는다. | `python3 -m unittest discover -s tests -p 'test_base62.py' -v` 실행. |
| 2. Horner 해시 및 separate chaining 테스트와 구현 | 1 | `tests/test_hash_table.py`에 Horner 단계·버킷 인덱스, 빈 테이블, 충돌 키, 갱신, 확장·재해싱, `max_load=None`, 성공/실패 비교 횟수 테스트를 먼저 추가한다. | `src/hash_table.py`의 `HashTable`, `HashStep`, `LookupTrace`를 구현한다. 핵심 자료구조는 리스트 기반이며 `dict`, `set`, `hash()` 없이 동작해야 한다. | 테스트를 먼저 실행해 실패를 확인하고, 구현 후 `python3 -m unittest discover -s tests -p 'test_hash_table.py' -v` 및 `make test` 통과. |
| 3. URL 단축기 테스트와 구현 | 2 | `tests/test_shortener.py`에서 HTTP/HTTPS 유효성, ID 및 코드 발급, 중복 URL, 복원, 미등록 코드, 잘못된 URL·타입 테스트를 먼저 작성한다. | `src/shortener.py`의 `validate_url`, `URLShortener`, `shorten`, `shorten_with_status`, `expand`를 구현한다. 저장과 조회는 단계 2의 해시 테이블 및 Base62를 사용한다. | 실패 테스트를 확인한 뒤 `python3 -m unittest discover -s tests -p 'test_shortener.py' -v`; 이어 `make test`. |
| 4. `.github/copilot-instructions.md` 규칙 파일 작성 | 3 | 별도 기능 테스트는 없다. 규칙 파일에 적을 범위를 기존 SPEC, PLAN, 테스트 실행 방식과 대조한다. | `.github/copilot-instructions.md`를 작성해 명세 우선, 표준 라이브러리만 사용, 직접 구현 자료구조 제약, TDD 순서, 검증 명령 및 범위 외 파일 변경 방지 규칙을 기록한다. SPEC.md의 요구사항을 재정의하지 않는다. | 파일이 저장소 규칙으로 적용될 경로에 있는지와 지시가 SPEC/PLAN과 모순되지 않는지 확인하고 `git diff --check` 실행. |
| 5. Separate chaining 적재율 실험 및 CSV/SVG 생성 | 2, 4 | `tests/test_experiment.py`에서 재현 가능한 키, 적재율별 항목 수와 실제 적재율, 성공/실패 비교 횟수, chaining 이론값, CSV 행·헤더, SVG 구조를 먼저 테스트한다. | `experiments/probe_experiment.py`의 첫 구현은 separate chaining만 대상으로 한다. 용량 고정 및 `max_load=None`을 사용하고, SPEC.md의 chaining 이론식과 대조해 `experiments/results.csv` 및 `experiments/results.svg`를 생성한다. | 테스트를 먼저 실패 확인 후 구현하고, 실험 테스트 및 `make experiment`를 실행한다. CSV의 성공/실패 행과 이론값, SVG의 축·범례·계열을 확인한다. |
| 6. 웹 서버 및 충돌 시각화 구현 | 3, 5 | `tests/test_server.py`에 루트 페이지, URL 폼 결과, 201/200, 400, 302/Location, 404, 시각화 데이터의 해시 단계·버킷·체인·비교 횟수 테스트를 먼저 작성한다. | `src/server.py`와 `src/templates/index.html`을 구현한다. 기존 JSON API를 유지하며 브라우저에서 단축 결과를 확인하고, 입력한 키의 Horner 계산 과정과 separate chaining 충돌 처리를 시각적으로 볼 수 있어야 한다. | 로컬 임시 포트 기반 서버 테스트를 실행하고, `make serve`로 브라우저에서 단축 폼 및 시각화를 직접 확인한다. |
| 7. Linear probing 테스트 및 구현 | 2, 4 | `tests/test_linear_probing.py`에 충돌 후 삽입·검색, 갱신, 재해싱, `max_load=None`, 성공/실패 탐색 및 빈 슬롯을 포함한 슬롯 확인 횟수, 가득 찬 테이블 처리를 먼저 테스트한다. | `src/linear_probing.py`의 `LinearProbingHashTable`, `get_with_probes`를 구현한다. 같은 Horner 해시를 사용하며 슬롯 배열과 다음 인덱스 탐색으로 충돌을 처리한다. | 테스트 우선으로 실패를 확인한 뒤 `python3 -m unittest discover -s tests -p 'test_linear_probing.py' -v`; 이어 `make test`. |
| 8. 두 충돌 처리 방식의 성능 비교 및 linear probing 시각화 | 5, 7 | 실험 테스트를 확장해 같은 키셋·용량·적재율·조회 집합을 두 방식에 적용하는지, 비교 단위·이론값·CSV/SVG 계열이 구분되는지 검증한다. | `experiments/probe_experiment.py`를 확장해 chaining의 키 비교 횟수와 probing의 슬롯 확인 횟수를 나란히 측정한다. SPEC.md의 linear probing 근사 이론식을 포함하고, SVG에서 두 충돌 처리 방식의 성공/실패 실측·이론선을 구별해 시각화한다. | 실험 테스트와 `make experiment`를 실행한다. CSV의 `measurement_unit` 구분, 두 방식의 같은 입력 조건, SVG 레이블·계열 및 α 범위를 확인한다. |
| 9. 전체 통합 검증 및 보고서 작성 | 1–8 | 전체 `tests/test_*.py`를 실행한다. 발견된 실패는 해당 단계의 테스트와 구현으로 돌아가 수정한다. | 모든 기능이 기존 Makefile 명령 및 SPEC.md와 일치하는지 확인한다. `REPORT.md`에 구현 범위, 설계 요약, 테스트 명령과 결과, 실험 설정·CSV/SVG 경로, 실험값과 이론값의 비교 및 측정 단위 차이를 기록한다. | `make test`, `make experiment`, `make serve`, 브라우저 수동 확인 및 `git diff --check`를 완료한다. 생성된 CSV/SVG와 보고서 수치를 서로 대조한다. |

`make test`는 기존 `unittest discover -s tests -v` 타깃으로 신규 테스트 파일을 자동 검색한다. 각 구현 단계에서는 테스트 작성 → 실패 확인 → 최소 구현 → 해당 테스트 통과 → 전체 테스트 순으로 진행한다. 단계 5는 separate chaining 단독 실험을 먼저 완성하고, 단계 8에서 linear probing 비교와 시각화를 추가한다. 서버 테스트는 외부 네트워크나 제3자 서비스에 의존하지 않는다.
