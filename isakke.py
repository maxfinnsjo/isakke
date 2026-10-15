#!/usr/bin/env python3
"""ISAKKE: a workers' champion that answers from Swedish labour law, with sources.

  python3 isakke.py fetch    download the laws from Riksdagen's open data (and SCB's occupation list) into laws/
  python3 isakke.py index    split them by paragraph (§) and embed them -> index.npz
  python3 isakke.py serve    web chat on $HOST:$PORT (default 127.0.0.1:8095); builds the index first if missing
  python3 isakke.py ask "..."  one question in the terminal
  python3 isakke.py test     self-check of the paragraph splitter

Needs Ollama ($OLLAMA, default http://localhost:11434) with an embedding model and a chat model.
"""
import csv, io, json, os, re, sys, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
LAWS_DIR, INDEX = HERE / "laws", Path(os.environ.get("INDEX", HERE / "index.npz"))
OLLAMA = os.environ.get("OLLAMA", "http://localhost:11434")
EMBED = os.environ.get("EMBED_MODEL", "bge-m3")
CHAT = os.environ.get("CHAT_MODEL", "gemma4:e4b")  # "" = no generated answer: show the closest paragraphs (the slim profile, runs on any CPU)
TOP_K = 6
RATE = int(os.environ.get("RATE_LIMIT", 0))  # questions per minute per client IP for a public demo, 0 = off (SCB itself allows 30 calls per 10 s)
MIN_SCORE = float(os.environ.get("MIN_SCORE", 0.30))  # best paragraph similarity below this = off-topic; the slim profile uses 0.48
DECIDER = os.environ.get("DECIDER_MODEL", "isakke-decider")  # Ollama decision model (see decider.Modelfile); "" turns the off-topic check off
SCB = "https://api.scb.se/OV0104/v1/doris/sv/ssd/AM/AM0110/AM0110A/LonYrkeRegion4AN"  # monthly pay by occupation (SSYK 2012), CC0

# Short name -> SFS number. The laws a worker in Sweden runs into most.
LAWS = {
    "LAS": "1982:80",     # employment protection: notice, dismissal, fixed-term jobs, priority rules
    "MBL": "1976:580",    # codetermination: unions, negotiation, collective agreements, strikes
    "ATL": "1982:673",    # working hours, overtime, rest
    "SemL": "1977:480",   # holidays and holiday pay
    "AML": "1977:1160",   # work environment, safety representatives
    "DL": "2008:567",     # discrimination
    "SjLL": "1991:1047",  # sick pay
    "FörälL": "1995:584", # parental leave
    "FML": "1974:358",    # union representatives at the workplace
    "VbL": "2021:890",    # whistleblowers
}


def post(path, body):
    req = urllib.request.Request(OLLAMA + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def fetch():
    LAWS_DIR.mkdir(exist_ok=True)
    for short, sfs in LAWS.items():
        url = f"https://data.riksdagen.se/dokument/sfs-{sfs.replace(':', '-')}.text"
        text = urllib.request.urlopen(url, timeout=60).read().decode("utf-8")
        (LAWS_DIR / f"{short}.txt").write_text(text)
        print(f"{short:7} {sfs:10} {text.splitlines()[0]}")
    meta = json.load(urllib.request.urlopen(SCB, timeout=60))
    occ = next(v for v in meta["variables"] if v["code"] == "Yrke2012")
    pairs = [(c, t) for c, t in zip(occ["values"], occ["valueTexts"]) if c != "0000"]
    (LAWS_DIR / "ssyk.json").write_text(json.dumps(pairs, ensure_ascii=False))
    print(f"SCB     {len(pairs)} occupations")


PARA = re.compile(r"^(\d+ [a-z]? ?§)\s", re.M)
CHAPTER = re.compile(r"^(\d+ kap\.)\s+[A-ZÅÄÖ][^§\n]*$", re.M)  # a heading line, not "37 kap. 3 § socialförsäkringsbalken"


def split(short, text):
    """[(label, text)] per paragraph, e.g. ("LAS 7 §", "...") or ("AML 3 kap. 2 §", "..."). Wrapped lines are joined."""
    title = text.splitlines()[0].strip()
    body = text.split("\n\n", 1)[1] if "Källa:" not in text else text.split("Källa:", 1)[1].split("\n", 1)[1]
    body = re.split(r"^Övergångsbestämmelser", body, flags=re.M | re.I)[0]  # transitional rules reuse § numbers
    out, chapter = [], ""
    marks = sorted([(m.start(), "p", m.group(1)) for m in PARA.finditer(body)] +
                   [(m.start(), "c", m.group(1)) for m in CHAPTER.finditer(body)])
    for n, (pos, kind, name) in enumerate(marks):
        if kind == "c":
            chapter = name + " "
            continue
        end = marks[n + 1][0] if n + 1 < len(marks) else len(body)
        chunk = re.sub(r"\s*\n\s*", " ", body[pos:end]).strip()
        out.append((f"{short} {chapter}{name.replace('  ', ' ')}", f"{title}, {chapter}{chunk}"))
    return out


def embed(texts):
    vecs = []
    for i in range(0, len(texts), 32):
        vecs += post("/api/embed", {"model": EMBED, "input": texts[i:i + 32]})["embeddings"]
    v = np.array(vecs, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def index():
    chunks = [c for f in sorted(LAWS_DIR.glob("*.txt")) for c in split(f.stem, f.read_text())]
    print(f"{len(chunks)} paragraphs, embedding with {EMBED}…")
    occ = json.loads((LAWS_DIR / "ssyk.json").read_text())
    np.savez(INDEX, vecs=embed([t for _, t in chunks]), labels=[l for l, _ in chunks], texts=[t for _, t in chunks],
             occ_vecs=embed([t for _, t in occ]), occ_codes=[c for c, _ in occ], occ_titles=[t for _, t in occ])


PROMPT = """You are ISAKKE, a workers' champion who helps employees in Sweden understand their rights.
Use ONLY the sources below and cite them as [1], [2] etc. Start with a direct one-sentence answer to the question. State plainly who must do what (e.g. "your employer pays"), using the law's own terms.
Terms: sjuklön = sick pay, paid by the employer for the first 14 days (the sick pay period); sjukpenning = sickness benefit from Försäkringskassan, a different thing; karensavdrag = the unpaid qualifying-day deduction.
If the sources are not enough, say so and suggest the union, a safety representative or a lawyer.
If the sources are about a different occupation than the one asked, say so instead of answering for the wrong one.
Collective agreements often give more than the law. Be short, factual and warm: 2-5 short sentences, no drama. This is not legal advice.

Sources:
{sources}

Question: {question}

Answer in the language of the question above (Swedish question: Swedish answer; English question: English answer)."""


PAY_OR_TRANSLATE = ("Only if the text asks what people in a named profession earn on average, reply exactly "
                    "`LÖN: <the profession in Swedish, singular>`, e.g. \"What does a nurse earn?\" -> `LÖN: sjuksköterska`. "
                    "Questions about the asker's own pay, sick pay, raises or who pays are NOT such questions. "
                    "In every other case reply with only the Swedish translation of the text (unchanged if already Swedish).\n\n")


def pay_hits(profession, idx):
    """Occupations closest to the profession, the biggest (most employees) first, with latest average monthly pay from SCB (live)."""
    stem = profession.lower()[:-2]  # embeddings alone put "sjuksköterska" next to "barnsköterskor"
    ranked = np.argsort(idx["occ_vecs"] @ embed([profession])[0])[::-1]
    same = [i for i in ranked if stem in str(idx["occ_titles"][i]).lower()]
    codes = [str(idx["occ_codes"][i]) for i in (same or ranked[:3])[:20]]
    sel = lambda code, vals: {"code": code, "selection": {"filter": "item", "values": vals}}
    body = {"query": [sel("Region", ["SE"]), sel("Sektor", ["0"]), sel("Yrke2012", codes), sel("Kon", ["1+2", "1", "2"]),
                      sel("ContentsCode", ["000007AS", "000007AP"]), {"code": "Tid", "selection": {"filter": "top", "values": ["1"]}}],
            "response": {"format": "csv"}}
    req = urllib.request.Request(SCB, json.dumps(body).encode(), {"Content-Type": "application/json"})
    rows = list(csv.reader(io.StringIO(urllib.request.urlopen(req, timeout=30).read().decode("latin-1"))))
    year = rows[0][-1].split()[-1]
    occs = {}
    for _, _, occ, sex, pay, n in rows[1:]:
        if pay.isdigit():
            occs.setdefault(occ, {})[sex] = (int(pay), int(n) if n.isdigit() else 0)
    best = sorted(occs.items(), key=lambda kv: -kv[1].get("totalt", (0, 0))[1])[:3]
    return [{"label": f"SCB {occ.split(' ', 1)[1]}",
             "text": f"SCB lönestrukturstatistik {year}, {occ}, genomsnittlig månadslön, alla sektorer, hela Sverige: "
                     + ", ".join(f"{k} {p} kr" for k, (p, _) in sex.items()) + f"; {sex.get('totalt', (0, 0))[1]} anställda."}
            for occ, sex in best]


OFF_TOPIC = ("Det där ligger utanför vad jag kan hjälpa till med: svensk arbetsrätt och löner.\n"
             "That is outside what I can help with: Swedish employment law and pay.")


# Without a chat model nothing translates the question: bge-m3 ranks English worse (LAS 11 § was 12th), so add the Swedish terms.
GLOSS = {"notice": "uppsägningstid", "vacation": "semester", "holiday": "semester", "overtime": "övertid", "sick": "sjuk sjuklön", "probation": "provanställning",
         "union": "fack facklig", "fired": "uppsägning avskedande", "dismiss": "uppsägning avskedande", "parental": "föräldraledighet", "discriminat": "diskriminering",
         "whistleblow": "visselblåsare", "safety": "arbetsmiljö skyddsombud", "bully": "mobbning kränkande särbehandling", "break": "rast", "rest": "vila",
         "working hours": "arbetstid", "fixed-term": "visstidsanställning", "temporary": "visstidsanställning", "strike": "strejk", "pregnan": "graviditet föräldraledighet",
         "salary": "lön", "wage": "lön", "contract": "anställningsavtal", "layoff": "uppsägning arbetsbrist", "redundan": "uppsägning arbetsbrist"}
# "Vad tjänar en sjuksköterska?" / "What does a nurse earn?" -> the profession (group 1 or 2)
PAY_Q = re.compile(r"\btjänar\s+(?:en |ett |man som |någon som är )?([^?.,!]+)|\b(?:what|how much)\s+(?:does|do|will)\s+(?:an?|the)?\s*([a-z\- ]+?)\s+(?:earn|make)\b", re.I)


def gloss(q):
    extra = [v for k, v in GLOSS.items() if k in q.lower()]
    return q + (" (" + " ".join(extra) + ")" if extra else "")


def on_topic(question, best):
    """Cascade: the best retrieval score settles the clear cases for free; only the in-between band goes to the decision model."""
    if best >= 0.55 or not DECIDER and best >= MIN_SCORE:  # without a decider only the clearly off-topic are refused
        return True
    if best < MIN_SCORE:
        return False
    try:
        a = post("/v1/systemone", {"model": DECIDER, "state": {"question": question}, "questions": {
            "work": {"type": "noul", "instructions": "Is this a question about rights, pay or conditions at work?"}}})
        return a["answers"]["work"]["noul"] >= 0.5
    except OSError:  # decider not installed or Ollama too old: let the question through
        return True


def ask(question, idx):
    if CHAT:
        # the laws are Swedish and bge-m3 ranks English queries worse (LAS 11 § was 12th for the notice question)
        sv = post("/api/chat", {"model": CHAT, "stream": False, "think": False, "options": {"temperature": 0},
                                "messages": [{"role": "user", "content": PAY_OR_TRANSLATE + question}]})["message"]["content"].strip()
        profession, query = (sv[4:].strip(), question) if sv.startswith("LÖN:") else (None, sv or question)
    else:
        m = PAY_Q.search(question)
        profession, query = (m.group(1) or m.group(2)).strip() if m else None, gloss(question)
    if profession:
        hits = pay_hits(profession, idx)
        if not hits:
            return {"answer": "Inga lönedata hittades. / No pay data found.", "sources": []}
    else:
        sims = idx["vecs"] @ embed([query])[0]
        if not on_topic(question, sims.max()):
            return {"answer": OFF_TOPIC, "sources": []}
        top = np.argsort(sims)[::-1][:TOP_K]
        hits = [{"label": str(idx["labels"][i]), "text": str(idx["texts"][i])} for i in top]
    if not CHAT:
        top3 = "\n\n".join(f"[{n + 1}] {h['label']}: {h['text'][:350]}{'…' if len(h['text']) > 350 else ''}" for n, h in enumerate(hits[:3]))
        return {"answer": "Närmaste träffar (ingen AI-genererad text) / Closest matches (no AI-generated text):\n\n" + top3, "sources": hits}
    sources = "\n\n".join(f"[{n + 1}] {h['label']}: {h['text']}" for n, h in enumerate(hits))
    r = post("/api/chat", {"model": CHAT, "stream": False, "think": False, "options": {"temperature": 0.2},
                           "messages": [{"role": "user", "content": PROMPT.format(sources=sources, question=question)}]})
    return {"answer": r["message"]["content"], "sources": hits}


recent = {}  # client -> times of its requests in the last minute


def limited(client):
    now = time.time()
    if len(recent) > 10000:
        recent.clear()
    times = recent[client] = [t for t in recent.get(client, []) if now - t < 60] + [now]
    return bool(RATE) and len(times) > RATE


def log(**kw):
    """One JSON line per event on stdout: `docker compose logs` is the demo's access log."""
    print(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), **kw}, ensure_ascii=False), flush=True)


class H(BaseHTTPRequestHandler):
    idx = None

    def log_message(self, *args):  # the default stderr line has the proxy's IP and no question; log() replaces it
        pass

    def client(self):
        return self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or self.client_address[0]  # behind Caddy

    def send(self, code, body, ctype="application/json"):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/":
            log(event="page", client=self.client(), ua=self.headers.get("User-Agent", "")[:80])
            return self.send(200, (HERE / "index.html").read_text(), "text/html; charset=utf-8")
        if self.path == "/api/mode":
            return self.send(200, json.dumps({"chat": bool(CHAT)}))
        self.send(404, '{"error":"not found"}')

    def do_POST(self):
        if self.path != "/api/ask":
            return self.send(404, '{"error":"not found"}')
        try:
            q = str(json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 4096)))["question"]).strip()[:1000]
        except (ValueError, KeyError, TypeError):
            return self.send(400, '{"error":"send {\\"question\\": \\"...\\"}"}')
        if not q:
            return self.send(400, '{"error":"empty question"}')
        if limited(self.client()):
            log(event="rate_limited", client=self.client(), q=q[:200])
            return self.send(429, '{"error":"för många frågor, vänta en minut / too many questions, wait a minute"}')
        t = time.time()
        try:
            r = ask(q, H.idx)
            labels = [h["label"] for h in r["sources"]]
            log(event="ask", client=self.client(), q=q[:200], kind="refused" if not labels else "pay" if labels[0].startswith("SCB") else "law",
                top=labels[:3], ms=round(1000 * (time.time() - t)))
            self.send(200, json.dumps(r, ensure_ascii=False))
        except OSError as e:  # Ollama or SCB down or slow
            log(event="error", client=self.client(), q=q[:200], error=str(e)[:200], ms=round(1000 * (time.time() - t)))
            self.send(503, json.dumps({"error": f"backend unavailable (Ollama or SCB): {e}"}))


def load():
    idx = dict(np.load(INDEX))
    if "occ_vecs" in idx:
        return idx
    index()  # index.npz from before the SCB pay feature
    return dict(np.load(INDEX))


def test():
    sample = "Lag (1977:1160) om arbetsmiljö\n\nSFS nr: 1977:1160\nKälla: Regeringskansliet / Lagrummet\n\n\n" \
             "1 kap. Lagens ändamål\n\n1 § Lagens ändamål är att\nförebygga ohälsa.\n\n2 a § Mer\ntext.\n\n" \
             "2 kap. Arbetsmiljöns beskaffenhet\n\n1 § Arbetsmiljön ska vara tillfredsställande."
    got = split("AML", sample)
    assert [l for l, _ in got] == ["AML 1 kap. 1 §", "AML 1 kap. 2 a §", "AML 2 kap. 1 §"], got
    assert got[0][1] == "Lag (1977:1160) om arbetsmiljö, 1 kap. 1 § Lagens ändamål är att förebygga ohälsa.", got[0][1]
    las = split("LAS", "Lag (1982:80) om anställningsskydd\n\nKälla: X\n\n\n7 § Uppsägning ska vara\nsakligt grundad.\n\n"
                       "8 § Tid enligt\n37 kap. 3 § socialförsäkringsbalken.\n\nÖvergångsbestämmelser\n\n22 § i den äldre lydelsen.")
    assert [l for l, _ in las] == ["LAS 7 §", "LAS 8 §"] and las[0][1].endswith("sakligt grundad."), las
    global RATE
    RATE = 2
    assert [limited("a"), limited("a"), limited("a"), limited("b")] == [False, False, True, False]
    RATE = 0
    print("ok")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "fetch":
        fetch()
    elif cmd == "index":
        index()
    elif cmd == "test":
        test()
    elif cmd == "ask":
        r = ask(" ".join(sys.argv[2:]), load())
        print(r["answer"], "\n\nKällor:", ", ".join(h["label"] for h in r["sources"]))
    else:
        if not INDEX.exists():
            index()
        H.idx = load()
        port = int(os.environ.get("PORT", 8095))
        print(f"ISAKKE on http://localhost:{port}")
        ThreadingHTTPServer((os.environ.get("HOST", "127.0.0.1"), port), H).serve_forever()
