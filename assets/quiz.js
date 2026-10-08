// 책 장면 문제: 고르기(choose)와 쓰기(produce). 페이지는 initQuiz({ questions, book, done })만 부른다.
function initQuiz({ questions: Q, book, done }) {
  const KIND = { en: ["영어식", "en-k"], ko: ["한국어식 직역", "ko-k"], la: ["라틴어 계열", "la-k"] };
  const nChoose = Q.filter(q => q.type === "choose").length;
  let cur = 0, correct = 0;
  const card = document.getElementById("quiz-card");
  const prog = document.getElementById("progress");
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function render() {
    prog.textContent = cur < Q.length ? `${cur + 1} / ${Q.length}` : "끝";
    if (cur >= Q.length) {
      card.innerHTML = `<div class="done"><span class="eyebrow">고르기 결과</span><span class="score">${correct} / ${nChoose}</span><p>${esc(done)}</p><div class="actions" style="justify-content:center"><button class="btn ghost" type="button" id="again">처음부터 다시</button></div></div>`;
      document.getElementById("again").addEventListener("click", () => { cur = 0; correct = 0; render(); });
      return;
    }
    const q = Q[cur];
    const meta = `<p class="meta">${esc(book)} ${q.ch}장 · 말하는 사람: ${esc(q.who)}</p><p>${esc(q.scene)}</p><p class="ask">${esc(q.ask)}</p>`;
    if (q.type === "choose") {
      card.innerHTML = meta + `<div class="opts">${q.opts.map((o, i) => `<button type="button" class="opt" data-i="${i}"><span class="en">${esc(o.t)}</span></button>`).join("")}</div><div class="feedback" hidden id="fb"></div>`;
      card.querySelectorAll(".opt").forEach(b => b.addEventListener("click", () => choose(+b.dataset.i)));
    } else {
      card.innerHTML = meta + `<label class="hint" for="ans-${cur}">영어로 쓰고 답을 확인하십시오. 막히면 빈칸으로 두고 눌러도 됩니다.</label><textarea id="ans-${cur}" spellcheck="false"></textarea><div class="actions"><button class="btn" type="button" id="reveal">모범 답 보기</button></div><div class="feedback" hidden id="fb"></div>`;
      document.getElementById("reveal").addEventListener("click", reveal);
    }
  }
  function next() {
    cur++; render();
    document.getElementById("quiz").scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  function choose(i) {
    const q = Q[cur], ok = q.opts[i].k === "en";
    if (ok) correct++;
    card.querySelectorAll(".opt").forEach((b, j) => {
      const o = q.opts[j];
      b.disabled = true;
      if (o.k === "en") b.classList.add("right"); else if (j === i) b.classList.add("wrong");
      b.insertAdjacentHTML("beforeend", `<span><span class="tag ${KIND[o.k][1]}">${KIND[o.k][0]}</span></span><span class="why">${esc(o.why)}</span>`);
    });
    const fb = document.getElementById("fb");
    fb.innerHTML = `<p class="verdict ${ok ? "ok" : "no"}">${ok ? "맞습니다." : "영어 화자라면 초록색 문장을 고릅니다."}</p><p class="feel">${esc(q.feel)}</p><div class="actions"><button class="btn" type="button" id="next">다음 문제</button></div>`;
    fb.hidden = false;
    document.getElementById("next").addEventListener("click", next);
  }
  function reveal() {
    const q = Q[cur];
    document.getElementById("reveal").disabled = true;
    const src = q.book === null ? `<p class="note">책 장면에 맞게 지은 문장입니다.</p>`
      : q.book !== q.answer ? `<p class="note">책 문장: <span class="en">${esc(q.book)}</span></p>`
      : `<p class="note">책 문장 그대로입니다.</p>`;
    const fb = document.getElementById("fb");
    fb.innerHTML = `<p class="verdict ok">모범 답</p><p class="en" style="font-size:1.25rem">${esc(q.answer)}</p>${src}<p class="hint">처음 푼 학습자가 고친 곳</p><ul class="fixes">${q.fixes.map(f => `<li><span class="en">${esc(f[0])}</span><span class="muted">${esc(f[1])}</span></li>`).join("")}</ul><div class="actions"><button class="btn" type="button" id="next">${cur === Q.length - 1 ? "결과 보기" : "다음 문제"}</button></div>`;
    fb.hidden = false;
    document.getElementById("next").addEventListener("click", next);
  }
  render();
}
