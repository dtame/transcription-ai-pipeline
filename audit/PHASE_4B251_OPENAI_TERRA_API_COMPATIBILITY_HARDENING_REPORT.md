# PHASE 4B.2.5.1 — OPENAI / GPT-5.6-TERRA API COMPATIBILITY HARDENING

## Result

PASS

Provider calls =
0

OpenAI HTTP =
0

Anthropic HTTP =
0

Historical 4B.2.5 FAIL unchanged =
FAIL

Canonical Python executable =
C:\TranscriptionAI\.venv\Scripts\python.exe

OpenAI SDK version =
2.43.0

Actual endpoint =
chat.completions

Root cause =
OpenAIEngine.build_payload mapped AIRequest.max_output_tokens onto chat.completions max_tokens for every OpenAI model. gpt-5.6-terra rejects max_tokens and requires max_completion_tokens. Provider-level max_output_tokens is a semantic budget, not the Responses API field.

Historical request SHA256 =
09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53

Corrected request SHA256 =
8a92848e412763f0e67468245f9c007ee9537ffa4f2f5469af9a6934d9ebeb31

Exact parameter changes =
max_tokens=8192 removed; max_completion_tokens=8192 added

SDK serialization =
PASS

Token limit 8192 =
8192

Temperature omitted =
PASS

json_object compatibility local =
PASS

Other server-side capabilities =
UNKNOWN

Benchmark identity =
MATCH

10/10 cases present =
YES

Label leakage =
0/10

Canonical input hashes pre/post =
pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958

Tests passed/failed =
283 passed in 9.52s

New regressions =
0

Production cache =
UNCHANGED

book.json =
NOT PUBLISHED

READY_FOR_ONE_NEW_EXPLICITLY_AUTHORIZED_TERRA_CANARY =
YES

READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT =
NO

READY_FOR_FULL_REAL_BOOK_GENERATION =
NO

Next action =
HUMAN REVIEW

## Historical status

4B.2 = FAIL
4B.2.1 = PASS
4B.2.2 = PARTIAL
4B.2.3 = PASS
4B.2.4 = FAIL
4B.2.4.1 = PASS
4B.2.5 = FAIL

Do not rewrite any historical result.

## Notes

OpenAIEngine now maps gpt-5.6-terra chat.completions output budget to max_completion_tokens=8192. Historical 4B.2.5 request 09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53 is unchanged evidence. json_object and max_completion_tokens server acceptance remain UNKNOWN. No Terra call was executed.

This phase does not authorize a Terra call.
Wait for human review.
