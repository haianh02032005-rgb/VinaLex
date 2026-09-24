import os, sys, re, unicodedata, json
from typing import List, Tuple

sys.stdout.reconfigure(encoding="utf-8")

def _strip_accents(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()

STOP_WORDS = {
    "về", "của", "tại", "cho", "và", "hoặc", "ở", "bị", "làm", "được", "có", "là", 
    "tôi", "muốn", "cần", "hỏi", "thủ", "tục", "quy", "định", "những", "các", "một", 
    "trong", "đến", "khi", "nào", "mới", "nhất", "lại", "cấp"
}

SYNONYMS = [
    (["so do", "so hong", "dat dai", "quyen su dung dat", "gcnqsdd"], ["so do", "so hong", "dat dai", "quyen su dung dat", "gcnqsdd", "dia chinh", "nha o", "dat"]),
    (["khai sinh", "giay khai sinh"], ["khai sinh", "chung sinh", "ho tich"]),
    (["can cuoc", "cccd", "cmnd", "dinh danh"], ["can cuoc", "cccd", "cmnd", "dinh danh", "vneid"]),
    (["luong", "tien luong", "luong toi thieu"], ["luong", "tien luong", "luong toi thieu", "lao dong", "nguoi lao dong"]),
    (["bao hiem", "bhxh", "bhyt", "bao hiem xa hoi"], ["bao hiem", "bhxh", "bhyt", "bao hiem xa hoi", "bao hiem y te", "that nghiep"]),
    (["ket hon", "hon nhan", "ly hon"], ["ket hon", "hon nhan", "ly hon", "tinh trang hon nhan"]),
    (["bang lai", "gplx", "lai xe"], ["bang lai", "lai xe", "gplx", "giay phep lai xe"]),
    (["doanh nghiep", "thanh lap cong ty", "kinh doanh"], ["doanh nghiep", "thanh lap", "cong ty", "kinh doanh"]),
]

with open("data/crawled_procedures.json", "r", encoding="utf-8") as f:
    tvpl_procs = json.load(f)
with open("data/dvc_procedures.json", "r", encoding="utf-8") as f:
    dvc_procs = json.load(f)
with open("data/crawled_legal_docs.json", "r", encoding="utf-8") as f:
    docs = json.load(f)

all_procs = dvc_procs + tvpl_procs

def score_item(q: str, title: str, category: str, text: str, doc_num: str = "") -> float:
    q_lower = q.lower().strip()
    q_clean = _strip_accents(q_lower)
    title_lower = title.lower()
    title_clean = _strip_accents(title_lower)
    cat_lower = category.lower()
    cat_clean = _strip_accents(cat_lower)
    text_lower = text.lower()
    text_clean = _strip_accents(text_lower)
    
    score = 0.0
    if doc_num and doc_num.lower() in q_lower:
        score += 80.0
        
    if q_lower in title_lower:
        score += 100.0
    elif q_clean in title_clean:
        score += 80.0
        
    if q_lower in text_lower:
        score += 30.0
    elif q_clean in text_clean:
        score += 20.0

    raw_tokens = [t.lower().strip() for t in re.split(r"[\s,\.\?\!\:\;]+", q) if len(t.strip()) > 1]
    meaningful_tokens = [t for t in raw_tokens if t not in STOP_WORDS]
    tokens = meaningful_tokens if meaningful_tokens else raw_tokens

    for t in tokens:
        t_clean = _strip_accents(t)
        if t in title_lower:
            score += 18.0
        elif t_clean in title_clean:
            score += 14.0
            
        if t in cat_lower:
            score += 8.0
        elif t_clean in cat_clean:
            score += 6.0
            
        if t in text_lower[:1500]:
            score += 2.0
            
    for q_pats, t_pats in SYNONYMS:
        if any(qp in q_clean for qp in q_pats):
            if any(tp in title_clean for tp in t_pats):
                score += 50.0
            elif any(tp in text_clean for tp in t_pats):
                score += 25.0
                
    return score

queries = [
    "làm lại sổ đỏ bị mất hoặc cấp giấy chứng nhận đất đai",
    "thủ tục đăng ký khai sinh cho con mới sinh",
    "quy định lương tối thiểu và bảo hiểm xã hội"
]

print("=== TEST ADVANCED SEARCH RANKING ===")
for q in queries:
    print(f"\n[QUERY] \"{q}\"")
    scored = []
    for p in all_procs:
        sc = score_item(q, p.get("title", ""), p.get("category", ""), p.get("description", ""))
        if sc > 0:
            scored.append((sc, "Thủ tục", p.get("title", ""), p.get("agency", "")))
    for d in docs:
        sc = score_item(q, d.get("title", ""), d.get("category", ""), d.get("content_text", "")[:2000], d.get("doc_number", ""))
        if sc > 0:
            scored.append((sc, "Văn bản", f"{d.get('doc_number')} - {d.get('title')}", d.get("agency", "")))
            
    scored.sort(key=lambda x: x[0], reverse=True)
    print(f"Top 3 results:")
    for sc, kind, title, agency in scored[:3]:
        print(f"  • [{kind}] (Score: {sc:.1f}) {title[:75]} | CQ: {agency}")
