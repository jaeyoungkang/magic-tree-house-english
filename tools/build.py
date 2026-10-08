#!/usr/bin/env python3
"""src/의 페이지 조각을 공통 머리·꼬리로 감싸 정적 HTML을 만든다.

페이지 조각은 맨 위에 <!--page {JSON} --> 머리표를 단다. 머리표의 키:
  path        공개 경로("" 는 첫 화면, "have/" 처럼 끝에 / )
  title       <title>과 og:title
  description 검색 결과와 링크 미리보기 설명
  menu        머리 메뉴에서 켤 항목: words, practice, ask
  crumbs      [[이름, 경로 또는 null], ...] 이동 경로(첫 화면은 넣지 않는다)
  og          미리보기 이미지 이름(assets/og/<og>.png). 없으면 default
  type        website 또는 article
  ld          "article" 이면 Article 구조화 데이터를 단다

본문에는 다음 자리표를 쓸 수 있다. 값은 site.json에서 만든다.
  {{cards}}            표제어 카드 묶음
  {{practice:WORD}}    그 표제어를 연습하는 책 장면 링크
  {{pager:WORD}}       앞뒤 표제어
  {{books}}            연습할 책 목록
  {{units:BOOK}}       그 책으로 연습하는 표제어 목록

실행: python3 tools/build.py (저장소 뿌리에서). 결과는 커밋한다. GitHub Pages는 그대로 올린다.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
BASE = SITE["base"]
FONTS = "https://fonts.googleapis.com/css2?family=Hahmlet:wght@500;700;800&family=IBM+Plex+Sans+KR:wght@400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&display=swap"
STATUS = {"ready": "읽기", "next": "다음", None: "준비 중"}
MENU = [("words", "/#words", "표제어"), ("practice", "/practice/", "연습"), ("ask", "/ask/", "해설기")]
# 예전 주소에서 새 주소로 넘긴다
REDIRECTS = {"have.html": "/have/", "get.html": "/get/", "be.html": "/be/", "ask.html": "/ask/"}

e = html.escape


def ready_words():
    return [w for g in SITE["groups"] for w in g["words"] if SITE["words"][w].get("status") == "ready"]


def cards():
    out = []
    for g in SITE["groups"]:
        items = []
        for w in g["words"]:
            info = SITE["words"][w]
            st = info.get("status")
            inner = f'<span class="w en">{w}</span><span class="pic">{e(info["pic"])}</span><span class="st">{STATUS[st]}</span>'
            items.append(f'<a class="vc" href="/{w}/">{inner}</a>' if st == "ready" else f'<div class="vc">{inner}</div>')
        out.append(f'<div class="grp"><p class="gh"><span class="num">{g["n"]}</span> {e(g["title"])}</p><div class="vcs">{"".join(items)}</div></div>')
    return "\n".join(out)


def practice(word):
    links = [
        f'<a class="link-card" href="/practice/{b["slug"]}/{word}/"><span class="t"><i>{e(b["title"])}</i> 장면으로 {word} 연습하기</span>'
        f'<span class="s">{e(b["ko"])} · {e(b["units"][word])}</span></a>'
        for b in SITE["books"] if word in b["units"]
    ]
    return f'<div class="links">{"".join(links)}</div>' if links else '<p class="muted">책 장면 연습은 준비 중입니다.</p>'


def pager(word):
    ws = ready_words()
    i = ws.index(word)
    prev = f'<a class="prev" href="/{ws[i-1]}/"><span class="k">앞 표제어</span><span class="en">{ws[i-1]}</span></a>' if i > 0 else ""
    nxt = f'<a class="next" href="/{ws[i+1]}/"><span class="k">다음 표제어</span><span class="en">{ws[i+1]}</span></a>' if i + 1 < len(ws) else ""
    return f'<nav class="pager" aria-label="앞뒤 표제어">{prev}{nxt}</nav>'


def books():
    return '<div class="links">' + "".join(
        f'<a class="link-card" href="/practice/{b["slug"]}/"><span class="t"><i>{e(b["title"])}</i></span>'
        f'<span class="s">{e(b["series"])} · {e(b["ko"])} · {e(b["blurb"])}</span>'
        f'<span class="s">연습할 표제어: {", ".join(b["units"])}</span></a>'
        for b in SITE["books"]) + "</div>"


def units(slug):
    b = next(b for b in SITE["books"] if b["slug"] == slug)
    return '<div class="links">' + "".join(
        f'<a class="link-card" href="/practice/{slug}/{w}/"><span class="t"><span class="en">{w}</span> 연습</span>'
        f'<span class="s">{e(SITE["words"][w]["pic"])} · {e(n)}</span></a>'
        for w, n in b["units"].items()) + "</div>"


FILL = {"cards": lambda _: cards(), "practice": practice, "pager": pager, "books": lambda _: books(), "units": units}


def fill(body):
    return re.sub(r"\{\{(\w+)(?::([\w-]+))?\}\}", lambda m: FILL[m.group(1)](m.group(2)), body)


def jsonld(meta, url):
    items = []
    if meta["path"] == "":
        items.append({"@context": "https://schema.org", "@type": "WebSite", "name": SITE["name"], "url": BASE + "/",
                      "description": meta["description"], "inLanguage": "ko"})
    else:
        trail = [[SITE["name"], "/"]] + meta.get("crumbs", [])
        items.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, **({"item": BASE + p} if p else {})}
            for i, (n, p) in enumerate(trail)]})
    if meta.get("ld") == "article":
        items.append({"@context": "https://schema.org", "@type": "Article", "headline": meta["h1"] if "h1" in meta else meta["title"],
                      "description": meta["description"], "inLanguage": "ko", "url": url,
                      "image": f'{BASE}/assets/og/{meta.get("og", "default")}.png',
                      "isPartOf": {"@type": "WebSite", "name": SITE["name"], "url": BASE + "/"}})
    return "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in items)


def page(meta, body):
    url = BASE + "/" + meta["path"]
    og = f'{BASE}/assets/og/{meta.get("og", "default")}.png'
    here = ' aria-current="page"'
    menu = "".join(f'<a href="{href}"{here if meta.get("menu") == key else ""}>{label}</a>' for key, href, label in MENU)
    crumbs = ""
    if meta.get("crumbs"):
        trail = [[SITE["name"], "/"]] + meta["crumbs"]
        lis = "".join(f'<li><a href="{p}">{e(n)}</a></li>' if p else f'<li aria-current="page">{e(n)}</li>' for n, p in trail)
        crumbs = f'<ol class="crumbs" aria-label="이동 경로">{lis}</ol>\n'
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(meta["title"])}</title>
<meta name="description" content="{e(meta["description"])}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="{meta.get("type", "article")}">
<meta property="og:site_name" content="{e(SITE["name"])}">
<meta property="og:title" content="{e(meta["title"])}">
<meta property="og:description" content="{e(meta["description"])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="ko_KR">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/icon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="/assets/site.css">
{jsonld(meta, url)}
</head>
<body>
<header class="top"><div class="top-in"><a class="brand" href="/"><span class="brand-mark" aria-hidden="true"></span>{e(SITE["name"])}</a><nav class="menu" aria-label="사이트">{menu}</nav></div></header>
<main class="wrap">
{crumbs}{fill(body).strip()}
</main>
<footer class="foot">
<p>감각을 이미지, 뉘앙스, 예시 셋으로 보는 틀은 공간 인지 언어학(Tyler &amp; Evans, Talmy)과 한국인 학습자 연구를 바탕으로 정리한 학습 가설입니다.</p>
<p><a href="/">{e(SITE["name"])}</a> · {e(SITE["tagline"])}</p>
</footer>
</body>
</html>
"""


def redirect(to):
    url = BASE + to
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>옮겼습니다</title>
<link rel="canonical" href="{url}"><meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url={to}"><script>location.replace("{to}" + location.hash)</script></head>
<body><p><a href="{to}">새 주소로 옮겼습니다.</a></p></body></html>
"""


def main():
    pages = []
    for src in sorted((ROOT / "src").rglob("*.html")):
        text = src.read_text(encoding="utf-8")
        m = re.match(r"\s*<!--page\s*(\{.*?\})\s*-->\s*", text, re.S)
        if not m:
            raise SystemExit(f"머리표가 없다: {src}")
        meta = json.loads(m.group(1))
        out = ROOT / meta["path"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(meta, text[m.end():]), encoding="utf-8")
        pages.append(meta["path"])
        print("만듦", out.relative_to(ROOT))
    for old, to in REDIRECTS.items():
        (ROOT / old).write_text(redirect(to), encoding="utf-8")
    urls = "\n".join(f"  <url><loc>{BASE}/{p}</loc></url>" for p in sorted(pages, key=lambda p: (p.count("/"), p)))
    (ROOT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n', encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    (ROOT / "CNAME").write_text(BASE.split("://", 1)[1] + "\n", encoding="utf-8")
    print(f"페이지 {len(pages)}개, 옛 주소 {len(REDIRECTS)}개, sitemap.xml, robots.txt, CNAME")


if __name__ == "__main__":
    main()
