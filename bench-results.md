# Model comparison, 15 Oct 2026

RTX 3060 Laptop (6 GB VRAM), Ollama 0.40.4, bge-m3 retrieval, same prompt, temperature 0.2, thinking off. Three questions with known answers: notice after 5 years (**3 months**, LAS 11 §), holiday days (**25**, SemL 4 §), "Who pays me the first two weeks when I am sick?" (**the employer, sick pay days 1–14**, SjLL). Time = warm answer (first answer includes model loading). Raw answers: `bench/2026-10-15.jsonl`.

| Model | Notice | Holidays | Sick pay (English) | Time | Verdict |
|---|---|---|---|---|---|
| gemma3:4b | ❌ "2 months" | ✅ | muddled | 3–6 s | out |
| **qwen3.5:4b** | ✅ | ✅ | mostly right, tangled opening | **2–7 s** | runner-up: fastest |
| qwen3.5:9b | ❌ "4 months", invented table | ✅ | ✅ but "karantänsavdrag" | 14–40 s | out: wrong + doesn't fit in VRAM |
| **gemma4:e4b** | ✅ cites LAS 11 § | ✅ | vague, doesn't say "employer" plainly | **3.5–4 s** (19 s cold) | **pick: careful, cites §, fast** |
| lfm2.5:8b | – | ❌ "15 days" | – | 16–22 s | out: ignores think=false, reasons in English |
| granite4.2:8b | ✅ | ✅ but adds "(15 dagar)" | ok | 18–34 s | out: slow, small errors |
| ministral-3:8b | ✅ | ✅ best nuance | ✅ clearest | 19–32 s | best wording, but 5–8× slower (6 GB, spills to CPU) |

**Findings**
- Every model answered the English question in Swedish: the prompt is written in Swedish. Fix the prompt (write it in English, or detect the question's language and say it explicitly).
- No model mentioned karensavdrag for the sick-pay question: check whether SjLL 6 § is retrieved (top-6 may miss it).
- Bigger isn't better on 6 GB: models over ~5.5 GB spill to CPU and get 5–10× slower.
