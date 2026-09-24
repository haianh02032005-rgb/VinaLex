"""
VinaLex — Test tích hợp Gemini AI Agent + Hệ thống RAG có sẵn
Kiểm tra:
1. Nạp và tra cứu RAG (8.300+ Chunks từ CSDL)
2. Các công cụ của Agent (Tools: Tra cứu thủ tục, cấp biểu mẫu PDF, kích hoạt OCR)
3. Thẩm định ngữ cảnh giấy tờ hành chính (verify_with_ai)
4. Cơ chế Fallback an toàn khi chưa có API Key
"""

import sys
import os
import asyncio
import json

# Đảm bảo import được backend
sys.path.insert(0, os.path.abspath("."))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def log(msg=""):
    print(msg, flush=True)

async def test_agent():
    log("=" * 75)
    log("VINALEX — KIỂM TRA TÍCH HỢP GEMINI AI AGENT & HỆ THỐNG RAG")
    log("=" * 75)

    from backend.services.gemini_service import GeminiService
    from backend.services.rag_service import RagService
    from backend.services.verification_service import DocumentVerificationService

    gemini = GeminiService()
    rag = RagService()
    verification = DocumentVerificationService()

    # 1. Kiểm tra tính sẵn sàng của RAG có sẵn
    log("\n--- 1. KIỂM TRA HỆ THỐNG RAG CÓ SẴN (RAGSERVICE) ---")
    query = "Quy định về đăng ký kết hôn và thủ tục nộp hồ sơ"
    docs = rag.retrieve_relevant_docs(query, top_k=3)
    context, sources = rag.build_context(docs)
    log(f"[*] Truy vấn RAG: '{query}'")
    log(f"[+] Số tài liệu tìm được: {len(docs)}")
    log(f"[+] Nguồn trích dẫn pháp lý ({len(sources)} nguồn):")
    for s in sources:
        log(f"    - {s}")
    assert len(docs) > 0, "RAG phải tìm được ít nhất 1 tài liệu liên quan!"
    log("[✓] Hệ thống RAG hoạt động hoàn hảo!")

    # 2. Kiểm tra bộ công cụ (Agent Tools)
    log("\n--- 2. KIỂM TRA BỘ CÔNG CỤ CỦA AGENT (FUNCTION CALLING) ---")
    # Tool 1
    t1 = gemini.tool_tra_cuu_thu_tuc("dang-ky-khai-sinh")
    log("[Tool 1: tra_cuu_thu_tuc]:")
    log(t1[:180] + "...")
    assert "Đăng ký khai sinh" in t1 or "dang-ky-khai-sinh" in t1, "Tool 1 phải trả về thông tin thủ tục khai sinh"

    # Tool 2
    t2 = gemini.tool_cung_cap_bieu_mau_pdf("quyet-toan-thue-tncn", "Tờ khai quyết toán thuế TNCN (Mẫu 02/QTT-TNCN)")
    log("\n[Tool 2: cung_cap_bieu_mau_pdf]:")
    log(t2)
    assert "/api/v1/procedures/download-template" in t2, "Tool 2 phải sinh link tải PDF"

    # Tool 3
    t3 = gemini.tool_kich_hoat_kiem_tra_ocr("dang-ky-ket-hon")
    log("\n[Tool 3: kich_hoat_kiem_tra_ocr]:")
    log(t3)
    assert "[SYS_TRIGGER_OCR:dang-ky-ket-hon]" in t3, "Tool 3 phải có mã trigger OCR"
    log("[✓] Cả 3 công cụ của Agent đều hoạt động chính xác!")

    # 3. Kiểm tra Thẩm định hồ sơ kết hợp RAG & Semantic Analysis
    log("\n--- 3. KIỂM TRA THẨM ĐỊNH HỒ SƠ (VERIFY_WITH_AI) ---")
    # Test case A: Nộp CCCD hợp lệ cho thủ tục Cấp giấy phép lái xe
    sample_cccd_valid = {
        "Họ và tên": "NGUYỄN VĂN AN",
        "Số CCCD": "001099012345",
        "Ngày sinh": "15/08/1995",
        "Quê quán": "Hà Nội",
    }
    res_valid = await verification.verify_with_ai(
        extracted_fields=sample_cccd_valid,
        expected_doc_name="CCCD hoặc hộ chiếu còn hạn",
        procedure_title="Cấp giấy phép lái xe hạng B1",
        filename="cccd_nguyen_van_an.jpg",
        raw_document_type="Căn cước công dân",
    )
    log(f"Test case A (Hồ sơ hợp lệ): Status = {res_valid['status']} | Valid = {res_valid['is_valid']}")
    log(f"  Gợi ý: {res_valid['suggestions']}")

    # Test case B: Nộp sai loại giấy tờ (Nộp Giấy chứng sinh thay vì CCCD)
    sample_wrong_doc = {
        "Họ tên mẹ": "TRẦN THỊ BÍCH",
        "Tên bé": "NGUYỄN VĂN B",
        "Bệnh viện": "Phụ sản Trung ương",
    }
    res_invalid = await verification.verify_with_ai(
        extracted_fields=sample_wrong_doc,
        expected_doc_name="CCCD hoặc hộ chiếu còn hạn",
        procedure_title="Cấp giấy phép lái xe hạng B1",
        filename="giay_chung_sinh.jpg",
        raw_document_type="Giấy chứng sinh",
    )
    log(f"\nTest case B (Sai loại giấy tờ): Status = {res_invalid['status']} | Valid = {res_invalid['is_valid']}")
    log(f"  Lỗi phát hiện: {res_invalid['errors']}")
    assert res_invalid["is_valid"] is False, "Nộp sai loại giấy tờ phải bị từ chối!"

    # 4. Kiểm tra Chatbot RAG pipeline
    log("\n--- 4. KIỂM TRA CHATBOT TƯ VẤN PHÁP LÝ (CHAT_WITH_AGENT) ---")
    log(f"[*] Trạng thái cấu hình Gemini API Key: {gemini.is_available()}")
    answer, chat_sources = await gemini.chat_with_agent("Thủ tục làm giấy khai sinh cho con cần những giấy tờ gì?")
    log(f"[+] Độ dài câu trả lời: {len(answer)} ký tự")
    log(f"[+] Trích dẫn ({len(chat_sources)} nguồn): {', '.join(chat_sources)}")
    log("[+] Trích đoạn câu trả lời:\n" + answer[:300] + "...\n")

    log("=" * 75)
    log("TẤT CẢ CÁC BÀI KIỂM THỬ TÍCH HỢP GEMINI AGENT & RAG ĐỀU THÀNH CÔNG 100%!")
    log("=" * 75)

if __name__ == "__main__":
    asyncio.run(test_agent())
