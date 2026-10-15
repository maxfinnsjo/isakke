# ISAKKE handover (from the Admin session, 15 Oct 2026)

**Rules from Max:** budget first: free/local only, no paid APIs ("crafty, not blingy"). Commits without Claude trailers. Max says yes before anything goes public or gets sent.

## State
- Works end to end: `fetch` → `index` (610 paragraphs, bge-m3, 38 s) → `ask`/`serve` (port 8095). Splitter self-test passes. Search finds the right paragraphs, also for English questions (LAS 11 § for notice, ATL 8 § overtime, SemL 4 § holidays, SjLL sick pay).
- Ollama is now the repo package `ollama-cuda` 0.40.4 (paru keeps it current). `ollama serve` runs as the user (models in `~/.ollama`); start it with `ollama serve &` if it's not running. Models here: bge-m3, gemma4:e4b, qwen3.5:4b (the losers of the comparison are removed).
- GPU: RTX 3060 Laptop, 6 GB VRAM, 14 GB RAM.

## Next
1. Done: default chat model is gemma4:e4b (`isakke.py`, `compose.yml`; fallback qwen3.5:4b). Prompt is English with the answer-language rule last; the question is translated to Swedish before embedding (English queries ranked LAS 11 § 12th, now top). Karensavdrag retrieves SjLL 6 §.
2. Done: sick pay. A terminology line (sjuklön = employer-paid sick pay, not sjukpenning) and "start with a direct one-sentence answer" in the prompt; the employer is named in 6 of 6 runs (Swedish and English), `bench.py gemma4:e4b` is 3/3 correct at 1.3–1.8 s.
3. Media: `docs/demo.gif` (animated, in the README: GitHub strips <video> tags for repo files, so a GIF is the only inline option), `docs/demo.mp4` (the same 56 s in better quality, for a real player on the portfolio page), `docs/live.png` (live demo). Done: public repo https://github.com/maxfinnsjo/isakke (local branch `development` tracks `origin/main`; push with `git push origin development:main`).
4. Done: SCB pay answers, decider off-topic gate (see Findings), two Docker profiles (README table), live slim demo.
5. **Live demo:** https://max.contigomedia.se/isakke (redirect to https://isakke.206.168.215.98.sslip.io/; linked from the README; HEAD requests return 501, only GET/POST are implemented) on the shared VPS (2 vCPU, 3.9 GB RAM, ~2 GB free next to other apps). `deploy/deploy.sh` (needs a clean git tree, aborts under 1.8 GB free RAM; `--stop` takes it down, `--dry-run` previews). Ollama capped at 2 GB, app 256 MB, bge-m3 unloads after 60 s idle (~100 MB idle). Per-IP limit 20/min (Caddy overwrites a spoofed X-Forwarded-For, tested). The image set is ~7 GB of the VPS disk. Redeploy after changing code or laws: commit, `deploy/deploy.sh`. A changed `laws/` needs `python3 isakke.py index` and a commit of `index.npz`.
6. CPU findings (4 threads, no GPU): qwen3.5:0.8b/2b and granite4:micro are fast-ish but wrong (invented days, mixed languages) and can't even do the translate/pay-intent prompt; ministral-3:3b is correct but 30–100 s per answer and 3 GB. qwen3.5:4b/gemma4:e2b not measured (too big for the VPS anyway). Hence slim = retrieval only.
7. Desktop Docker test (from scratch, 12 GB download) passed: GPU passthrough, decider on CPU, answers right. First request after start ~100 s (four models load). The test volume `isakke_ollama` (~12 GB) is still on this machine: `docker volume rm isakke_ollama` to free it.
8. Ideas left: a real answer on a CPU host needs a better small model than today's (re-run `cpubench`-style tests when one lands); a free-tier GPU or cheap GPU host would allow the desktop profile as the demo.

## Findings (15 Oct, research)
**SCB pay data: feasible, no key, CC0.** PxWebApi v1 works: `https://api.scb.se/OV0104/v1/doris/sv/ssd/AM/AM0110/AM0110A/LonYrkeRegion4AN` (average monthly pay 2023–2025 by region, sector, SSYK 2012 occupation (432 codes) and sex; also base pay, headcount, women's pay as % of men's). POST a JSON query with `"response":{"format":"csv"}`; output is latin-1. Example: 2221 Grundutbildade sjuksköterskor 2025 = 44 000 kr (men 45 200, women 43 900). v2 (`statistikdatabasen.scb.se/api/v2`, 30 calls per 10 s) exists too. Plan: a "pay" intent that maps the profession in the question to an SSYK code (embed the 432 titles with bge-m3, like the laws), fetches live, and answers with the figure, the gender gap and the source. It needs its own code path, since the laws prompt says "use ONLY the sources".

**Decider models.** Ollama 0.35+ has `POST /v1/systemone` (state + typed questions: `choice`, `noul` yes/no probability, `score`). Models: `nimble`/`nimble-v3` (9B, too big for 6 GB), `tev1` (4B, 2.5 GB), `tev1:0.8b` (833 MB, installed along with tev1). `strands-decider` needs MLX (Apple only) and fails here; `d1` and `clef-flash` are hosted-only, not in Ollama.
- Routing works: tev1:0.8b picks LAS/SemL/ATL/SjLL/AML/MBL/none in about 60 ms warm, right on 5 of 5 labour questions. It also detects the pay intent ("Vad tjänar en sjuksköterska?" → pay 0.82). Off-topic detection is weak ("Hur lagar jag pasta?" → ATL 0.51), so use a threshold or a separate "is this about work?" question.
- Update: 4B off-topic check works ("about work?" 0.80–0.91 vs 0.00–0.02); hard law routing gave no retrieval gain. See `on_topic()`.
- Citation check does NOT work: 0.8B scores right and wrong answers 0.19/0.20; tev1 4B scored a wrong "four months" 0.43 above the right "three months" 0.40. Don't build it.
- Routing gain is unproven: retrieval is already good with the translate step. Test by restricting search to the routed law and re-running `bench.py`.

## Ideas to keep ISAKKE on the bleeding edge
- Re-run the comparison when new small models land (Ollama "newest", EuroEval Swedish leaderboard in a browser).

## Roadmap
- ARM / phone: run the slim profile on an ARM host or a phone (Termux + Ollama). Parked by Max, not started.
- Hosted free-tier models for the slim demo: LIVE since 15 Oct. `~/apps/isakke/.env` on the VPS (mode 600, never in the repo) holds the keys copied server-side from skandinavet's `.env` (LLM_API_KEY, GROQ_, OLLAMA_, OPENROUTER_) and ISAKKE's own chain: ollamacloud:gemma4:31b, groq:openai/gpt-oss-120b, ollamacloud:gpt-oss:120b, openrouter nvidia nemotron :free; caps 100 AI answers/day, 8 per visitor. The Gemini models were left out (skandinavet had them out of quota). The keys and the free quotas are SHARED with skandinavet: if the news channel starves, lower LLM_DAILY_MAX or take gpt-oss:120b out of the chain; to switch AI off, delete the LLM_CHAIN line there and run `deploy/deploy.sh` (back to search mode). Live test: gemma4:31b via Ollama Cloud, 1-6 s, correct in sv and en, the number check flags the correct "14 days" (a sum of 1+13). Tested with a fake provider (order, 429/402 blocking, per-client cap, fallback to search mode) and with local gemma4 over /v1 (note: a thinking model needs reasoning_effort set or it uses all max_tokens; done per provider). Add providers in PROVIDERS. This HANDOVER and deploy/ show the demo URL in the public repo.

## Logging
`deploy/deploy.sh --logs` follows the live demo's log: one JSON line per page visit, question (with client IP, kind law/pay/refused, top paragraphs, ms), rate-limit hit or backend error. Docker keeps 3 x 5 MB, then rotates.
