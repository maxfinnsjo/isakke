#!/usr/bin/env python3
"""ISAKKE: a workers' champion that answers from Swedish labour law, with sources.

  python3 isakke.py fetch    download the laws from Riksdagen's open data into laws/
  python3 isakke.py index    split them by paragraph (§) and embed them -> index.npz
  python3 isakke.py serve    web chat on $PORT (default 8095); builds the index first if missing
  python3 isakke.py ask "..."  one question in the terminal
  python3 isakke.py test     self-check of the paragraph splitter

Needs Ollama ($OLLAMA, default http://localhost:11434) with an embedding model and a chat model.
"""
import json, os, re, sys, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
LAWS_DIR, INDEX = HERE / "laws", Path(os.environ.get("INDEX", HERE / "index.npz"))
OLLAMA = os.environ.get("OLLAMA", "http://localhost:11434")
EMBED = os.environ.get("EMBED_MODEL", "bge-m3")
CHAT = os.environ.get("CHAT_MODEL", "gemma3:4b")
TOP_K = 6

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
    np.savez(INDEX, vecs=embed([t for _, t in chunks]), labels=[l for l, _ in chunks], texts=[t for _, t in chunks])


PROMPT = """Du är ISAKKE, en arbetarkämpe. Du hjälper arbetstagare i Sverige att förstå sina rättigheter.
Svara på samma språk som frågan. Använd BARA källorna nedan. Hänvisa till dem med [1], [2] osv.
Om källorna inte räcker: säg det rakt ut och föreslå facket, ett skyddsombud eller en jurist.
Kom ihåg att kollektivavtal ofta ger mer än lagen. Var tydlig och varm, korta stycken. Du ger inte juridisk rådgivning.

Källor:
{sources}

Fråga: {question}"""


def ask(question, idx):
    q = embed([question])[0]
    top = np.argsort(idx["vecs"] @ q)[::-1][:TOP_K]
    hits = [{"label": str(idx["labels"][i]), "text": str(idx["texts"][i])} for i in top]
    sources = "\n\n".join(f"[{n + 1}] {h['label']}: {h['text']}" for n, h in enumerate(hits))
    r = post("/api/chat", {"model": CHAT, "stream": False, "think": False, "options": {"temperature": 0.2},
                           "messages": [{"role": "user", "content": PROMPT.format(sources=sources, question=question)}]})
    return {"answer": r["message"]["content"], "sources": hits}


class H(BaseHTTPRequestHandler):
    idx = None

    def send(self, code, body, ctype="application/json"):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/":
            return self.send(200, (HERE / "index.html").read_text(), "text/html; charset=utf-8")
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
        try:
            self.send(200, json.dumps(ask(q, H.idx), ensure_ascii=False))
        except OSError as e:  # Ollama down or slow
            self.send(503, json.dumps({"error": f"model unavailable: {e}"}))


def load():
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
        ThreadingHTTPServer(("", port), H).serve_forever()
