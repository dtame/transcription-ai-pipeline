# PHASE 4B.2.6.1 — TERRA OUTPUT BUDGET AND SEMANTIC CONTRACT FORENSICS

## A. Executive Summary

RESULT = PASS
PROVIDER CALLS = 0
OPENAI HTTP = 0
ANTHROPIC HTTP = 0
PRIMARY DIAGNOSIS = Combination: exhausted completion budget with zero visible JSON, unknown reasoning split, and a verbose 10-case output contract. json_object was not HTTP-rejected and is not semantically proven.
CERTAINTY = MEDIUM — facts about emptiness and budget are confirmed; reasoning split is UNKNOWN
RECOMMENDATION = B+C

4B.2.6 proved the corrected API contract is accepted, not that the semantic validator works. This phase did not call Terra.

## B. Historical Evidence

4B.2.5 = FAIL (HTTP 400 unsupported_parameter max_tokens).
4B.2.5.1 = PASS (local mapping to max_completion_tokens; no Terra call).
4B.2.6 = FAIL (request accepted; 8192 completion tokens; finish_reason=length; empty JSON).

4B.2.6 request SHA-256 = 8a92848e412763f0e67468245f9c007ee9537ffa4f2f5469af9a6934d9ebeb31
4B.2.5 request SHA-256 = 09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53
Contracts used in 4B.2.6 = book-semantic-validator-1.0 / book-semantic-validation-transport-1.0 / json_object / max_completion_tokens=8192.
Observed tokens = input 4076 / completion 8192.
Reasoning tokens = UNKNOWN
Observed cost = 0.106456 USD
0/10 is absence of decisions, not ten misclassifications.

Canonical hashes pre/post = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958

## C. Root Cause Analysis

### Facts (CONFIRMED)

- The server accepted max_completion_tokens=8192 and billed 8192 completion tokens.
- finish_reason=length.
- Visible message.content is empty (0 bytes).
- parse_json_payload raised AIStructuredOutputError empty. No repair. No retry.
- json_object was not HTTP 400. No usable JSON body was returned.
- Ten required handles are missing. No Terra verdict exists.

### Hypotheses

- Hidden reasoning or other non-emitted completion tokens consumed the budget before JSON.
- The ten-case contract (copied claim text + required explanations) increased planning cost enough to starve visible output.

### Unknowns

- reasoning_tokens = UNKNOWN. Do not infer 8192.
- Whether the server sent completion_tokens_details. The field was not persisted.
- Whether json_object is semantically produced by gpt-5.6-terra.
- Whether a larger budget would emit JSON.
- message.refusal persisted = UNKNOWN

### Local extraction gap (LOCALLY_VERIFIED)

- extract_thinking_tokens_from_usage reads output_tokens_details.thinking_tokens, not completion_tokens_details.reasoning_tokens.
- Missing persistence is not proof the server omitted the field.

## D. Semantic Contract Assessment

System prompt size = 2661 chars / estimated 666 tokens.
Instruction size = 1355 chars / estimated 339 tokens.
Evidence SRC size = 2227 chars / estimated 557 tokens.
Paragraph text size = 3614 chars / estimated 904 tokens.
Minimal historical JSON estimate = 1308 tokens.
Detailed historical JSON estimate = 3591 tokens.
Minimal compact JSON estimate = 336 tokens.

These sizes are estimates. They are not Terra reasoning counts.

The 1.0 contract requires copied claim text (t) and a free-form explanation (x) for every claim, plus full-paragraph offset coverage. That is useful for auditability but redundantly large. Compact 1.1-candidate keeps spans, decisions, evidence handles, reason codes, and short reservations. It does not drop semantic fidelity requirements.

FUNERAL, CONNECTIVE, P3, and P8 remain frozen. External biblical memory is not authorized evidence for P8.

## E. Strategy Comparison

| Strategy | Evidence fit | Complexity | Truncation | Resume | Control | 19 ch. | Version |
|---|---|---|---|---|---|---|---|
| A raise budget | Weak: 8192 already empty | Low | High if reasoning dominates | None | Unchanged | Poor if repeated | None |
| B compact 1.1 | Addresses confirmed verbosity | Medium | Medium | None if still 10-in-1 | Preserved | Better density | Candidate only |
| C small batches | Isolates JSON emission | Medium | Lower per call | High | Preserved | Aligned | Orchestration |
| B+C | Best match to the evidence | Medium | Lowest | High | Preserved | Aligned | Candidate 1.1 |

Recommendation = B+C

4B.2.6 confirmed budget exhaustion and zero visible JSON. Reasoning tokens are UNKNOWN, so A alone may buy more hidden tokens. The historical contract confirmedly duplicates claim text and requires free-form explanations across ten paragraphs. Compact 1.1-candidate reduces expected visible JSON without dropping fidelity fields. A one-case or two-case batch is the cheapest way to test whether Terra can emit JSON at all. Combined B+C changes two variables, but the first authorized canary should still be a single compact case so a repeat empty+length failure isolates json_object/reasoning rather than 10-case volume.

A alone is not justified as the next experiment. Cost is not linear with max_completion_tokens. Unknown cost is not reported as zero.

## F. Proposed Next Canary

This section is a proposal only. It is not an authorization.

Model = gpt-5.6-terra
Endpoint = chat.completions
Prompt / transport = book-semantic-validator-1.1-candidate / book-semantic-validation-transport-1.1-candidate
Cases = 1 (h01 / 4b22_p2_supported)
Budget = max_completion_tokens=8192
Estimated cost if min JSON = 0.004356
Worst-case if 8192 exhausted = 0.1017

4B.2.6 produced no decisions. The first question is whether Terra can emit usable JSON. h01 is the smallest isolation of that question. Negative-case power is out of scope until JSON exists.

Success criteria:
- Exactly one authorized Terra call
- Usable JSON object parsed without repair
- finish_reason != length with empty content
- h01 present with claim spans covering the paragraph
- No human-label leakage
- No cache acceptance even if SUPPORTED
- Missing cases remain unevaluated, not accepted

Stop conditions:
- HTTP 400 or any request error
- finish_reason=length and empty or non-JSON content
- Any retry, fallback, or Sonnet call
- Any second Terra call
- Any production cache write

## G. Tests and Regressions

TESTS = 157 passed in 5.28s
PASSED = 157
FAILED = 0
NEW REGRESSIONS = 0
A FakeAI PASS demonstrates local orchestration and contracts, not Terra quality.

## H. Readiness

READY_FOR_NEXT_TERRA_CANARY_DESIGN_REVIEW = YES
READY_FOR_NEW_REMOTE_TERRA_CALL = NO
READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO
READY_FOR_FULL_REAL_BOOK_GENERATION = NO
PRODUCTION CACHE = UNCHANGED
book.json = NOT PUBLISHED

## Historical status

4B.2 = FAIL
4B.2.1 = PASS
4B.2.2 = PARTIAL
4B.2.3 = PASS
4B.2.4 = FAIL
4B.2.4.1 = PASS
4B.2.5 = FAIL
4B.2.5.1 = PASS
4B.2.6 = FAIL

Do not rewrite any historical result.

NEXT ACTION = HUMAN REVIEW
No Terra call. No Sonnet call. No CH016 regeneration. No 19-chapter run. No book.json. Candidate contracts stay unpromoted.

Canonical environment executable = C:\TranscriptionAI\.venv\Scripts\python.exe
Inputs unchanged = YES
