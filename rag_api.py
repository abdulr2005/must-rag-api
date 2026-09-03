import os
import re

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from supabase import create_client


# =========================
# Load environment variables
# =========================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([
    GEMINI_API_KEY,
    SUPABASE_URL,
    SUPABASE_KEY
]):
    raise RuntimeError("Missing environment variables")


# =========================
# Clients
# =========================

gemini = genai.Client(
    api_key=GEMINI_API_KEY
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================
# FastAPI App
# =========================

app = FastAPI(
    title="MUST RAG Retrieval API",
    version="1.0.0"
)


# =========================
# Request Schema
# =========================

class SearchRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=2
    )

    top_k: int = Field(
        default=3,
        ge=1,
        le=10
    )


# =========================
# Helper Functions
# =========================

def extract_course_codes(text: str):
    """
    Detect course codes such as:

    AI.483
    CS.383
    AI 483
    CS-383
    """

    matches = re.findall(
        r'\b([A-Za-z]{2,5})[.\s,-]?(\d{3})\b',
        text,
        flags=re.IGNORECASE
    )

    return {
        f"{prefix.upper()}.{number}"
        for prefix, number in matches
    }


def extract_gpa(text: str):
    """
    Extract GPA only when the question
    looks GPA-related.
    """

    text_lower = text.lower()

    gpa_words = [
        "gpa",
        "cgpa",
        "معدل",
        "المعدل",
        "تراكمي",
        "التراكمي"
    ]

    if not any(
        word in text_lower
        for word in gpa_words
    ):
        return None

    numbers = re.findall(
        r'\b\d+(?:\.\d+)?\b',
        text
    )

    for number in numbers:

        value = float(number)

        if 0 <= value <= 4:
            return value

    return None


def gpa_rule_matches(
    metadata: dict,
    gpa: float
):
    """
    Check whether a GPA-rule chunk matches
    the GPA mentioned in the user's question.

    Supports:
    - applies_to_cumulative_gpa
    - nested rules
    - increase_applies_to
    """

    # =========================
    # 1. Direct GPA range
    # =========================

    direct_rule = str(
        metadata.get(
            "applies_to_cumulative_gpa",
            ""
        )
    ).strip()

    if direct_rule:

        # GPA < 2
        if "أقل من 2" in direct_rule:
            return gpa < 2

        # 2 <= GPA < 3
        if (
            "من 2" in direct_rule
            and "أقل من 3" in direct_rule
        ):
            return 2 <= gpa < 3

        # GPA >= 3
        if (
            "3 فأكثر" in direct_rule
            or "3 أو أكثر" in direct_rule
            or "لا يقل عن 3" in direct_rule
            or ">=3" in direct_rule.replace(" ", "")
            or "≥3" in direct_rule.replace(" ", "")
        ):
            return gpa >= 3


    # =========================
    # 2. Nested GPA rules
    # =========================

    rules = metadata.get(
        "rules",
        []
    )

    rules_text = str(rules)

    if (
        "لا يقل عن 3" in rules_text
        or "3 فأكثر" in rules_text
        or "3 أو أكثر" in rules_text
        or ">=3" in rules_text.replace(" ", "")
        or "≥3" in rules_text.replace(" ", "")
    ):
        return gpa >= 3

    return False


def extract_semester(text: str):
    """
    Detect semester from Arabic
    or English questions.

    Examples:
    الفصل الثامن
    الفصل 8
    semester 8
    semester eight
    """

    text_lower = text.lower()

    semester_map = {
        "الأول": 1,
        "الاول": 1,
        "الثاني": 2,
        "الثالث": 3,
        "الرابع": 4,
        "الخامس": 5,
        "السادس": 6,
        "السابع": 7,
        "الثامن": 8,
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8
    }

    for word, number in semester_map.items():

        if word in text_lower:
            return number

    match = re.search(
        r'(?:semester|الفصل(?:\s+الدراسي)?)\s*(\d+)',
        text_lower
    )

    if match:
        return int(
            match.group(1)
        )

    return None


def extract_major(text: str):
    """
    Detect major from Arabic
    or English question.
    """

    text_upper = text.upper()

    if re.search(
        r'\bAI\b',
        text_upper
    ):
        return "AI"

    if re.search(
        r'\bCS\b',
        text_upper
    ):
        return "CS"

    if re.search(
        r'\bIS\.\d{3}\b',   # course code like IS.301
        text_upper
    ) or re.search(
        r'\bIS\s+MAJOR\b',  # explicit "IS Major"
        text_upper
    ):
        return "IS"

    text_lower = text.lower()

    if "ذكاء اصطناعي" in text_lower:
        return "AI"

    if (
        "علوم حاسب" in text_lower
        or "علوم الحاسب" in text_lower
    ):
        return "CS"

    if (
        "نظم معلومات" in text_lower
        or "نظم المعلومات" in text_lower
    ):
        return "IS"

    return None


def normalize_major(metadata_major):
    """
    Normalize metadata major values such as:

    AI
    AI Major
    CS Major / IS Major (shared)
    """

    value = str(
        metadata_major or ""
    ).upper()

    majors = set()

    if re.search(
        r'\bAI\b',
        value
    ):
        majors.add("AI")

    if re.search(
        r'\bCS\b',
        value
    ):
        majors.add("CS")

    if re.search(
        r'\bIS\b',
        value
    ):
        majors.add("IS")

    return majors


def is_semester_plan_question(text: str):
    """
    Detect questions asking for
    courses/modules in a semester.
    """

    text_lower = text.lower()

    plan_words = [
        "المواد",
        "مواد",
        "المقررات",
        "مقررات",
        "courses",
        "subjects",
        "semester plan",
        "study plan",
        "الخطة",
        "الخطة الدراسية"
    ]

    return any(
        word in text_lower
        for word in plan_words
    )

def is_elective_question(text: str):
    """
    Detect questions specifically about elective courses,
    as distinct from general semester-plan questions.
    Both can contain "المواد" ("courses"), so this needs to
    be checked BEFORE the generic semester-plan boost.
    """

    text_lower = text.lower()

    elective_words = [
        "اختيارية",
        "الاختيارية",
        "اختياري",
        "elective",
        "electives",
        "ec pool",
        "optional course"
    ]

    return any(
        word in text_lower
        for word in elective_words
    )


def is_university_regulation_question(text: str):
    """
    Detect questions specifically about university-level requirements or elective pools
    (general_regulation_pool), e.g. متطلبات الجامعة, متطلبات جامعة, university elective.
    """
    text_lower = text.lower()
    phrases = [
        "متطلبات الجامعة",
        "متطلبات جامعة",
        "جامعية اختيارية",
        "جامعة اختيارية",
        "university elective",
        "university electives",
        "متطلب جامعة",
        "متطلبات عامة"
    ]
    return any(p in text_lower for p in phrases)


def detect_graduation_project_intent(text: str):
    """Return 1 or 2 when a Graduation Project course is requested."""

    text_lower = text.lower()

    if re.search(r'مشروع\s+التخرج\s+(?:الثاني|2)\b', text_lower):
        return 2

    if re.search(r'مشروع\s+التخرج\s+(?:الأول|الاول|1)\b', text_lower):
        return 1

    if re.search(r'\bgraduation\s+project\s+(?:ii|2)\b', text_lower):
        return 2

    if re.search(r'\bgraduation\s+project\s+(?:i|1)\b', text_lower):
        return 1

    return None


# =========================
# Reranking
# =========================

def rerank(
    question: str,
    rows: list
):
    """
    Hybrid reranking using:

    1. Vector similarity
    2. Exact course-code match
    3. GPA-rule matching
    4. Semester matching
    5. Major matching
    6. Semester-plan intent
    7. Prerequisite intent
    8. Confidence preference
    """

    question_lower = question.lower()

    question_codes = extract_course_codes(
        question
    )

    gpa = extract_gpa(
        question
    )

    semester = extract_semester(
        question
    )

    major = extract_major(
        question
    )

    graduation_project = (
        detect_graduation_project_intent(
            question
        )
    )

    expected_graduation_code = None

    if graduation_project and major:
        expected_graduation_code = (
            f"{major}.{497 + graduation_project}"
        )

    semester_plan_intent = (
        is_semester_plan_question(
            question
        )
    )

    elective_intent = (
        is_elective_question(
            question
        )
    )

    univ_reg_intent = (
        is_university_regulation_question(
            question
        )
    )

    ranked = []

    for row in rows:

        metadata = (
            row.get("metadata")
            or {}
        )

        similarity = float(
            row.get(
                "similarity",
                0
            )
        )

        boost = 0.0


        # =========================
        # 1. Exact Course Code
        # =========================

        metadata_raw = (
            metadata.get("raw")
            or {}
        )

        if not isinstance(metadata_raw, dict):
            metadata_raw = {}

        course_code = str(
            metadata.get("course_code")
            or metadata_raw.get("course_code")
            or ""
        ).upper()

        course_code_norm = re.sub(r"[.\s,-]", "", course_code)
        question_codes_norm = {
            re.sub(r"[.\s,-]", "", q)
            for q in question_codes
        }

        if (
            course_code_norm
            and (
                course_code in question_codes
                or course_code_norm in question_codes_norm
            )
        ):
            boost += 0.20


        # =========================
        # 1a. Graduation Project Intent
        # =========================

        if graduation_project:

            if (
                expected_graduation_code
                and course_code
                == expected_graduation_code
            ):
                boost += 0.50

            if (
                metadata.get("doc_type")
                == "graduation_project"
            ):
                boost += 0.20

            elif (
                metadata.get("doc_type")
                == "elective_pool_course"
            ):
                boost -= 0.20


        # =========================
        # 2. GPA Rules
        # =========================

        if gpa is not None:

            if gpa_rule_matches(
                metadata,
                gpa
            ):
                boost += 0.35

            elif (
                metadata.get("doc_type")
                == "gpa_article"
            ):
                boost -= 0.05


        # =========================
        # 3. Semester Matching
        # =========================

        metadata_semester = (
            metadata.get(
                "semester"
            )
        )

        if semester is not None:

            if (
                metadata_semester
                == semester
            ):
                boost += 0.15

            elif (
                metadata_semester
                is not None
            ):
                boost -= 0.10


        # =========================
        # 4. Major Matching
        # =========================

        metadata_majors = (
            normalize_major(
                metadata.get("major")
            )
        )

        if major is not None:

            if (
                major
                in metadata_majors
            ):
                boost += 0.15

            elif metadata_majors:
                boost -= 0.05


        # =========================
        # 5a. University Regulation Intent
        #     (checked FIRST so university elective pools take
        #      precedence over major elective pools)
        # =========================

        if univ_reg_intent:

            if (
                metadata.get("doc_type")
                == "general_regulation_pool"
            ):
                boost += 0.40

            elif (
                metadata.get("doc_type")
                == "elective_pool_course"
            ):
                boost -= 0.15

        # =========================
        # 5b. Elective Intent (check next - takes priority
        #     over generic semester-plan since both share
        #     the word "المواد")
        # =========================

        elif elective_intent:

            if (
                metadata.get("doc_type")
                == "elective_pool_course"
            ):
                boost += 0.35

            elif (
                metadata.get("doc_type")
                == "semester_plan"
            ):
                boost -= 0.05

        # =========================
        # 5c. Semester Plan Intent
        #     (only applies when NOT an elective question)
        # =========================

        elif semester_plan_intent:

            if (
                metadata.get("doc_type")
                == "semester_plan"
            ):
                boost += 0.30

            elif (
                metadata.get("doc_type")
                == "major_regulation_course"
            ):
                boost -= 0.05


        # =========================
        # 6. Prerequisite Intent
        # =========================

        prereq_words = [
            "prerequisite",
            "prerequisites",
            "requirement",
            "requirements",
            "متطلب",
            "متطلبات",
            "المتطلب",
            "المتطلبات"
        ]

        if any(
            word in question_lower
            for word in prereq_words
        ):

            if metadata.get(
                "prerequisites_clean"
            ):
                boost += 0.10


        # =========================
        # 7. Prefer Verified Data
        # =========================

        confidence = str(
            metadata.get(
                "confidence",
                ""
            )
        ).lower()

        if confidence == "verified":
            boost += 0.03

        elif (
            confidence
            == "needs_verification"
        ):
            boost -= 0.03


        # =========================
        # Final Score
        # =========================

        final_score = (
            similarity
            + boost
        )

        row["_final_score"] = (
            final_score
        )

        row["_vector_score"] = (
            similarity
        )

        ranked.append(row)


    ranked.sort(
        key=lambda x:
        x["_final_score"],
        reverse=True
    )

    return ranked


# =========================
# Health Check
# =========================

@app.get("/")
def health():

    return {
        "status": "ok",
        "service":
            "MUST RAG Retrieval API"
    }


# =========================
# RAG Retrieval Endpoint
# =========================

@app.post("/rag/search")
def rag_search(
    request: SearchRequest
):

    try:

        # =========================
        # 1. Embed User Question
        # =========================

        embedding_result = (
            gemini.models.embed_content(

                model=(
                    "gemini-embedding-001"
                ),

                contents=(
                    request.question
                ),

                config=(
                    types.EmbedContentConfig(

                        task_type=(
                            "RETRIEVAL_QUERY"
                        ),

                        output_dimensionality=1024

                    )
                )
            )
        )

        query_embedding = (
            embedding_result
            .embeddings[0]
            .values
        )


        # =========================
        # 2. Vector Search
        # =========================
        #
        # Retrieve candidate pool
        # before reranking.
        #

        response = (
            supabase.rpc(

                "match_documents",

                {
                    "query_embedding":
                        query_embedding,

                    "match_count":
                        40,

                    "filter":
                        {}
                }

            ).execute()
        )

        rows = (
            response.data
            or []
        )


        # =========================
        # 3. Hybrid Reranking
        # =========================

        rows = rerank(
            request.question,
            rows
        )


        # =========================
        # 4. Final Top K
        # =========================

        rows = rows[
            :request.top_k
        ]


        # =========================
        # 5. Clean Response
        # =========================

        results = []

        for rank, row in enumerate(
            rows,
            start=1
        ):

            results.append({

                "rank":
                    rank,

                "text":
                    row["content"],

                "score":
                    round(
                        row[
                            "_final_score"
                        ],
                        4
                    ),

                "vector_score":
                    round(
                        row[
                            "_vector_score"
                        ],
                        4
                    ),

                "metadata":
                    row["metadata"]
            })


        return {

            "question":
                request.question,

            "count":
                len(results),

            "results":
                results
        }


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
