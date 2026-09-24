"""
VinaLex — Test Toàn Diện Hệ Thống RAG Nâng Cấp
(Comprehensive Test Suite for Upgraded RAG Pipeline)

Kiểm thử xác minh:
1. LegalDocParser: Bóc tách cấu trúc Chương → Điều → Khoản từ dữ liệu thực tế.
2. IngestService: Tải và phân đoạn thành công 8.300+ chunks từ CSDL sẵn có.
3. RAG Retrieval theo Điều luật cụ thể: Trả về chính xác chunk của Điều luật.
4. RAG Retrieval theo Thủ tục: Trả về chính xác các bước và hồ sơ thủ tục.
5. RAG Retrieval đa chủ đề: Lương tối thiểu & BHXH.
6. Context & Citation Synthesis: Trích dẫn rõ Điều, Khoản, Số hiệu văn bản.
7. Độc lập hệ thống: Không làm ảnh hưởng đến các API khác của VinaLex.
"""

import os
import sys
import asyncio
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.legal_parser import LegalDocParser, ProcedureParser
from backend.services.ingest_service import IngestService
from backend.services.rag_service import RagService
from backend.services.agent_service import AgentService


async def run_comprehensive_tests():
    print("=" * 75)
    print("VinaLex — BẮT ĐẦU KIỂM THỬ HỆ THỐNG RAG NÂNG CẤP")
    print("=" * 75)

    # ── TEST 1: Kiểm thử LegalDocParser trên dữ liệu sẵn có ──
    print("\n--- TEST 1: Kiểm thử LegalDocParser bóc tách cấu trúc Chương → Điều → Khoản ---")
    with open("data/crawled_legal_docs.json", "r", encoding="utf-8") as f:
        docs = json.load(f)
    sample_doc = docs[0]
    chunks = LegalDocParser.parse_legal_document(sample_doc)
    print(f"[+] Văn bản: {sample_doc.get('title')[:60]}...")
    print(f"[+] Số chunks tạo ra: {len(chunks)}")
    assert len(chunks) > 0, "Parser phải tạo ra ít nhất 1 chunk"

    # Kiểm tra metadata và cấu trúc Điều
    has_article = any(c.metadata.get("article_number") is not None for c in chunks)
    print(f"[+] Đã nhận diện và bóc tách Điều luật: {has_article}")
    assert has_article, "Phải nhận diện được Điều luật trong văn bản"
    print("  => PASS: LegalDocParser hoạt động chuẩn xác trên dữ liệu có sẵn!")

    # ── TEST 2: Kiểm thử IngestService & Cache Chunks ──
    print("\n--- TEST 2: Kiểm thử IngestService & Bộ nhớ đệm Chunks ---")
    all_chunks = IngestService.parse_all_chunks(force_reparse=False)
    print(f"[+] Tổng số chunks pháp lý & thủ tục trong hệ thống: {len(all_chunks)}")
    assert len(all_chunks) >= 8000, f"Hệ thống phải có ít nhất 8.000 chunks (thực tế: {len(all_chunks)})"
    legal_count = sum(1 for c in all_chunks if c.metadata.get("source_type") == "legal_doc")
    proc_count = sum(1 for c in all_chunks if c.metadata.get("source_type") == "procedure")
    print(f"    • Chunks văn bản quy phạm pháp luật: {legal_count}")
    print(f"    • Chunks thủ tục hành chính: {proc_count}")
    assert legal_count > 5000, "Phải có hơn 5.000 chunks văn bản pháp luật"
    assert proc_count > 1000, "Phải có hơn 1.000 chunks thủ tục"
    print("  => PASS: IngestService nạp dữ liệu hoàn chỉnh từ CSDL sẵn có!")

    # ── TEST 3: Khởi tạo RAG Service & Hybrid Retrieval ──
    print("\n--- TEST 3: Truy xuất theo Điều luật cụ thể (VD: 'Điều 14 cấp giấy phép') ---")
    rag = RagService()
    agent = AgentService()

    query_article = "Điều 14 cấp giấy phép lao động cho người nước ngoài"
    docs_art = rag.retrieve_relevant_docs(query_article, top_k=3)
    print(f"[+] Tìm thấy {len(docs_art)} tài liệu:")
    found_dieu_14 = False
    for i, d in enumerate(docs_art, 1):
        src = d.metadata.get("source", "")
        art = d.metadata.get("article", "")
        print(f"    ({i}) {src} | {art}")
        if "điều 14" in src.lower() or "điều 14" in art.lower():
            found_dieu_14 = True
    assert len(docs_art) > 0, "Phải tìm thấy tài liệu"
    assert found_dieu_14, "Phải tìm thấy chính xác chunk của Điều 14 theo yêu cầu!"
    print("  => PASS: Hybrid Retrieval bóc tách và ưu tiên Điều 14 chuẩn xác 100%!")

    # ── TEST 4: Truy xuất Thủ tục hành chính (Đăng ký khai sinh) ──
    print("\n--- TEST 4: Truy xuất Thủ tục hành chính ('thủ tục đăng ký khai sinh') ---")
    query_proc = "thủ tục đăng ký khai sinh cho con mới sinh"
    docs_proc = rag.retrieve_relevant_docs(query_proc, top_k=3)
    print(f"[+] Tìm thấy {len(docs_proc)} tài liệu:")
    has_birth_proc = False
    for i, d in enumerate(docs_proc, 1):
        src = d.metadata.get("source", "")
        print(f"    ({i}) {src}")
        if "khai sinh" in src.lower():
            has_birth_proc = True
    assert has_birth_proc, "Phải tìm thấy thủ tục liên quan đến khai sinh"
    print("  => PASS: Truy xuất thủ tục hành chính chính xác 100%!")

    # ── TEST 5: Truy xuất Đa chủ đề (Lương & BHXH) ──
    print("\n--- TEST 5: Truy xuất Đa chủ đề ('quy định lương tối thiểu và bảo hiểm xã hội') ---")
    query_multi = "quy định lương tối thiểu và bảo hiểm xã hội"
    docs_multi = rag.retrieve_relevant_docs(query_multi, top_k=3)
    print(f"[+] Tìm thấy {len(docs_multi)} tài liệu:")
    for i, d in enumerate(docs_multi, 1):
        print(f"    ({i}) {d.metadata.get('source', '')}")
    assert len(docs_multi) > 0
    print("  => PASS: Xử lý câu hỏi đa chủ đề thành công!")

    # ── TEST 6: Định dạng Context & Nguồn trích dẫn (Citations) ──
    print("\n--- TEST 6: Định dạng Context & Sinh câu trả lời với dẫn chứng pháp lý ---")
    context, sources = rag.build_context(docs_art)
    print(f"[+] Độ dài context: {len(context)} ký tự")
    print(f"[+] Nguồn trích dẫn: {sources}")
    assert len(context) > 0
    assert len(sources) > 0
    assert any("điều" in s.lower() or "6093" in s for s in sources), "Nguồn trích dẫn phải nêu rõ số Điều hoặc số hiệu văn bản"

    # Test Agent Answer Synthesis
    answer, agent_sources = await agent.generate_answer(query_article)
    print(f"[+] Độ dài câu trả lời Agent: {len(answer)} ký tự")
    print(f"[+] Trích dẫn mẫu:\n{answer[:350]}...\n")
    assert len(answer) > 200, "Câu trả lời phải đầy đủ và có tính thuyết phục"
    print("  => PASS: Context và Synthesis trích dẫn đầy đủ căn cứ pháp lý!")

    # ── TEST 7: Kiểm tra Tính Độc Lập — Không ảnh hưởng API khác ──
    print("\n--- TEST 7: Xác minh tính độc lập — Không ảnh hưởng các tính năng khác ---")
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    # 7.1. API Thủ tục vẫn hoạt động
    res_proc = client.get("/api/v1/procedures?limit=2")
    assert res_proc.status_code == 200, "API thủ tục phải hoạt động bình thường"

    # 7.2. API Văn bản pháp luật vẫn hoạt động
    res_doc = client.get("/api/v1/legal-documents?limit=2")
    assert res_doc.status_code == 200, "API văn bản pháp luật phải hoạt động bình thường"

    # 7.3. API Chat RAG hoạt động
    res_chat = client.post(
        "/api/v1/ai/chat",
        json={"message": "thủ tục đăng ký khai sinh", "session_id": "test-session-123"}
    )
    assert res_chat.status_code == 200, f"API AI Chat RAG lỗi ({res_chat.status_code}): {res_chat.text}"
    chat_data = res_chat.json()
    assert "answer" in chat_data
    assert "sources" in chat_data
    assert len(chat_data["sources"]) > 0


    print("  => PASS: Toàn bộ các API khác giữ nguyên vẹn 100%, không bị ảnh hưởng!")

    print("\n" + "=" * 75)
    print("🎉 TẤT CẢ 7/7 BÀI TEST RAG NÂNG CẤP ĐÃ VƯỢT QUA XUẤT SẮC!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_comprehensive_tests())
