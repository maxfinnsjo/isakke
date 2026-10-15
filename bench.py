# Same 3 questions per model; expected facts: LAS 11 § -> 3 months, SemL 4 § -> 25 days, SjLL -> employer pays sick pay days 1-14.
import sys, time, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import isakke
idx = isakke.load()
QS = ["Hur lång uppsägningstid har jag efter fem års anställning?",
      "Hur många semesterdagar har jag rätt till per år?",
      "Who pays me the first two weeks when I am sick?"]
for m in sys.argv[1:]:
    isakke.CHAT = m
    isakke.ask("hej", idx)  # warm-up load, not timed
    for q in QS:
        t = time.time(); r = isakke.ask(q, idx)
        print(json.dumps({"model": m, "s": round(time.time() - t, 1), "q": q, "a": r["answer"]}, ensure_ascii=False), flush=True)
