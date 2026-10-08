"""영어 감각 해설 API.

영어 문장을 받으면 감각 사전(이미지, 뉘앙스, 예시)으로 해설하고, 한국어 문장을 받으면 영어다운 문장을 만들어
같은 틀로 해설한다. Claude API(Anthropic SDK)를 서버에서 부르고, 키는 환경 변수 ANTHROPIC_API_KEY로만 읽는다.
"""
import json
import os
import time
from collections import defaultdict
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
EFFORT = os.environ.get("ANTHROPIC_EFFORT", "low")
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
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "word": {"type": "string", "description": "표제어 또는 덩어리(예: get, out, be about to)"},
        "in_sentence": {"type": "string", "description": "문장에서 그 표제어가 쓰인 부분"},
        "image": {"type": "string", "description": "이 문장에서 보이는 이미지"},
        "nuance": {"type": "string", "description": "이 문장에서의 뉘앙스"},
    },
    "required": ["word", "in_sentence", "image", "nuance"],
}
CONTRAST = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "kind": {"type": "string", "enum": ["영어식", "한국어식 직역", "라틴어 계열"]},
        "text": {"type": "string"},
        "note": {"type": "string", "description": "영어 화자에게 어떻게 들리는지"},
    },
    "required": ["kind", "text", "note"],
}
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "english": {"type": "string", "description": "해설하는 영어 문장(한국어 입력이면 만든 영어 문장)"},
        "korean": {"type": "string", "description": "자연스러운 한국어 뜻"},
        "picture": {"type": "string", "description": "문장 전체가 그리는 그림을 두세 문장으로"},
        "headwords": {"type": "array", "items": ITEM},
        "contrasts": {"type": "array", "items": CONTRAST, "description": "같은 장면의 세 문장. 영어식, 한국어식 직역, 라틴어 계열 하나씩"},
        "alternatives": {"type": "array", "items": {"type": "string"}, "description": "한국어 입력일 때 다른 상황에 맞는 영어 문장 0~2개와 그 차이 한 줄"},
        "note": {"type": "string", "description": "학습 팁 한두 문장. 또는 처리하지 않은 까닭"},
    },
    "required": ["english", "korean", "picture", "headwords", "contrasts", "alternatives", "note"],
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


client = anthropic.AsyncAnthropic(max_retries=2, timeout=60.0) if os.environ.get("ANTHROPIC_API_KEY") else None


async def _ask_claude(task: str) -> dict:
    if client is None:
        raise HTTPException(503, "해설 서버가 아직 준비되지 않았습니다.")
    try:
        response = await client.beta.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=16000,
            # 감각 사전이 든 지시문은 매번 같으므로 캐시한다.
            system=[{"type": "text", "text": RULES, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": task}],
            output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
            # 안전 분류기가 거절하면 서버가 거절 범주에 맞는 다른 모델로 다시 시도한다.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError:
        raise HTTPException(503, "지금 해설 요청이 많습니다. 잠시 뒤 다시 써 주십시오.")
    except (anthropic.APIStatusError, anthropic.APIConnectionError):
        raise HTTPException(502, "해설을 만들지 못했습니다. 잠시 뒤 다시 써 주십시오.")
    if response.stop_reason == "refusal":
        return {"english": "", "korean": "", "picture": "", "headwords": [], "contrasts": [], "alternatives": [],
                "note": "이 문장은 해설하지 않았습니다. 다른 문장으로 써 주십시오."}
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(502, "해설을 읽지 못했습니다. 다시 써 주십시오.")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "ready": client is not None, "model": ANTHROPIC_MODEL}


@app.post("/explain")
async def explain(ask: Ask, req: Request) -> dict:
    _take_quota(_client_ip(req))
    task = (
        "다음 영어 문장을 감각 사전으로 해설하라. english 칸에는 이 문장을 그대로 두고(맞춤법이 틀렸으면 고친 문장), "
        "문장이 어색하면 note에 영어 화자가 실제로 쓰는 문장을 알려라.\n\n영어 문장: " + ask.text.strip()
    )
    return await _ask_claude(task)


@app.post("/translate")
async def translate(ask: Ask, req: Request) -> dict:
    _take_quota(_client_ip(req))
    task = (
        "다음 한국어 문장을 영어 화자가 그 장면에서 실제로 할 말로 옮기고, 그 영어 문장을 감각 사전으로 해설하라. "
        "기본동사와 불변화사를 쓸 수 있으면 우선한다. contrasts에는 이 한국어를 그대로 옮긴 한국어식 직역을 꼭 넣는다.\n\n"
        "한국어 문장: " + ask.text.strip()
    )
    return await _ask_claude(task)
