#!/usr/bin/env python3
"""링크 미리보기 이미지(assets/og/<이름>.png, 1200x630)를 Chrome 헤드리스로 그린다.

실행: python3 tools/og.py (저장소 뿌리에서, macOS의 Chrome이 있어야 한다).
새 표제어나 새 책을 더하면 CARDS에 한 줄을 더하고 다시 돌린다.
"""
import html
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# 이름: (위 작은 글, 큰 글, 아래 설명, 큰 글이 영어인가)
CARDS = {
    "default": ("영어 감각", "뜻을 외우지 말고, 그림으로 잡는 영어 감각", "have · get · be · go · come · put · take · give …", False),
    "have": ("영어 감각 · 기본동사", "have", "내 영역 안에 놓여 있다", True),
    "get": ("영어 감각 · 기본동사", "get", "경계를 넘어 들어선다", True),
    "be": ("영어 감각 · 기본동사", "be", "이미 거기 놓여 있다", True),
    "ask": ("영어 감각", "영어 문장 감각 해설기", "영어 문장을 넣으면 그림으로 풀어 드립니다", False),
    "titanic": ("영어 감각 · 책 장면 연습", "Tonight on the Titanic", "매직트리하우스 17권 장면으로 연습하는 have, get, be", True),
}
FONTS = "https://fonts.googleapis.com/css2?family=Hahmlet:wght@700;800&family=IBM+Plex+Sans+KR:wght@500;600&family=Newsreader:opsz,wght@6..72,500&display=block"


def card(top, big, sub, en):
    e = html.escape
    big_font = "'Newsreader', Georgia, serif" if en else "'Hahmlet', serif"
    size = 150 if en and len(big) < 8 else 80 if en else 62
    return f"""<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}"><style>
body {{ margin:0; width:1200px; height:630px; background:#F3F5F7; font-family:'IBM Plex Sans KR',sans-serif; color:#16212C; overflow:hidden; position:relative; word-break:keep-all; }}
.zone {{ position:absolute; right:-120px; top:50%; transform:translateY(-50%); width:560px; height:560px; border-radius:50%; background:rgba(11,107,112,.10); border:5px dashed #0B6B70; }}
.dot {{ position:absolute; right:110px; top:50%; transform:translateY(-50%); width:110px; height:110px; border-radius:50%; background:#0B6B70; }}
.in {{ position:absolute; left:84px; top:0; bottom:0; width:660px; display:flex; flex-direction:column; justify-content:center; gap:22px; }}
.top {{ font-weight:600; font-size:30px; color:#0B6B70; letter-spacing:.04em; }}
.big {{ font-family:{big_font}; font-weight:{500 if en else 800}; font-size:{size}px; line-height:1.15; }}
.sub {{ font-size:32px; color:#56636F; font-weight:500; line-height:1.4; }}
</style></head><body><div class="zone"></div><div class="dot"></div>
<div class="in"><div class="top">{e(top)}</div><div class="big">{e(big)}</div><div class="sub">{e(sub)}</div></div></body></html>"""


def main():
    out = ROOT / "assets" / "og"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, args in CARDS.items():
            src = Path(tmp) / f"{name}.html"
            src.write_text(card(*args), encoding="utf-8")
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1200,630",
                            "--virtual-time-budget=8000", f"--screenshot={out / (name + '.png')}", src.as_uri()],
                           check=True, capture_output=True)
            print("그림", f"assets/og/{name}.png")


if __name__ == "__main__":
    main()
