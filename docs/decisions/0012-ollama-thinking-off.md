# 0012. Ollama requests switch thinking off

- **Status:** Accepted
- **Date:** 2026-10-20

## Context
Some local models are "thinking" models: before answering, they write
hidden reasoning, which Ollama returns in a separate `thinking` field. That
reasoning counts toward the token limit. QuestVector caps narrative
generation at 600 tokens, which is plenty for a 3–4 sentence summary
without reasoning.

On 20 Oct 2026, QuestVector's unchanged Ollama path was run against two
thinking models, qwen3.5:9b-q4_K_M and gemma4:12b-it-q4_K_M, using
synthetic data. All six runs failed. Five spent the whole 600 tokens
reasoning and returned an empty answer (89–120 s each). The sixth ran past
the then-fixed 120-second timeout.

Ollama's `/api/generate` takes a `think` option: true/false, or a level.
On Ollama 0.40.6, `think: false` was accepted by all three models tried,
including llama3.1:8b, which can't think. `think: true` on llama3.1:8b
fails with HTTP 400 "does not support thinking".

The same three models were then run 5 times each with thinking off. The
runs used the prompt QuestVector builds from the synthetic fixtures in
`tests/fixtures/ollama_live/`, a 600-token limit and a 600-second timeout.
Invented facts were judged by reading every output.

| Model | Runs with invented facts | Trap words (Datadog / Vault / SOC 2) | Third-person pronouns | "Here is…" preamble | Sentences (3–4 asked) | Tokens, median (range) | Time, median (range) |
|---|---|---|---|---|---|---|---|
| llama3.1:8b | 3 of 5 | SOC 2 in 1 run | 0 | 5 of 5 | 4 in every run, plus the preamble | 164 (129–192) | 31.8 s (22.8–41.6) |
| qwen3.5:9b-q4_K_M | 3 of 5 | SOC 2 in 2 runs | 0 | 0 | 3–4 | 157 (92–168) | 31.7 s (18.2–45.6) |
| gemma4:12b-it-q4_K_M | 0 of 5 | none | 0 | 0 | 4 in every run | 141 (132–151) | 25.2 s (22.6–46.6) |

All 15 runs finished normally, well under the limit. Each model's first
run includes 4–9 s to load it. Examples of invented facts: "7+ years of
experience" taken from the job description (llama3.1); "Senior DevOps
Manager with over a decade of experience" (qwen3.5); "led successful SOC 2
Type II audit efforts" (llama3.1).

Options considered:
- **A. Always send `think: false`.** One field in the request.
- **B. A vault setting to turn thinking on or off, default off.** More
  settings and tests for a choice nobody has needed yet.
- **C. Leave thinking on and raise the token limit.** Measured at 90–120 s
  a run, and the token limit no longer bounds the summary.
- **D. Ask Ollama for the model's capabilities first, then decide.** An
  extra request every time, for the same outcome as A.

## Decision
`OllamaNarrativeGenerator` always sends `"think": false` to
`/api/generate`. This extends [ADR-0005](0005-ollama-over-plain-http.md);
it doesn't replace it.

## Consequences
- Thinking models answer within the token limit, in about the same time as
  non-thinking models.
- Models lose their reasoning step, which a short summary didn't need in
  these runs. The most accurate model in this test (gemma4) was running
  with thinking off.
- Tested only on Ollama 0.40.6; how other versions treat `think` hasn't been
  checked. If a model still returns reasoning and runs out of tokens, the
  error says so instead of returning an empty answer.
- Revisit with option B if a user needs thinking on.
- The invented facts and the preamble are accuracy problems, handled
  separately (backlog item 5, PRD R14).
