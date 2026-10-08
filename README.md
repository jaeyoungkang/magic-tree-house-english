# 영어 감각

뜻을 외우지 않고 그림으로 잡는 영어 기본동사. 표제어마다 영어 화자에게 보이는 그림을 설명하고, 영어 원서의 장면으로
연습합니다.

https://english.artificialmind.kr/

## 구조

| 경로 | 내용 |
| --- | --- |
| `src/` | 페이지 조각. 여기를 고친다 |
| `site.json` | 표제어, 묶음, 책 목록. 카드와 링크, 메뉴가 여기서 나온다 |
| `assets/site.css`, `assets/quiz.js` | 모든 페이지가 함께 쓰는 스타일과 문제 엔진 |
| `tools/build.py` | `src/`를 감싸 `index.html`, `have/index.html` 같은 정적 페이지와 `sitemap.xml`을 만든다 |
| `tools/og.py` | 링크 미리보기 이미지(`assets/og/`)를 만든다 |
| `api/` | 해설기 API |

## 페이지를 더할 때

- 표제어: `src/<표제어>.html`을 `src/have.html`의 틀로 만들고, `site.json`의 `status`를 `ready`로 바꾼다.
- 책 장면 연습: `src/practice/<책>/<표제어>.html`을 만들고, `site.json`의 그 책 `units`에 한 줄을 더한다. 새 책이면
  `books`에 항목을, `src/practice/<책>/index.html`을 더한다.
- 그다음 `python3 tools/build.py`를 돌리고(미리보기 이미지가 새로 필요하면 `python3 tools/og.py`도), 결과를 함께 커밋한다.
- 미리보기: `python3 -m http.server 8000` 뒤 http://localhost:8000/
