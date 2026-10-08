"""영어 감각 해설 API.

영어 문장을 받으면 감각 사전(이미지, 뉘앙스, 예시)으로 해설하고, 한국어 문장을 받으면 영어다운 문장을 만들어
같은 틀로 해설한다. Gemini API를 서버에서 부르고, 키는 환경 변수 GEMINI_API_KEY로만 읽는다.
"""
import json
import os
import time
from collections import defaultdict
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
# 앞 모델이 붐비거나(503) 한도에 걸리면(429) 다음 모델로 넘어간다.
FALLBACK_MODELS = [m for m in os.environ.get("GEMINI_FALLBACKS", "gemini-flash-latest,gemini-2.5-flash").split(",") if m]
PER_IP_PER_DAY = int(os.environ.get("PER_IP_PER_DAY", "30"))
GLOBAL_PER_DAY = int(os.environ.get("GLOBAL_PER_DAY", "600"))
MAX_CHARS = 300
ALLOWED_ORIGINS = [
    "https://jaeyoungkang.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

SENSES = (Path(__file__).parent / "senses.md").read_text(encoding="utf-8")

RULES = """너는 한국인 영어 학습자를 돕는 해설자다. 영어 화자가 표현에서 곧바로 받는 '감각'을 설명한다.

감각은 세 결로 본다.
- 이미지: 무엇이 어디에 있고, 어느 쪽으로 움직이고, 어떤 경계를 넘고, 어떤 힘이 미치는지.
- 뉘앙스: 말의 무게, 거리, 일상과 격식의 결.
- 예시: 영어 화자의 귀에 자연스러운 예와 걸리는 예.

규칙
1. 설명은 문법 규칙이나 문법 용어가 아니라 감각의 말(이미지, 뉘앙스)로 한다. 품사, 시제 이름, 구문 이름을 늘어놓지 않는다.
2. 아래 감각 사전에 있는 표제어(불변화사, 기본동사, 잇는 말)가 문장에 있으면 반드시 사전의 이미지와 뉘앙스에서 출발해 설명한다. 사전에 없는 낱말은 사전의 결에 맞게 짧게 설명한다.
3. 같은 장면을 세 가지로 견준다: 한국어를 그대로 옮긴 '한국어식 직역', 라틴어 계열의 격식 있는 낱말을 쓴 '라틴어 계열', 영어 화자가 실제로 쓰는 '영어식'. 걸리는 문장도 틀렸다고 하지 말고 어떻게 다르게 들리는지 말한다.
4. 무엇이 주어가 되는지를 본다. 사람이 주어면 가깝고, 시간이나 느낌이나 물건이 주어면 한 발 떨어진다.
5. 뜻이 굳은 덩어리(put up with, give up, get it, be about to)는 덩어리로 익히라고 말한다. 이미지 하나로 억지로 풀지 않는다.
6. 한국어는 '합니다'체로, 짧고 쉬운 문장으로 쓴다. '자리', '때', '입자'라는 말을 쓰지 않고 '장면', '시간'이나 '시점', '불변화사'라고 쓴다.
7. 입력이 영어 학습과 관계없는 요청이거나 해로운 내용이면 note에 그 까닭만 적고 다른 칸은 비운다.

감각 사전
""" + SENSES

ITEM = {
    "type": "OBJECT",
    "properties": {
        "word": {"type": "STRING", "description": "표제어 또는 덩어리(예: get, out, be about to)"},
        "in_sentence": {"type": "STRING", "description": "문장에서 그 표제어가 쓰인 부분"},
        "image": {"type": "STRING", "description": "이 문장에서 보이는 이미지"},
        "nuance": {"type": "STRING", "description": "이 문장에서의 뉘앙스"},
    },
    "required": ["word", "in_sentence", "image", "nuance"],
}
CONTRAST = {
    "type": "OBJECT",
    "properties": {
        "kind": {"type": "STRING", "enum": ["영어식", "한국어식 직역", "라틴어 계열"]},
        "text": {"type": "STRING"},
        "note": {"type": "STRING", "description": "영어 화자에게 어떻게 들리는지"},
    },
    "required": ["kind", "text", "note"],
}
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "english": {"type": "STRING", "description": "해설하는 영어 문장(한국어 입력이면 만든 영어 문장)"},
        "korean": {"type": "STRING", "description": "자연스러운 한국어 뜻"},
        "picture": {"type": "STRING", "description": "문장 전체가 그리는 그림을 두세 문장으로"},
        "headwords": {"type": "ARRAY", "items": ITEM},
        "contrasts": {"type": "ARRAY", "items": CONTRAST, "description": "같은 장면의 세 문장. 영어식, 한국어식 직역, 라틴어 계열 하나씩"},
        "alternatives": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "한국어 입력일 때 다른 상황에 맞는 영어 문장 0~2개와 그 차이 한 줄"},
        "note": {"type": "STRING", "description": "학습 팁 한두 문장. 또는 처리하지 않은 까닭"},
    },
    "required": ["english", "korean", "picture", "headwords", "contrasts", "note"],
}

app = FastAPI(title="english-sense-api", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

_day = time.strftime("%Y-%m-%d")
_per_ip: dict[str, int] = defaultdict(int)
_total = 0


def _client_ip(req: Request) -> str:
    return req.headers.get("cf-connecting-ip") or (req.client.host if req.client else "unknown")


def _take_quota(ip: str) -> None:
    global _day, _total
    today = time.strftime("%Y-%m-%d")
    if today != _day:
        _day, _total = today, 0
        _per_ip.clear()
    if _total >= GLOBAL_PER_DAY:
        raise HTTPException(429, "오늘 쓸 수 있는 횟수를 모두 썼습니다. 내일 다시 써 주십시오.")
    if _per_ip[ip] >= PER_IP_PER_DAY:
        raise HTTPException(429, f"한 사람이 하루에 {PER_IP_PER_DAY}번까지 쓸 수 있습니다. 내일 다시 써 주십시오.")
    _per_ip[ip] += 1
    _total += 1


class Ask(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)


async def _gemini(task: str) -> dict:
    if not GEMINI_API_KEY:
        raise HTTPException(503, "해설 서버가 아직 준비되지 않았습니다.")
    body = {
        "systemInstruction": {"parts": [{"text": RULES}]},
        "contents": [{"role": "user", "parts": [{"text": task}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
        },
    }
    models = [GEMINI_MODEL] + [m for m in FALLBACK_MODELS if m != GEMINI_MODEL]
    r = None
    async with httpx.AsyncClient(timeout=60) as client:
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            r = await client.post(url, json=body, headers={"x-goog-api-key": GEMINI_API_KEY})
            if r.status_code not in (429, 500, 503):
                break
    if r is None or r.status_code != 200:
        raise HTTPException(502, "해설을 만들지 못했습니다. 잠시 뒤 다시 써 주십시오.")
    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception:
        raise HTTPException(502, "해설을 읽지 못했습니다. 다시 써 주십시오.")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "ready": bool(GEMINI_API_KEY), "model": GEMINI_MODEL}


@app.post("/explain")
async def explain(ask: Ask, req: Request) -> dict:
    _take_quota(_client_ip(req))
    task = (
        "다음 영어 문장을 감각 사전으로 해설하라. english 칸에는 이 문장을 그대로 두고(맞춤법이 틀렸으면 고친 문장), "
        "문장이 어색하면 note에 영어 화자가 실제로 쓰는 문장을 알려라.\n\n영어 문장: " + ask.text.strip()
    )
    return await _gemini(task)


@app.post("/translate")
async def translate(ask: Ask, req: Request) -> dict:
    _take_quota(_client_ip(req))
    task = (
        "다음 한국어 문장을 영어 화자가 그 장면에서 실제로 할 말로 옮기고, 그 영어 문장을 감각 사전으로 해설하라. "
        "기본동사와 불변화사를 쓸 수 있으면 우선한다. contrasts에는 이 한국어를 그대로 옮긴 한국어식 직역을 꼭 넣는다.\n\n"
        "한국어 문장: " + ask.text.strip()
    )
    return await _gemini(task)
