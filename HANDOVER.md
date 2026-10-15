# ISAKKE handover (from the Admin session, 15 Oct 2026)

**Rules from Max:** budget first: free/local only, no paid APIs ("crafty, not blingy"). Commits without Claude trailers. Max says yes before anything goes public or gets sent.

## State
- Works end to end: `fetch` → `index` (610 paragraphs, bge-m3, 38 s) → `ask`/`serve` (port 8095). Splitter self-test passes. Search finds the right paragraphs, also for English questions (LAS 11 § for notice, ATL 8 § overtime, SemL 4 § holidays, SjLL sick pay).
- Ollama is now the repo package `ollama-cuda` 0.40.4 (paru keeps it current). `ollama serve` runs as the user (models in `~/.ollama`); start it with `ollama serve &` if it's not running. Models here: bge-m3, gemma4:e4b, qwen3.5:4b (the losers of the comparison are removed).
- GPU: RTX 3060 Laptop, 6 GB VRAM, 14 GB RAM.

## Next
1. Done: default chat model is gemma4:e4b (`isakke.py`, `compose.yml`; fallback qwen3.5:4b). Prompt is English with the answer-language rule last; the question is translated to Swedish before embedding (English queries ranked LAS 11 § 12th, now top). Karensavdrag retrieves SjLL 6 §.
2. Open: the sick-pay answer is still weak. gemma4:e4b says "sickness benefit" and doesn't plainly say the employer pays days 1–14 (SjLL 7 § is retrieved). Try a prompt hint, a bigger TOP_K, or ministral-3:8b if speed is acceptable. Re-run `python3 bench.py gemma4:e4b` to check.
3. Screenshot is in `docs/screenshot.png` and the README. Push to a **new public GitHub repo** (Max says yes first; there are no secrets here, laws are public domain).
4. Optional: a pay comparison (SCB open salary statistics by occupation).
5. Hosting a live demo costs a GPU; for now the demo = repo + screenshots + a short screencast.

## Ideas to keep ISAKKE on the bleeding edge
- **Decider models** (new on Ollama, Oct 2026: Liquid AI `d1` 3B, Together `tev1` 0.8B/4B, Strands `strands-decider` 2B, Bespoke `nimble`/`nimble-v3` 9B, Cloudflare `clef-flash` 9B). They turn a state + typed questions into fast decisions, not chat. Possible uses: route a question to the right law(s) before search (narrower, better retrieval); decide "answerable from the sources?" vs "ask your union / a lawyer"; tag the topic (notice, pay, hours, safety, discrimination) for the UI and stats; check that the answer's citations really support it. Small and fast, so they fit next to the chat model on 6 GB.
- Re-run the comparison when new small models land (Ollama "newest", EuroEval Swedish leaderboard in a browser).
