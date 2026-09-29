from backend.api.procedures import filter_and_rank_procedures
from backend.services.agent_service import AgentService
from backend.services.legal_search import analyze_query, contains_phrase, normalize_text
from backend.services.rag_service import RagService
from backend.services.rag_service import Document


def test_query_normalization_entities_and_synonyms():
    query = analyze_query("Khoản 2 Điều 14 Nghị định 13/2023/NĐ-CP về CCCD")
    assert query.article == 14
    assert query.clause == 2
    assert query.document_numbers == ("13/2023/nd-cp",)
    assert "can cuoc" in query.expanded_terms
    assert normalize_text("Đăng ký  khai-sinh!") == "dang ky khai-sinh"


def test_phrase_matching_respects_word_boundaries():
    assert contains_phrase("Đăng ký khai sinh", "khai sinh")
    assert not contains_phrase("khai sinhvien", "khai sinh")


def test_procedure_search_understands_abbreviation_and_accentless_query():
    items = [
        {"title": "Cấp thẻ căn cước", "description": "", "tags": ["căn cước công dân"], "view_count": 1},
        {"title": "Đăng ký khai sinh", "description": "", "tags": ["hộ tịch"], "view_count": 99},
    ]
    results = filter_and_rank_procedures(items, search="lam cccd")
    assert [item["title"] for item in results] == ["Cấp thẻ căn cước"]


def test_legal_scenario_flags_issues_and_missing_decisive_facts():
    analysis = AgentService.analyze_legal_scenario("Tôi có bị phạt và phải bồi thường không?")
    assert "Vi phạm và chế tài" in analysis["issues"]
    assert "thời điểm xảy ra sự việc" in analysis["missing_facts"]
    assert "tư cách và quan hệ giữa các bên" in analysis["missing_facts"]


def test_prompt_requires_grounded_conditional_reasoning():
    prompt = AgentService().build_prompt("Tôi có được cấp phép không?", "Điều 1. Điều kiện A")
    assert "Vấn đề pháp lý" in prompt
    assert "nếu... thì..." in prompt
    assert "Không tự tạo căn cứ" in prompt


def test_rag_returns_no_unrelated_default_documents(monkeypatch):
    service = RagService()
    service._initialize = lambda: None
    service._all_chunks = [Document(page_content="Quy định về đất đai", metadata={"title": "Đất đai"})]
    monkeypatch.setattr(RagService, "_shared_inverted_index", {})
    monkeypatch.setattr(RagService, "_shared_preprocessed", [])
    monkeypatch.setattr(RagService, "_shared_article_map", {})
    monkeypatch.setattr(RagService, "_shared_doc_num_map", {})
    assert service.retrieve_relevant_docs("xin chào") == []
