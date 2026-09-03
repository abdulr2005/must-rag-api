"""
Test harness v2 for the MUST RAG /rag/search endpoint.
Adds: a real isolated test for the 'IS' major false-positive bug,
and doc_type-based checks (not just substring presence) for the
elective vs semester-plan distinction.
"""

import requests

BASE_URL = "http://127.0.0.1:8000"

TEST_CASES = [
    {
        "question": "مادة CS.383 عندها prerequisite ايه؟",
        "expect_course_code": "CS.383",
        "note": "Exact course-code match",
    },
    {
        "question": "الحد الأقصى للساعات لو المعدل التراكمي 3.5",
        "expect_doc_type": "gpa_article",
        "expect_metadata_contains": {"article": 1},
        "note": "GPA>=3 should hit Article 1",
    },
    {
        "question": "لو المعدل التراكمي بتاعي 1.8 اقدر اسجل كام ساعة؟",
        "expect_doc_type": "gpa_article",
        "expect_metadata_contains": {"article": 2},
        "note": "GPA<2 should hit Article 2",
    },
    {
        "question": "إيه المواد الاختيارية المتاحة في AI Major؟",
        "expect_doc_type": "elective_pool_course",
        "note": "STRICT elective check - must be elective_pool_course, not semester_plan or major_regulation_course",
    },
    {
        "question": "What is the prerequisite for AI.483?",
        "expect_course_code": "AI.483",
        "note": "Contains 'AI' code - does NOT isolate the IS bug (kept for course-code regression check only)",
    },
    {
        # This is the real IS-bug isolation test: no AI/CS/IS course code
        # present anywhere, but the English word "is" appears naturally.
        # Before the fix, this would likely surface IS-major documents
        # incorrectly. After the fix, results should be driven by
        # vector similarity alone (probably GPA or general policy docs,
        # since the question itself is major-agnostic).
        "question": "Is the GPA calculation formula the same for every student?",
        "expect_doc_type_not": "major_regulation_course",  # shouldn't randomly surface an IS-major course
        "check_no_is_major_bias": True,
        "note": "ISOLATED IS-bug test - no course code present, tests extract_major() specifically",
    },
    {
        "question": "إزاي بتتحسب الـ GPA؟",
        "expect_doc_type": "gpa_formula",
        "note": "GPA formula lookup",
    },
    {
        "question": "ما هي مواد سمستر 6 في CS Major؟",
        "expect_doc_type": "semester_plan",
        "expect_metadata_contains": {"major": "CS", "semester": 6},
        "note": "Semester + major combined filter",
    },
]


def check_result(case, top):
    """Returns (passed: bool, reason: str)"""
    metadata = top.get("metadata", {})

    if "expect_course_code" in case:
        code = case["expect_course_code"]
        found = code in str(metadata) or code in top["text"]
        if not found:
            return False, f"expected course code '{code}' not found"

    if "expect_doc_type" in case:
        actual = metadata.get("doc_type")
        if actual != case["expect_doc_type"]:
            return False, f"expected doc_type='{case['expect_doc_type']}', got '{actual}'"

    if "expect_doc_type_not" in case:
        actual = metadata.get("doc_type")
        if actual == case["expect_doc_type_not"]:
            return False, f"doc_type should NOT be '{case['expect_doc_type_not']}' but was"

    if "expect_metadata_contains" in case:
        for key, val in case["expect_metadata_contains"].items():
            if metadata.get(key) != val:
                return False, f"expected metadata[{key}]={val}, got {metadata.get(key)}"

    if case.get("check_no_is_major_bias"):
        # Specifically flag if an IS-major document got suspiciously boosted
        if metadata.get("major") == "IS":
            return False, "IS-major document surfaced with no IS-related content in question - possible false-positive bug"

    return True, "OK"


def run_tests():
    print(f"Testing against {BASE_URL}\n{'=' * 60}\n")

    try:
        health = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"Health check: {health.status_code} - {health.json()}\n")
    except Exception as e:
        print(f"COULD NOT REACH SERVER: {e}")
        return

    results_summary = []

    for i, case in enumerate(TEST_CASES, start=1):
        print(f"[{i}] Q: {case['question']}")
        print(f"    Note: {case['note']}")

        try:
            resp = requests.post(
                f"{BASE_URL}/rag/search",
                json={"question": case["question"], "top_k": 3},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("results"):
                print("    NO RESULTS RETURNED")
                results_summary.append((case["question"], "FAIL - empty"))
                continue

            top = data["results"][0]
            print(f"    Top: doc_type={top['metadata'].get('doc_type')}, score={top['score']}")
            print(f"    Text: {top['text'][:120]}...")

            passed, reason = check_result(case, top)
            status = "PASS" if passed else f"FAIL - {reason}"
            print(f"    -> {status}")

            results_summary.append((case["question"], status))

        except Exception as e:
            print(f"    ERROR: {e}")
            results_summary.append((case["question"], f"ERROR - {e}"))

        print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for question, status in results_summary:
        marker = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{marker}] {question}  ({status if marker == 'FAIL' else ''})")


if __name__ == "__main__":
    run_tests()
