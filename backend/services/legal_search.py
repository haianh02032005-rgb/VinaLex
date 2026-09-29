"""Tiện ích chuẩn hóa và mở rộng truy vấn pháp lý tiếng Việt.

Module này là nguồn dùng chung cho tìm kiếm thủ tục, văn bản và RAG để tránh
mỗi API hiểu từ khóa theo một cách khác nhau.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Optional, Sequence, Tuple


STOP_WORDS: FrozenSet[str] = frozenset({
    "ve", "cua", "tai", "cho", "va", "hoac", "o", "bi", "lam", "duoc",
    "co", "la", "toi", "muon", "can", "hoi", "nhung", "cac", "mot",
    "trong", "den", "khi", "nao", "moi", "nhat", "lai", "theo", "nhu",
    "the", "thu", "tuc", "quy", "dinh", "van", "ban",
})

# Mỗi nhóm biểu diễn một khái niệm. Chỉ mở rộng khi truy vấn chứa nguyên cụm,
# không dùng phép ``in`` trên từ con để tránh các kết quả giả.
LEGAL_CONCEPTS: Tuple[Tuple[str, ...], ...] = (
    ("so do", "so hong", "gcnqsdd", "giay chung nhan quyen su dung dat"),
    ("dat dai", "nha dat", "dia chinh", "thua dat", "bat dong san"),
    ("khai sinh", "giay khai sinh", "chung sinh", "dang ky khai sinh"),
    ("khai tu", "giay khai tu", "dang ky khai tu"),
    ("can cuoc", "cccd", "cmnd", "chung minh nhan dan", "the can cuoc"),
    ("dinh danh dien tu", "vneid"),
    ("bao hiem xa hoi", "bhxh", "so bhxh", "che do bhxh"),
    ("bao hiem y te", "bhyt"),
    ("giay phep lai xe", "gplx", "bang lai", "bang lai xe", "lai xe"),
    ("dang ky doanh nghiep", "thanh lap cong ty", "dang ky kinh doanh"),
    ("tam tru", "dang ky tam tru"),
    ("thuong tru", "dang ky thuong tru", "ho khau", "so ho khau"),
    ("thue thu nhap ca nhan", "thue tncn", "quyet toan thue tncn"),
    ("ly lich tu phap", "phieu ly lich tu phap"),
    ("giay phep xay dung", "xin phep xay dung"),
)


def normalize_text(value: object) -> str:
    """Chuẩn hóa Unicode, bỏ dấu và dấu câu nhưng giữ ``/`` và ``-`` của số hiệu."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("đ", "d").replace("Đ", "D").lower()
    text = "".join(
        char for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    text = re.sub(r"[^a-z0-9/_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = normalize_text(text)
    normalized_phrase = normalize_text(phrase)
    if not normalized_text or not normalized_phrase:
        return False
    return bool(re.search(rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)", normalized_text))


def extract_document_numbers(query: str) -> List[str]:
    """Lấy số hiệu như 13/2023/NĐ-CP và không nhầm số Điều/Khoản là số hiệu."""
    normalized = normalize_text(query)
    return list(dict.fromkeys(re.findall(r"\b\d{1,5}/\d{4}/[a-z0-9-]+\b", normalized)))


@dataclass(frozen=True)
class SearchQuery:
    original: str
    normalized: str
    tokens: Tuple[str, ...]
    phrases: Tuple[str, ...]
    expanded_terms: Tuple[str, ...]
    article: Optional[int]
    clause: Optional[int]
    document_numbers: Tuple[str, ...]


def analyze_query(query: str, stop_words: Optional[Iterable[str]] = None) -> SearchQuery:
    normalized = normalize_text(query)
    ignored = STOP_WORDS | frozenset(normalize_text(w) for w in (stop_words or ()))
    tokens = tuple(
        token for token in re.findall(r"[a-z0-9/_-]+", normalized)
        if len(token) > 1 and token not in ignored
    )

    matched_groups: List[Sequence[str]] = []
    matched_phrases: List[str] = []
    for group in LEGAL_CONCEPTS:
        hits = [term for term in group if contains_phrase(normalized, term)]
        if hits:
            matched_groups.append(group)
            matched_phrases.extend(hits)

    expanded = list(tokens)
    for group in matched_groups:
        expanded.extend(group)

    article_match = re.search(r"\b(?:dieu)\s+(\d+)\b", normalized)
    clause_match = re.search(r"\b(?:khoan)\s+(\d+)\b", normalized)
    return SearchQuery(
        original=query,
        normalized=normalized,
        tokens=tuple(dict.fromkeys(tokens)),
        phrases=tuple(dict.fromkeys(matched_phrases)),
        expanded_terms=tuple(dict.fromkeys(normalize_text(term) for term in expanded if term)),
        article=int(article_match.group(1)) if article_match else None,
        clause=int(clause_match.group(1)) if clause_match else None,
        document_numbers=tuple(extract_document_numbers(query)),
    )


def best_concept_match(query: SearchQuery, fields: Iterable[str]) -> bool:
    """Kiểm tra ít nhất một đồng nghĩa cùng khái niệm xuất hiện trong dữ liệu."""
    haystack = " ".join(normalize_text(field) for field in fields if field)
    if not query.phrases:
        return False
    for group in LEGAL_CONCEPTS:
        if any(term in query.phrases for term in group):
            if any(contains_phrase(haystack, term) for term in group):
                return True
    return False
