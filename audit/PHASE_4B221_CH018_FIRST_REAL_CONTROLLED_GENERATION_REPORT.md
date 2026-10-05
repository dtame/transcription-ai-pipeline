**PHASE 4B.2.21 — CH018 FIRST REAL CONTROLLED GENERATION**

RESULT = PASS
AUTHORIZATION SCOPE = BOOK_GENERATION_LATER_PHASE_CH018_FIRST_REMAINING_CHAPTER_ONE_SHOT_ONLY
PROVIDER CALLS = 1
ANTHROPIC HTTP = 1
OPENAI HTTP = 0
CHAPTER = CH018
MODEL = anthropic/claude-sonnet-5
PROMPT = book-generator-faithful-restatement-1.1-candidate
PROMPT HASH = e39084dc9ed3b048bfdaa2e112b380d15957085eeb613dd74c97a32b880cec50
SOURCE CONTEXT HASH = 6a0d2ef569d711d01e0a82e93919a76e6940c6383ce25ad6be447c21b4e99937
INPUT TOKENS = 10400
OUTPUT TOKENS = 2070
FINISH REASON = end_turn
PREFLIGHT MAX COST = 0.11706
ACTUAL COST = 0.041500 USD
AUTHORIZED CAP = 0.15 USD
RETRIES = 0
FALLBACKS = 0
JSON VALID = YES
STRUCTURAL CONTRACT = PASS
SECTIONS PRESENT = ['SEC067', 'SEC068', 'SEC069', 'SEC070']
IDEA HANDLES EXPECTED = 11
IDEA HANDLES FOUND = 11
IDEA HANDLES INVALID = []
SRC HANDLES INVALID = []
AUTHORIAL VOICE REVIEW = NO_ISSUE_DETECTED
POTENTIAL SUBSTANTIVE ISSUES = 1
CANONICAL HASHES PRE/POST = pre source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958; post source=df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855 plan=01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440 transcript=1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958
CH012 UNCHANGED = YES
PRODUCTION CACHE = UNCHANGED
SEMANTIC CERTIFICATION = NOT PERFORMED
HUMAN EDITORIAL ACCEPTANCE = PENDING
book.json = NOT PUBLISHED
READY_FOR_HUMAN_REVIEW = YES
READY_FOR_NEXT_CHAPTER = NO
NEXT ACTION = HUMAN EDITORIAL REVIEW OF CH018. DO NOT GENERATE THE NEXT CHAPTER. DO NOT RETRY THE PROVIDER.

## Quality summary

The chapter is readable English teaching in the author's first person, with
direct address in the activation section and third person for other people
(the young woman, the crowd, Moussa, the pregnant woman, the husband).
It does not read as a conference report. No "The speaker explained / recounted"
frame was detected.

Four planned sections are present in order: the graveside prophecy and
resurrection; activation rather than persuasion, with Joshua/Jericho;
the church-boy raising and the unsuccessful hospital case; the vessel
versus performance. Fourteen paragraphs. Finish reason end_turn.
No detectable truncation.

All 11 planned IDEA handles appear in paras[].e. No invented IDEA or SRC
handles. REF041 (Jericho) and REF058 appear. EX047 (Moussa) and EX048
(the eight-month pregnancy / hospital death) are cited. EX046 is in the
prepared allowed set and the graveside testimony is present in the prose,
but the EX046 handle itself is absent from paras[].e. Handle presence is
not treated as content restatement, and the missing handle was not filled
in after the call.

The offline editorial heuristic flagged POTENTIAL_SUBSTANTIVE_ISSUE for
absolute wording. The triggering sentence is "But it does not always happen
that way," which is a reservation, not a strengthened guarantee. A human
reader should still check "God cannot lie," "You can't help God," and
"The outcome belongs to God, not to the failure of the one who prays"
against the sources before any acceptance.

This control does not certify semantic fidelity. CH018 is not accepted
until an explicit human decision.

Canonical Python = C:\TranscriptionAI\.venv\Scripts\python.exe
Phase = 4B.2.21
Stop reason = ONE_REAL_CALL_COMPLETED

## Stop

STOP. No second provider call. No Terra call. No next chapter.
No 18-chapter generation. No book.json. No DOCX/PDF.
Wait for human editorial review.
