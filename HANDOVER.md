# ISAKKE handover (from the Admin session, 15 Oct 2026)

**Rules from Max:** budget first: free/local only, no paid APIs ("crafty, not blingy"). Commits without Claude trailers. Max says yes before anything goes public or gets sent.

## State
- Works end to end: `fetch` → `index` (610 paragraphs, bge-m3, 38 s) → `ask`/`serve` (port 8095). Splitter self-test passes. Search finds the right paragraphs, also for English questions (LAS 11 § for notice, ATL 8 § overtime, SemL 4 § holidays, SjLL sick pay).
- Ollama is now the repo package `ollama-cuda` 0.40.4 (paru keeps it current). `ollama serve` runs as the user (models in `~/.ollama`); start it with `ollama serve &` if it's not running. Models here: bge-m3, gemma4:e4b, qwen3.5:4b (the losers of the comparison are removed).
- GPU: RTX 3060 Laptop, 6 GB VRAM, 14 GB RAM.

## Next
1. Done: default chat model is gemma4:e4b (`isakke.py`, `compose.yml`; fallback qwen3.5:4b). Prompt is English with the answer-language rule last; the question is translated to Swedish before embedding (English queries ranked LAS 11 § 12th, now top). Karensavdrag retrieves SjLL 6 §.
2. Done: sick pay. A terminology line (sjuklön = employer-paid sick pay, not sjukpenning) and "start with a direct one-sentence answer" in the prompt; the employer is named in 6 of 6 runs (Swedish and English), `bench.py gemma4:e4b` is 3/3 correct at 1.3–1.8 s.
3. Screenshot is in `docs/screenshot.png` and the README. Done: public repo https://github.com/maxfinnsjo/isakke (local branch `development` tracks `origin/main`; push with `git push origin development:main`).
4. Optional, researched (see Findings): SCB pay comparison; decider-model routing.
5. Hosting a live demo costs a GPU; for now the demo = repo + screenshots + a short screencast.

## Findings (15 Oct, research)
**SCB pay data: feasible, no key, CC0.** PxWebApi v1 works: `https://api.scb.se/OV0104/v1/doris/sv/ssd/AM/AM0110/AM0110A/LonYrkeRegion4AN` (average monthly pay 2023–2025 by region, sector, SSYK 2012 occupation (432 codes) and sex; also base pay, headcount, women's pay as % of men's). POST a JSON query with `"response":{"format":"csv"}`; output is latin-1. Example: 2221 Grundutbildade sjuksköterskor 2025 = 44 000 kr (men 45 200, women 43 900). v2 (`statistikdatabasen.scb.se/api/v2`, 30 calls per 10 s) exists too. Plan: a "pay" intent that maps the profession in the question to an SSYK code (embed the 432 titles with bge-m3, like the laws), fetches live, and answers with the figure, the gender gap and the source. It needs its own code path, since the laws prompt says "use ONLY the sources".

**Decider models.** Ollama 0.35+ has `POST /v1/systemone` (state + typed questions: `choice`, `noul` yes/no probability, `score`). Models: `nimble`/`nimble-v3` (9B, too big for 6 GB), `tev1` (4B, 2.5 GB), `tev1:0.8b` (833 MB, installed along with tev1). `strands-decider` needs MLX (Apple only) and fails here; `d1` and `clef-flash` are hosted-only, not in Ollama.
- Routing works: tev1:0.8b picks LAS/SemL/ATL/SjLL/AML/MBL/none in about 60 ms warm, right on 5 of 5 labour questions. It also detects the pay intent ("Vad tjänar en sjuksköterska?" → pay 0.82). Off-topic detection is weak ("Hur lagar jag pasta?" → ATL 0.51), so use a threshold or a separate "is this about work?" question.
- Citation check does NOT work: 0.8B scores right and wrong answers 0.19/0.20; tev1 4B scored a wrong "four months" 0.43 above the right "three months" 0.40. Don't build it.
- Routing gain is unproven: retrieval is already good with the translate step. Test by restricting search to the routed law and re-running `bench.py`.

## Ideas to keep ISAKKE on the bleeding edge
- Re-run the comparison when new small models land (Ollama "newest", EuroEval Swedish leaderboard in a browser).
