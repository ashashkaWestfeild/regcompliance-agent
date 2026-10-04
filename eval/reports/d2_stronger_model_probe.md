# Stronger-model probe on the scope question (block C2, 4 Oct 2026)

**Exploratory, development data.** Not a held-out result and not a change to the frozen v1
results or to the stopped D2 attempt ([closing note](d2_closing_note.md)). Five prompts, 25
items: too few for a rate; counts only.

## What was done

The D2 detector asked a model, per batch of five items, whether a policy passage (with its
list lead-in) applies a regulatory duty to everything the regulation names ("same",
"narrower", "unclear"). On 3 Oct local qwen3:8b answered "same" on the planted narrowings C05
and L03, which is one reason D2 stopped. Here the **exact cached prompts** that contained those
items (same system prompt, schema, temperature 0, no thinking) were re-sent unchanged to:

- **qwen3.5:9b**, local (Ollama, one 8 GB laptop GPU, shared with another application during the
  run): 13.6 to 63.8 s per batch;
- **gpt-oss-120b**, hosted (Groq, the app's model): 2.0 to 4.2 s per batch.

Nothing was written to a database or to the model-call cache. Item-by-item answers:
[`d2_stronger_model_probe.json`](d2_stronger_model_probe.json).

## Result

| | qwen3:8b (3 Oct) | qwen3.5:9b | gpt-oss-120b |
|---|---|---|---|
| C05 ("savings accounts"): items quoting the planted passage answered narrower, of 5 | 0 | 1 | 3 |
| ...of which the core duty ("identify accounts operated as Money Mules"), of 2 | 0 | 0 | 1 |
| L03 (lead-in "for individual customers"): core items answered narrower, of 3 | 0 | 0 | 0 |
| Other items answered narrower (no key; unscored), of 15 | 4 | 7 | 5 |

- **C05.** The larger hosted model names "savings accounts" as the limit in 3 of the 5 items
  that quote the narrowed sentence; the 9B model once; qwen3:8b never. Even the 120B model calls
  one of the two copies of the core statement "same", so batch context still sways it.
- **L03.** No model reads the list lead-in "The frequency of periodic updation for individual
  customers shall be as follows:" as narrowing RBI's duty for all customers (0 of 3 for each).
  (qwen3:8b's one "narrower" on another L03 item named the wrong words, "following types of
  transactions", from an unrelated lead-in.) A model-only fix is not in sight here; a code rule comparing the lead-in's subject words with
  RBI's ("individual customers" against "customers") is the likelier route.
- **Noise.** Every model also answers "narrower" on items with no planted change (4, 7 and 5 of
  15), mostly by reading a sub-heading or a "Customers other than Individuals" lead-in as a limit.
  Some of these may be real (the third key's L03 note says that section states no periodicity),
  but without a key they are unscored. This is the same pressure that broke the D2 ceiling.

## What it means

A stronger model helps with the one-word qualifier (C05) but not with a limit stated in a
lead-in (L03), and it still raises unscored "narrower" answers elsewhere. It does not reopen D2:
the bar was fixed in advance and the third bank has been used. If the work resumes after
10 Oct: a lead-in rule in code, gpt-oss-120b for the scope question with the code checks kept,
and a fresh unseen bank with a frozen key to measure it.
