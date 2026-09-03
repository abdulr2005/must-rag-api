# MUST Academic Advisor — RAG System Design

**Privacy note:** This design uses zero real student data. All personal/academic records (GPA, transcript, courses taken) are represented as schema placeholders only, resolved at runtime per logged-in student — never stored in the knowledge base.

**Cost note:** Every design choice below is made assuming free-tier / limited API budget. Section 6 covers token-minimization specifically — read that before implementing.

---

## 1. Core Architecture: Two-Track System

This is **not** a pure RAG system. Based on question analysis of your requirements file, questions split into two fundamentally different tracks that must be handled differently:

```
                        ┌─────────────────────┐
                        │   User Question      │
                        └──────────┬───────────┘
                                   ▼
                        ┌─────────────────────┐
                        │  Query Classifier     │
                        │  (Static vs Personal) │
                        └──────────┬───────────┘
                     ┌─────────────┴─────────────┐
                     ▼                             ▼
          ┌─────────────────────┐      ┌─────────────────────┐
          │   TRACK A: RAG        │      │  TRACK B: Function    │
          │   (Static Knowledge)  │      │  Calling (Live Data)  │
          └─────────────────────┘      └─────────────────────┘
                     │                             │
                     ▼                             ▼
          Vector DB: course catalog,      SIS/DB Query: student's
          prerequisites, electives,       transcript, GPA, completed
          GPA policy, bylaws              courses, current registration
                     │                             │
                     └─────────────┬─────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │   LLM (synthesizes    │
                        │   both into answer)    │
                        └─────────────────────┘
```

**Why this matters:** A pure-RAG design will eventually get asked "فاضلي كام ساعة للتخرج؟" and either hallucinate an answer or retrieve irrelevant document chunks. The classifier routes personal questions to a live data tool call instead of the vector store.

---

## 2. Track A — RAG Knowledge Base (What Goes In)

### 2.1 Document sources (confirmed available)
| Source | Content | Format needed |
|---|---|---|
| Curriculum flowcharts (CS, AI, IS, General) | Prerequisite graph, semester placement, elective categories (UE/OC/EC) | Convert to structured JSON — flowcharts aren't chunkable as-is |
| Course title table | Course code → name mapping | CSV/JSON |
| Registration rules decree (2026/2027 Fall) | GPA-based credit hour load rules | Chunked by article (المادة الأولى، الثانية...) |

### 2.2 Document sources (still missing — see Section 4)
- Fee schedule (per-course or per-credit-hour pricing)
- Complete credit-hour count per course (only General Major semesters 1–4 have this)
- Term-by-term course offering/availability list
- Withdrawal/add-drop procedural policy
- Graduation requirements doc (military training, 120hr practical training clauses)

### 2.3 Suggested course catalog schema (per course, no student data)
```json
{
  "course_code": "CS.383",
  "course_name": "Image Processing",
  "major": ["CS", "AI"],
  "credit_hours": null,          // MISSING for CS/AI/IS — only General Major has this
  "level_semester": 6,
  "type": "mandatory",           // mandatory | UE | OC | EC
  "department": "Computer Science",
  "prerequisites": ["CS.231", "AI.201"],
  "unlocks": ["AI.414"],
  "delivery_mode": null,         // MISSING — online/offline not in source docs
  "price_per_credit_hour": null  // MISSING — no fee schedule provided yet
}
```

### 2.4 GPA/registration policy rules (from the decree — structured, no student data)
```json
{
  "rule_set": "Fall 2026/2027 registration",
  "standard_min_hours": 12,
  "standard_max_hours": 18,
  "graduating_student_max_hours": 23,
  "graduating_student_min_cgpa": 3.0,
  "low_gpa_tier_1": { "cgpa_range": "<2.0", "min_hours": 12, "max_hours": 14, "extendable_to": 15, "note": "extra fee applies for 15th hour" },
  "low_gpa_tier_2": { "cgpa_range": "2.0–<3.0", "max_hours": "per college's academic plan" },
  "exceptions_min_hours_not_required": ["graduating student", "transferring academic stage"],
  "hard_constraint": "no schedule conflicts allowed in any case"
}
```
This is genuinely RAG-appropriate — it's policy text, identical for every student, safe to retrieve and quote.

---

## 3. Track B — Function Calling for Personalized Data

These are NOT documents. They're **tool definitions** the LLM calls at runtime against MUST's actual student information system (SIS), authenticated per logged-in student.

### 3.1 Required tools (function signatures — no data included, just schema)
```
get_student_academic_summary(student_id) →
    { cgpa, total_earned_hours, current_semester_registered_hours,
      academic_status, program }

get_student_completed_courses(student_id) →
    [ { course_code, semester_taken, grade } ]

get_student_registration_eligibility(student_id, course_code) →
    { eligible: bool, missing_prerequisites: [...], reason }

get_program_requirements(major) →
    { total_hours_required, required_courses, elective_hours_required }

get_current_term_offerings() →
    [ { course_code, sections, delivery_mode, seats_available } ]
```

### 3.2 How a personalized question actually resolves
Example — "إيه المواد اللي لسه ناقصاني؟" (What courses do I still need?):
1. LLM calls `get_student_completed_courses(student_id)` → live result
2. LLM calls `get_program_requirements(student.major)` → live result (or RAG'd from curriculum JSON, since program requirements are static)
3. LLM computes the set difference and answers — **the specific list is never stored anywhere**, it's computed fresh every time

This is the only safe way to answer this question category. A hardcoded "answers file" for these questions is not just incomplete — it's actively wrong for every student except the one whose data it was written from.

### 3.3 Screenshot upload as a fallback input path

This wasn't in the original design and is worth adding — it directly solves your biggest blocker (Section 4: SIS API access) as a stopgap.

**The problem it solves:** Track B assumes a live SIS connection. Until IT grants that access, Track B literally cannot function. A screenshot upload (like the transcript image tested earlier) lets a student self-provide their data as an alternative to a live DB query — no backend integration needed to start.

**Flow:**
```
Student uploads transcript screenshot
            ▼
   Vision extraction (ONE-TIME per session, not per message)
            ▼
   Structured JSON: { cgpa, earned_hours, semester_gpas, ... }
            ▼
   Stored in session state (in-memory / session cache — NOT the vector DB, NOT persisted)
            ▼
   All follow-up questions in that session reuse the cached JSON
   (zero re-extraction, zero re-upload needed)
```

**Extraction schema (matches what a transcript screenshot can realistically provide):**
```json
{
  "cgpa": null,
  "total_earned_hours": null,
  "semester_history": [ { "term": null, "gpa": null } ],
  "completed_courses": null,   // only available if the student expands/screenshots the per-course view, not the summary view
  "extracted_at": "session_only, discard after session ends"
}
```

**Important limitation to design around:** the summary transcript view (CGPA + earned hours) doesn't give you the *course-by-course* list needed for "إيه المواد الناقصاني؟". You'd need the student to upload the expanded per-semester course view too, or fall back to asking them to type specific course codes for that subset of questions.

**Product/privacy note:** since this reads personal academic data from an image, be explicit in the UI that the screenshot is processed for that session only and not stored — and treat this as a temporary bridge, not a permanent replacement for real SIS integration once IT access comes through (a live query is always more reliable than a screenshot that could be outdated by the time it's uploaded).

---

## 4. Data Gaps — Action Items (What You Still Need to Collect)

| Priority | Missing item | Source to request |
|---|---|---|
| High | Fee schedule (per credit hour / per course) | Finance office |
| High | Complete credit-hour table for CS/AI/IS courses | Registrar / department heads |
| Medium | Term-by-term course offering + delivery mode | Registrar (this is dynamic — consider live feed, not static doc) |
| Medium | Graduation requirement doc (military training, 120hr training clause) | Student affairs / bylaws |
| Medium | SIS API or DB access (read-only) for student records | IT department — **this is the actual blocker for Track B**, more urgent than more documents |
| Low | Withdrawal/add-drop procedure text | Registrar handbook |

---

## 5. Token/Cost Minimization — Critical Given Free-Tier Constraints

Every one of these directly reduces token spend. Ordered by impact.

### 5.1 Don't re-run vision extraction every message
The single biggest avoidable cost: if a screenshot is re-sent or re-read on every turn, you pay vision-token cost repeatedly for the same data. **Extract once, cache the JSON in session state, never re-call vision on that image again.** This is already built into the flow in 3.3 — just don't skip it in implementation.

### 5.2 Classify before you generate
Don't send every question to the full LLM to figure out "is this static or personal." Use a **cheap, non-LLM classifier first**:
- Regex/keyword rules catch most cases instantly and free: presence of "أنا / بتاعي / لسه ناقصاني" → personal; presence of a course code pattern + "كام ساعة/prerequisite" → static lookup
- Only fall back to an LLM call for genuinely ambiguous questions
- This alone can eliminate a full model call for a large fraction of traffic

### 5.3 Keep RAG chunks small and top-k low
- Chunk by logical unit (one course, one policy article) — not large blocks. Smaller, precise chunks mean fewer tokens retrieved per query
- Retrieve top-3 chunks max, not top-10 — course/policy lookups rarely need more
- Never dump the full course catalog or full decree into context "just in case" — retrieve only what the query needs

### 5.4 Use prompt caching for anything static and repeated
- The system prompt, the tool definitions (Section 3.1), and any frequently-reused policy text (like the GPA decree) should use prompt caching (supported on the Anthropic API) — cached tokens are billed at a fraction of normal input cost on repeat calls
- This matters most for the GPA policy JSON in 2.4, since it's small, static, and queried constantly

### 5.5 Minimize conversation history sent per turn
- Don't resend the entire chat history every turn once it grows long — summarize or truncate older turns, keep only the last few exchanges plus the extracted student-data JSON (which is small)
- The cached student profile (3.3) means you don't need history to "remember" GPA/hours — it's already in a compact JSON, not buried in prior chat turns

### 5.6 Use the cheapest model tier that works per task
- Classification (6.2) and simple lookups (course name, credit hours) → smallest/cheapest available model
- Only route to a larger model for genuinely complex synthesis (e.g., combining prerequisite graph + completed courses into a "what's missing" answer)
- This tiered-model approach is usually the single largest cost lever after caching

### 5.7 Cap output length
- Academic advising answers should be short and direct by design (a course name, a yes/no + reason, a number). Set a low max_tokens ceiling for most response types rather than letting the model generate long explanatory text by default.

---

## 6. Multilingual Support — Egyptian Arabic, MSA, and English

Your questions file itself is written in Egyptian colloquial Arabic (اقدر اسجل، فاضلي، ناقصاني), mixed with English course/technical terms (prerequisite, Level, Section, GPA) — so the bot needs to handle **code-switching**, not just three separate languages.

### 6.1 Language handling strategy
- **Detect, don't force**: identify the input language/dialect per message (Egyptian Arabic / MSA / English) rather than requiring the student to pick a language setting
- **Mirror the user's register**: reply in the same variety the student used — if they write in عامية مصرية, respond in عامية مصرية; if MSA, respond in MSA; if English, respond in English. Don't "upgrade" a colloquial question into a formal MSA answer — it reads as stiff and less trustworthy to students
- **Preserve English technical terms as-is**: course codes, "GPA," "prerequisite," "Level," "Section" should stay in English/Latin script even inside an Arabic sentence — this matches how your own questions file naturally mixes them

### 6.2 System prompt instruction (add to your LLM system prompt)
```
Respond in the same language and register the student used:
- Egyptian colloquial Arabic in → Egyptian colloquial Arabic out
- Modern Standard Arabic in → Modern Standard Arabic out
- English in → English out
- Mixed/code-switched in → mirror the same mix
Keep course codes, GPA, prerequisite, Level, Section, and other academic
system terms in English/Latin script regardless of response language,
since these match what students see in the actual student portal.
Do not default to Modern Standard Arabic for a colloquial question.
```

### 6.3 Embeddings and retrieval implications
- Use a multilingual embedding model (not English-only) so an Egyptian-Arabic query retrieves the right chunk even if the source doc is Arabic (decree) or English (course catalog)
- Test retrieval specifically on **mixed-language queries** ("مادة CS.383 عندها prerequisite؟") since that's your most common real pattern, not pure single-language
- Benchmark a couple of free/lightweight multilingual embedding options rather than defaulting to the largest one — your corpus (course catalog + one decree) is small and doesn't need a heavyweight model (ties back to Section 5's cost focus)

### 6.4 What NOT to do
- Don't build three separate knowledge bases per language — one knowledge base, multilingual embedding, language-aware generation. Tripling the corpus triples storage/retrieval cost for no benefit
- Don't pre-translate source documents into English/colloquial copies — translate at response time only, so the source-of-truth stays exactly as issued by the registrar

---

## 7. Implementation Plan

Phased so each step produces something testable before the next — no phase blocks on something you don't have yet.

### Phase 0 — Data structuring (no coding required)
| Task | Output | Blocked by? |
|---|---|---|
| Convert the 4 curriculum flowcharts into course JSON (2.3) | `courses.json` | Nothing — already have the images |
| Chunk the registration decree by article (2.4) | `registration_policy.json` | Nothing — already have the PDF |
| Request missing docs — fees, full CH tables, graduation requirements (Section 4) | Requests sent | Nothing — send in parallel |
| File SIS read-access request with IT | Ticket filed | Nothing — expect this to take longest, don't wait on it |

### Phase 1 — Static-question RAG pipeline
| Task | Output |
|---|---|
| Stand up a vector DB (prefer a free/self-hosted option over paid managed, given budget) | Working vector store |
| Embed `courses.json` + `registration_policy.json` with a multilingual model (7.3) | Populated index |
| Build the cheap static/personal classifier (5.2) | Classifier function |
| Build retrieval + generation for static-bucket questions | Answers "مادة X ليها prerequisite؟" etc. |
| **Checkpoint:** run every static-bucket question from Problem.txt through it, log pass/fail | Accuracy report |

### Phase 2 — Personalized questions via screenshot fallback
| Task | Output |
|---|---|
| Build screenshot upload + one-time vision extraction (3.3) | Session-cached student JSON |
| Build compute-on-the-fly logic (remaining hours, missing courses, GPA load) from cached JSON + `courses.json` | Answers personal questions, stores nothing |
| **Checkpoint:** re-run the transcript example from earlier in this conversation end to end | Pass/fail |

### Phase 3 — Multilingual + cost polish
| Task | Output |
|---|---|
| Add the language-mirroring system prompt (7.2) | Correct-register responses |
| Test mixed Egyptian-Arabic/English queries specifically | Retrieval quality check |
| Apply prompt caching to system prompt + policy JSON (5.4) | Lower cost per call |
| Cap output length per response type (5.7) | Lower cost per call |

### Phase 4 — Swap in live SIS (once IT access lands)
| Task | Output |
|---|---|
| Replace screenshot fallback with live `get_student_*` tool calls (3.1) | Real-time personal answers |
| Keep screenshot upload as a manual backup path | Resilience if SIS is down |
| Re-run the full Problem.txt suite (static + personal) | Final coverage report |

**Can start today with zero dependencies:** Phase 0, plus the first two rows of Phase 1 — you already have every input needed. Say the word and I'll generate `courses.json` from the 4 flowchart images now.

---

## 8. Recommended Build Order (Quick Summary)

1. **Structure what you have now** — convert the 4 flowcharts + course title table into the JSON schema above (I can help generate this)
2. **Chunk and embed the registration decree** — small, stable, high-value document, with prompt caching applied
3. **Build the cheap classifier first** (6.2) — this is what keeps costs down from day one, not an afterthought
4. **Build the screenshot-upload fallback** (3.3) for personalized questions — unblocks Track B without waiting on SIS access
5. **Request the missing static docs** (fees, full CH tables, graduation requirements) in parallel
6. **Request SIS read access from IT** in parallel — once granted, swap the screenshot fallback for live queries without changing the rest of the architecture
