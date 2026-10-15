# ISAKKE handover (from the Admin session, 15 Oct 2026)

**Why it exists:** a portfolio demo of RAG, and the link in Max's Vizzit application (AI developer, local FAQ/RAG project; deadline **Fri 16 Oct**). Letter and CV are in `~/Documents/Jobb/ansokningar/2026-10-vizzit/`. Add the demo link to the letter before he sends it. Then it's a showcase for the portfolio (`~/Code/portfolio`, live at max.contigomedia.se/portfolio) and GitHub.

**Rules from Max:** budget first: free/local only, no paid APIs ("crafty, not blingy"). Commits without Claude trailers. Max says yes before anything goes public or gets sent.

## State
- Works end to end: `fetch` → `index` (610 paragraphs, bge-m3, 38 s) → `ask`/`serve` (port 8095). Splitter self-test passes. Search finds the right paragraphs, also for English questions (LAS 11 § for notice, ATL 8 § overtime, SemL 4 § holidays, SjLL sick pay).
- `ollama serve` was started by hand as the user (the system service is disabled). Models here: bge-m3, gemma3:4b, qwen3.5:4b, qwen3.5:9b.
- GPU: RTX 3060 Laptop, 6 GB VRAM, 14 GB RAM.

## Next
1. **Pick the chat model.** Max has had poor results with gemma3. `python3 bench.py <models…>` runs three questions with known answers (5 years → 3 months notice, LAS 11 §; 25 holiday days, SemL 4 §; employer pays sick pay days 1–14 minus karensavdrag, SjLL). Results: `bench-results.md`. gemma4:e4b needs a newer Ollama (0.30.4 installed, `/usr/local/bin`, needs sudo to update). Set the winner as the default in `isakke.py` and `compose.yml`.
2. Tune the prompt: gemma3 was over-emotional and said "avskedad" (fired for cause) about a notice question. Keep answers short, factual and warm.
3. Screenshot of the chat page for README + portfolio; push to a **new public GitHub repo** (Max says yes first; there are no secrets here, laws are public domain).
4. Optional: a pay comparison (SCB open salary statistics by occupation), which is part of Max's idea of a workers' champion.
5. Hosting a live demo costs a GPU; for now the demo = repo + screenshots + a short screencast.

## Ideas to keep ISAKKE on the bleeding edge
- **Decider models** (new on Ollama, Oct 2026: Liquid AI `d1` 3B, Together `tev1` 0.8B/4B, Strands `strands-decider` 2B, Bespoke `nimble`/`nimble-v3` 9B, Cloudflare `clef-flash` 9B). They turn a state + typed questions into fast decisions, not chat. Possible uses: route a question to the right law(s) before search (narrower, better retrieval); decide "answerable from the sources?" vs "ask your union / a lawyer"; tag the topic (notice, pay, hours, safety, discrimination) for the UI and stats; check that the answer's citations really support it. Small and fast, so they fit next to the chat model on 6 GB.
- Re-run the comparison when new small models land (Ollama "newest", EuroEval Swedish leaderboard in a browser).
