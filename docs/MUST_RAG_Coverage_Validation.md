# RAG Data Coverage Validation v2 — Now Cross-Checked Against Structured JSON Data

**What changed since v1:** You provided fully structured JSON (courses_Done.json, semesters_plan_DONE.json, 4 regulation files, gpa_rules_DONE.json) instead of flowchart images. This closes several major gaps. Numbers below are computed directly from your files, not estimated.

**Legend:** ✅ Covered (static) | 🔧 Covered by design, needs live/screenshot student data | ⚠️ Partial | ❌ Not covered

---

## What actually changed (the real wins)

### 1. Credit hours per course — nearly solved
Checked programmatically against `courses_Done.json`: **95 of 104 courses have credit_hours populated.** Only 9 are null: `AI.401, CS.312, CS.401, CS.498, CS.499, IS.401, IS.498, IS.499, TRAINING` — notably, most of the nulls are Graduation Project I/II and "Selected Topics" courses (likely variable-credit by design) plus Training itself. This was your single biggest Section-2 gap in v1 (only General Major had this) — **now ~91% solved.**

### 2. Total hours required per major — now computable, with one caveat
Summed directly from `semesters_plan_DONE.json`:
- **General core (sem 1–4): 72 hours**
- **AI Major total: 140 hours**
- **CS Major total: 140 hours**
- **IS Major total: 141 hours**

**Caveat, stated in your own file's notes:** the Training course's credit hours aren't printed on the original chart — your data assumes 3 CH to keep each semester at a clean 18-hour total, and explicitly flags "please confirm with the department." So this answers "فاضلي كام ساعة للتخرج؟" **once the student's earned hours are known (still needs Track B/screenshot)** — but the total itself carries an unconfirmed assumption. Treat it as "~140, pending department confirmation," not a hard fact, until verified.

### 3. Elective-hour requirement per major — now computable
Common core: UE(1–3) + OC(1–3) = 6 slots × 2 CH = **12 hours**. Major-specific: EC(1–4) = 4 slots × 3 CH = **12 hours**. **Total elective hours required ≈ 24**, same structure across all three majors. This directly answers "أنا محتاج كام ساعة Electives؟" — a question that was a flat ❌ in v1.

### 4. GPA calculation itself — new, wasn't even attempted in v1
`gpa_rules_DONE.json` now includes the actual grade-scale table (letter grade → quality points, by credit hours) and the GPA formula. This means the bot can now **compute** a GPA from a list of (course, credit hours, grade) — not just apply GPA-based *load rules* like before. Still needs per-course grades to actually run (Track B/transcript), but the *formula itself* was completely missing before and is a real gap closed.

### 5. Elective pools with prerequisites — now listable
Each regulation file has a full `elective_course_pool` with prerequisites per course. "إيه المواد الاختيارية المتاحة؟" is now a clean static list per major, not just a category flag.

---

## Important new caveat: prerequisite confidence

Your own files flag this, and it matters: every prerequisite marked `"confidence": "Visual - verify"` was read off flowchart arrows and **has not been verified against the original source**. This applies to most semester-5-through-8 prerequisites in the 4 regulation files. A few specific issues I noticed while reading them:
- `AI.461` prerequisite listed as `"AI330"` (no dot) — likely a typo for `AI.330`, which doesn't otherwise appear as a course code in your catalog. Worth checking against the source chart.
- `CS.341`, `IS.311`, `CS.351`, `CS.381`, `MATH301` all have no printed title in your source material (flagged directly in your `_meta.unresolved_titles` note) — these need names confirmed before going live, since "مادة X اسمها إيه؟" would fail or return a placeholder for these 5 specifically.
- Course code inconsistency: `C.S381` in the CS Major semester_6 plan vs `CS.381` used everywhere else — a formatting typo that would break exact-match lookups if not normalized during ingestion.

**Recommendation:** treat all "Visual - verify" prerequisites as answerable-but-flagged in the bot's responses (e.g., "based on available data, prerequisite is X — please confirm with your advisor") until someone does a manual pass against the original 4 flowchart images.

---

## Updated section-by-section coverage

### Section 1: بيانات الطالب والتقدم الأكاديمي
| Question | v1 | v2 | Why it changed |
|---|---|---|---|
| ما هي مواد سمستر X؟ | ✅ | ✅ | unchanged, was already solid |
| فاضلي كام ساعة للتخرج؟ | ❌ | 🔧⚠️ | total hours now computed (~140, unconfirmed) — just needs student's earned hours via Track B |
| إيه المواد اللي لسه ناقصاني؟ (mandatory) | 🔧⚠️ | 🔧✅ | prerequisite graph is now much more complete/traceable; still needs live completed-courses data |
| إيه المواد اللي لسه ناقصاني؟ (electives) | ❌ | ⚠️ | can now say exact hours remaining (24 total pool), still can't name a specific required elective — same structural limit as before |
| مستوفي متطلبات التخرج (عسكري + 120 ساعة)؟ | ❌ | ❌ | **still nothing** — `practical_training_required: true` exists per major but that's just a flag that Training is required, not a status field for whether *this student* completed it, and military service status isn't in any file at all |

### Section 2: Course Information
| Question | v1 | v2 |
|---|---|---|
| مادة X كام ساعة؟ | ⚠️ (General Major only) | ✅ (95/104 courses, ~91%) |
| مادة X اسمها إيه؟ | ✅ | ✅ (minus the 5 unresolved titles above) |
| Everything prerequisite-related | ✅ | ✅ (but now flagged with the confidence caveat above) |
| متاحة الترم ده؟ / Online-Offline؟ / Sections؟ | ❌ | ❌ — **still untouched, still needs a live registrar feed, no static document will ever solve this** |

### Sections 4 & 5: Credit Hours/Load & GPA
Unchanged from v1 — already your best-covered section — **plus** now the bot can compute GPA itself from grades (new capability), not just apply load rules to a given GPA.

### Section 7: Electives
| Question | v1 | v2 |
|---|---|---|
| إيه المواد الاختيارية المتاحة؟ | ✅ | ✅ (now with prerequisites per elective, more detail) |
| أنا محتاج كام ساعة Electives؟ | ❌ | ✅ (~24 hours, computed) |

### Sections 3, 6, 8, and withdrawal questions
No material change — Section 3's SIS-dependent questions still need live data (just with much better underlying static data to compute against once they get it), Section 6 (pure prerequisites) unaffected since it was already ✅, Section 8 (fees) and withdrawal remain flat ❌ — none of the new files touch pricing or procedure.

---

## Updated overall estimate

| Bucket | v1 estimate | v2 estimate |
|---|---|---|
| ✅ Fully covered now, zero student input | ~23% | **~40–45%** |
| 🔧 Covered by design, blocked on live SIS/screenshot | ~38% | ~38% (unchanged — same blocker, better data waiting behind it) |
| ⚠️ Partial | ~10% | ~10% |
| ❌ Not covered | ~29% | **~10–15%** |

The real shift: static coverage roughly doubled, and the missing-document bucket shrank hard — down to essentially just **fees, withdrawal policy, term-offering/scheduling, and graduation admin status (military/training completion)**. Those four are now your only remaining "go get this paperwork" items; everything else is either done or waiting on live SIS access.

## What's left to request (only 4 items now)
1. **Fee schedule** — still nothing
2. **Withdrawal/add-drop procedure** — still nothing
3. **Term-by-term offering + delivery mode + sections** — inherently dynamic, needs a live feed regardless
4. **Military training + Training-course completion status field** — needs its own tracked field, not covered by `practical_training_required` (which just says the requirement exists, not whether it's met)

Plus the housekeeping items: confirm Training's real credit-hour value, resolve the 5 unnamed courses, fix the `C.S381` typo, and get the "Visual - verify" prerequisites checked against the original charts before this goes to production.
