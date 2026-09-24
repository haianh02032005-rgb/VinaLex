"""
VinaLex — Legal & Procedure Document Parser (Bộ Bóc Tách Cấu Trúc Pháp Lý)

Tuân thủ ARCHITECTURE.md Lớp 3 (Phân hệ RAG):
- Phân đoạn văn bản pháp luật theo cấu trúc chuẩn Việt Nam:
    Phần / Chương / Mục → Điều → Khoản → Điểm
- Phân đoạn thủ tục hành chính:
    Tổng quan & Điều kiện → Thành phần hồ sơ → Trình tự thực hiện
- Làm giàu metadata cho mỗi chunk để phục vụ Hybrid Retrieval & Citation.
"""

import re
import unicodedata
from typing import List, Dict, Any, Optional
from langchain.schema import Document


def strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để phục vụ so khớp không dấu."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


class LegalDocParser:
    """
    Parser chuyên biệt bóc tách văn bản quy phạm pháp luật Việt Nam (Luật, Nghị định, Thông tư, Quyết định).
    """

    # Regex nhận diện Chương
    RE_CHAPTER = re.compile(
        r"(?i)(?:^|\n)\s*(Chương\s+[IVXLCDM\d]+[^\n]*)\n*([^\n]*)",
        re.MULTILINE
    )

    # Regex nhận diện Điều: Điều 1., Điều 1:, Điều 1 - Tiêu đề
    RE_ARTICLE = re.compile(
        r"(?i)(?:^|\n)\s*(Điều\s+(\d+)[\.\:]?\s*([^\n]*))",
        re.MULTILINE
    )

    # Regex nhận diện Khoản: "1. ", "2. ", "Khoản 1. "
    RE_CLAUSE = re.compile(
        r"(?i)(?:^|\n)\s*((?:Khoản\s+)?(\d+)[\.\)]\s*([^\n]*))",
        re.MULTILINE
    )

    # Regex nhận diện Mục La Mã: I. MỤC ĐÍCH, II. NỘI DUNG
    RE_ROMAN_SECTION = re.compile(
        r"(?i)(?:^|\n)\s*([IVXLCDM]+\.\s+[^\n]+)",
        re.MULTILINE
    )

    @classmethod
    def parse_legal_document(cls, doc_data: Dict[str, Any]) -> List[Document]:
        """
        Bóc tách một văn bản pháp luật thành danh sách Document chunks theo cấu trúc Điều/Khoản.
        """
        content = (doc_data.get("content_text") or "").strip()
        if not content:
            # Fallback nếu không có content_text nhưng có summary
            summary = (doc_data.get("summary") or "").strip()
            if summary:
                content = summary
            else:
                return []

        doc_number = (doc_data.get("doc_number") or "").strip()
        title = (doc_data.get("title") or "").strip()
        doc_type = (doc_data.get("doc_type") or "Văn bản pháp luật").strip()
        agency = (doc_data.get("agency") or "").strip()
        issue_date = (doc_data.get("issue_date") or "").strip()
        effective_date = (doc_data.get("effective_date") or "").strip()
        signer = (doc_data.get("signer") or "").strip()
        category = (doc_data.get("category") or "").strip()
        original_url = (doc_data.get("original_url") or "").strip()
        slug = (doc_data.get("slug") or "").strip()

        base_metadata = {
            "source_type": "legal_doc",
            "doc_number": doc_number,
            "doc_type": doc_type,
            "title": title,
            "agency": agency,
            "issue_date": issue_date,
            "effective_date": effective_date,
            "signer": signer,
            "category": category,
            "url": original_url,
            "slug": slug,
        }

        # Kiểm tra văn bản có phân chia theo "Điều" hay không
        article_matches = list(cls.RE_ARTICLE.finditer(content))

        if not article_matches:
            # Văn bản không có "Điều" (Chỉ thị, Thông báo, Kế hoạch, Quyết định cá biệt)
            return cls._parse_non_article_document(content, base_metadata)

        # Văn bản có "Điều" -> Phân tách theo Điều và Chương
        chunks: List[Document] = []

        # 1. Phần mở đầu (Preamble / Căn cứ ban hành) trước Điều 1
        first_article_start = article_matches[0].start()
        if first_article_start > 150:
            preamble_text = content[:first_article_start].strip()
            # Giới hạn preamble không quá 1000 ký tự
            if len(preamble_text) > 1000:
                preamble_text = preamble_text[:1000] + "..."
            
            meta = dict(base_metadata)
            meta.update({
                "chapter": "Căn cứ ban hành & Thẩm quyền",
                "article": "Căn cứ pháp lý",
                "article_number": 0,
                "article_title": "Căn cứ ban hành",
                "source": f"{doc_type} {doc_number}: Căn cứ ban hành",
            })
            header_prefix = f"Văn bản: {doc_type} {doc_number} - {title}\nCơ quan ban hành: {agency} | Ngày ban hành: {issue_date}\n\n[CĂN CỨ PHÁP LÝ & MỤC ĐÍCH]:\n"
            chunks.append(Document(page_content=header_prefix + preamble_text, metadata=meta))

        # 2. Quét các Chương và vị trí bắt đầu
        chapter_matches = list(cls.RE_CHAPTER.finditer(content))

        def get_current_chapter(pos: int) -> str:
            current_ch = ""
            for cm in chapter_matches:
                if cm.start() <= pos:
                    ch_line1 = cm.group(1).strip()
                    ch_line2 = cm.group(2).strip() if cm.group(2) else ""
                    current_ch = f"{ch_line1}: {ch_line2}".strip(": ")
                else:
                    break
            return current_ch

        # 3. Duyệt từng Điều
        for i, match in enumerate(article_matches):
            art_start = match.start()
            art_end = article_matches[i + 1].start() if i + 1 < len(article_matches) else len(content)

            full_art_header = match.group(1).strip()
            art_num_str = match.group(2).strip()
            art_title = match.group(3).strip() if match.group(3) else ""
            try:
                art_num = int(art_num_str)
            except ValueError:
                art_num = i + 1

            art_text = content[art_start:art_end].strip()
            current_chapter = get_current_chapter(art_start)

            # Metadata riêng cho Điều này
            meta = dict(base_metadata)
            meta.update({
                "chapter": current_chapter,
                "article": f"Điều {art_num}",
                "article_number": art_num,
                "article_title": art_title,
                "source": f"{doc_type} {doc_number} - Điều {art_num}: {art_title}".strip(": "),
            })

            # Tiền tố ngữ cảnh để embeddings và LLM luôn biết điều luật thuộc văn bản nào
            context_header = (
                f"Văn bản: {doc_type} {doc_number} - {title}\n"
                f"Cơ quan ban hành: {agency} | Ban hành: {issue_date}\n"
                f"{f'Chương: {current_chapter}' if current_chapter else ''}\n"
                f"Vị trí: Điều {art_num}. {art_title}\n\n"
            ).replace("\n\n\n", "\n\n")

            # Nếu Điều quá dài (> 1.800 ký tự) -> Tách nhỏ theo Khoản
            if len(art_text) > 1800:
                sub_chunks = cls._split_article_by_clauses(
                    art_text, full_art_header, context_header, meta
                )
                chunks.extend(sub_chunks)
            else:
                chunks.append(Document(
                    page_content=context_header + art_text,
                    metadata=meta
                ))

        return chunks

    @classmethod
    def _split_article_by_clauses(
        cls,
        art_text: str,
        art_header: str,
        context_header: str,
        base_meta: Dict[str, Any],
        min_chunk_chars: int = 500,
        max_chunk_chars: int = 1500
    ) -> List[Document]:
        """Tách Điều dài thành các nhóm Khoản con có kích thước hợp lý (500 - 1500 chars)."""
        clause_matches = list(cls.RE_CLAUSE.finditer(art_text))
        if not clause_matches or len(clause_matches) <= 1:
            # Tách thô theo đoạn nếu không nhận diện được Khoản
            return cls._chunk_by_size(context_header + art_text, base_meta, max_chars=max_chunk_chars)

        chunks: List[Document] = []
        current_clauses: List[str] = []
        current_len = 0
        first_clause_num = ""
        last_clause_num = ""

        for j, c_match in enumerate(clause_matches):
            c_start = c_match.start()
            c_end = clause_matches[j + 1].start() if j + 1 < len(clause_matches) else len(art_text)
            c_num = c_match.group(2).strip()
            c_text = art_text[c_start:c_end].strip()

            if not first_clause_num:
                first_clause_num = c_num
            last_clause_num = c_num

            current_clauses.append(c_text)
            current_len += len(c_text)

            if current_len >= min_chunk_chars or j == len(clause_matches) - 1:
                clause_label = (
                    f"Khoản {first_clause_num}"
                    if first_clause_num == last_clause_num
                    else f"Khoản {first_clause_num} - {last_clause_num}"
                )
                meta = dict(base_meta)
                meta["clause"] = clause_label
                meta["source"] = f"{base_meta.get('source', '')} ({clause_label})"

                header = f"{context_header}[{art_header} - {clause_label}]:\n"
                chunks.append(Document(
                    page_content=header + "\n\n".join(current_clauses),
                    metadata=meta
                ))
                current_clauses = []
                current_len = 0
                first_clause_num = ""
                last_clause_num = ""

        return chunks


    @classmethod
    def _parse_non_article_document(cls, content: str, base_metadata: Dict[str, Any]) -> List[Document]:
        """Bóc tách văn bản không có Điều theo Mục La Mã hoặc phân đoạn kích thước vừa phải."""
        sections = cls.RE_ROMAN_SECTION.split(content)
        chunks: List[Document] = []

        doc_prefix = (
            f"Văn bản: {base_metadata.get('doc_type', '')} {base_metadata.get('doc_number', '')} - {base_metadata.get('title', '')}\n"
            f"Cơ quan: {base_metadata.get('agency', '')} | Ban hành: {base_metadata.get('issue_date', '')}\n\n"
        )

        if len(sections) > 1:
            # Có phân mục La Mã (I., II., III...)
            for idx in range(1, len(sections), 2):
                sec_title = sections[idx].strip()
                sec_body = sections[idx + 1].strip() if idx + 1 < len(sections) else ""
                combined = f"[{sec_title}]\n{sec_body}"

                meta = dict(base_metadata)
                meta.update({
                    "chapter": sec_title,
                    "article": sec_title[:40],
                    "source": f"{base_metadata.get('doc_number', '')} - {sec_title[:40]}",
                })

                if len(combined) > 1600:
                    chunks.extend(cls._chunk_by_size(doc_prefix + combined, meta, max_chars=1200))
                else:
                    chunks.append(Document(page_content=doc_prefix + combined, metadata=meta))
        else:
            # Phân tách theo đoạn văn bản kích thước tiêu chuẩn ~1000 ký tự
            chunks = cls._chunk_by_size(doc_prefix + content, base_metadata, max_chars=1200)

        return chunks

    @classmethod
    def _chunk_by_size(cls, text: str, metadata: Dict[str, Any], max_chars: int = 1200) -> List[Document]:
        """Chia văn bản theo khối kích thước có overlap."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: List[Document] = []
        current_chunk: List[str] = []
        current_len = 0

        for para in paragraphs:
            if current_len + len(para) > max_chars and current_chunk:
                chunk_str = "\n\n".join(current_chunk)
                meta = dict(metadata)
                chunks.append(Document(page_content=chunk_str, metadata=meta))
                # Giữ lại đoạn cuối làm overlap
                current_chunk = [current_chunk[-1], para] if len(current_chunk) > 1 else [para]
                current_len = sum(len(p) for p in current_chunk)
            else:
                current_chunk.append(para)
                current_len += len(para)

        if current_chunk:
            chunk_str = "\n\n".join(current_chunk)
            chunks.append(Document(page_content=chunk_str, metadata=dict(metadata)))

        return chunks


class ProcedureParser:
    """
    Parser chuyên biệt bóc tách thủ tục hành chính công (Dịch vụ công).
    Chia 1 thủ tục thành 3 chunks chuyên biệt:
      1. Tổng quan, đối tượng & điều kiện
      2. Thành phần hồ sơ yêu cầu
      3. Trình tự & các bước thực hiện
    """

    @classmethod
    def parse_procedure(cls, proc_data: Dict[str, Any]) -> List[Document]:
        """
        Bóc tách thủ tục hành chính thành các Document chunks có ngữ cảnh sâu.
        """
        title = (proc_data.get("title") or "").strip()
        if not title:
            return []

        slug = (proc_data.get("slug") or proc_data.get("id") or "").strip()
        agency = (proc_data.get("agency") or proc_data.get("authority") or "Cơ quan hành chính nhà nước").strip()
        category = (proc_data.get("category") or "").strip()
        category_slug = (proc_data.get("category_slug") or "").strip()
        level = (proc_data.get("level") or "Cơ sở").strip()
        processing_time = (proc_data.get("processing_time") or "Theo quy định").strip()
        fee = (proc_data.get("fee") or "Miễn phí").strip()
        desc = (proc_data.get("description") or "").strip()
        documents = proc_data.get("documents") or []
        steps = proc_data.get("steps") or []

        base_metadata = {
            "source_type": "procedure",
            "slug": slug,
            "title": title,
            "agency": agency,
            "category": category,
            "category_slug": category_slug,
            "level": level,
            "processing_time": processing_time,
            "fee": fee,
            "url": f"/thu-tuc/{slug}",
        }

        chunks: List[Document] = []

        # ── Chunk 1: Tổng quan, Thẩm quyền, Thời gian & Lệ phí ──
        overview_text = (
            f"Thủ tục hành chính: {title}\n"
            f"Lĩnh vực: {category} | Cấp thực hiện: {level}\n"
            f"Cơ quan giải quyết: {agency}\n"
            f"Thời hạn giải quyết: {processing_time}\n"
            f"Phí, lệ phí: {fee}\n\n"
            f"[MÔ TẢ & YÊU CẦU ĐIỀU KIỆN]:\n{desc if desc else 'Thực hiện theo quy định của pháp luật chuyên ngành hiện hành.'}"
        )
        meta_overview = dict(base_metadata)
        meta_overview.update({
            "section": "Tổng quan & Điều kiện",
            "source": f"Thủ tục: {title} (Tổng quan)",
        })
        chunks.append(Document(page_content=overview_text, metadata=meta_overview))

        # ── Chunk 2: Thành phần hồ sơ ──
        if documents:
            doc_lines = [f"Thủ tục hành chính: {title}\nCơ quan tiếp nhận: {agency}\n\n[THÀNH PHẦN HỒ SƠ YÊU CẦU]:"]
            for idx, d in enumerate(documents, 1):
                doc_lines.append(f"{idx}. {d}")
            
            meta_docs = dict(base_metadata)
            meta_docs.update({
                "section": "Thành phần hồ sơ",
                "source": f"Thủ tục: {title} (Hồ sơ cần nộp)",
            })
            chunks.append(Document(page_content="\n".join(doc_lines), metadata=meta_docs))

        # ── Chunk 3: Trình tự các bước thực hiện ──
        if steps:
            step_lines = [f"Thủ tục hành chính: {title}\nCơ quan thực hiện: {agency}\n\n[TRÌNH TỰ THỰC HIỆN]:"]
            for s in steps:
                if isinstance(s, dict):
                    idx = s.get("index", "")
                    s_title = s.get("title", "")
                    s_desc = s.get("description", "")
                    step_lines.append(f"+ Bước {idx}: {s_title} — {s_desc}")
                elif isinstance(s, str):
                    step_lines.append(f"+ {s}")

            meta_steps = dict(base_metadata)
            meta_steps.update({
                "section": "Trình tự thực hiện",
                "source": f"Thủ tục: {title} (Trình tự giải quyết)",
            })
            chunks.append(Document(page_content="\n".join(step_lines), metadata=meta_steps))

        return chunks
