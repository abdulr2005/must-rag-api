from rag_api import rerank


def _row(course_code, doc_type, major, similarity, nested=False):
    metadata = {
        "doc_type": doc_type,
        "major": major,
    }

    if nested:
        metadata["raw"] = {"course_code": course_code}
    else:
        metadata["course_code"] = course_code

    return {
        "content": course_code,
        "metadata": metadata,
        "similarity": similarity,
    }


def test_arabic_ai_graduation_project_ii_ranks_ai_499_first():
    rows = [
        _row("AI.352", "elective_pool_course", "AI", 0.90),
        _row("AI.499", "graduation_project", "AI", 0.55, nested=True),
    ]

    ranked = rerank(
        "ما هي مادة مشروع التخرج الثاني لتخصص الذكاء الاصطناعي وكم عدد ساعاتها وما هو المتطلب السابق لها؟",
        rows,
    )

    assert ranked[0]["metadata"]["raw"]["course_code"] == "AI.499"


def test_arabic_cs_graduation_project_i_ranks_cs_498_first():
    rows = [
        _row("CS.442", "elective_pool_course", "CS", 0.91),
        _row("CS.498", "graduation_project", "CS", 0.56),
    ]

    ranked = rerank(
        "ما هو مشروع التخرج الأول لتخصص علوم الحاسب وكم عدد ساعاته وما هو المتطلب السابق؟",
        rows,
    )

    assert ranked[0]["metadata"]["course_code"] == "CS.498"
