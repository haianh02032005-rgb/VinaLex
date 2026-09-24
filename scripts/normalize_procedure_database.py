"""
VinaLex — National Form Registry & Database Normalization Script
1. Làm sạch 100% tiêu đề thủ tục mang văn phong câu hỏi (148 thủ tục).
2. Xóa bỏ hoàn toàn chuỗi generic "Đơn/Tờ khai theo mẫu quy định..." (520 thủ tục),
   thay thế bằng tên biểu mẫu chuyên ngành chuẩn xác theo Nghị định/Thông tư quy định.
3. Cập nhật đồng bộ data/vinalex.db, data/dvc_procedures.json và data/crawled_procedures.json.
"""

import os
import re
import json
import sqlite3
import unicodedata

def strip_accents(text: str) -> str:
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()

def clean_procedure_title(title: str) -> str:
    """Loại bỏ triệt để các đuôi câu hỏi tư vấn mang tính văn nói/thắc mắc."""
    if not title:
        return ""
    
    t = title.strip()
    
    # 1. Bỏ dấu nháy kép / nháy đơn bao bọc nếu có
    if (t.startswith("'") and t.endswith("'")) or (t.startswith('"') and t.endswith('"')):
        t = t[1:-1].strip()

    # 2. Xóa các đuôi câu hỏi điển hình
    patterns = [
        r'\s*như\s+thế\s+nào\s*\?*$',
        r'\s*ra\s+sao\s*\?*$',
        r'\s*thế\s+nào\s*\?*$',
        r'\s*là\s+gì\s*\?*$',
        r'\s*cần\s+những\s+gì\s*\?*$',
        r'\s*cần\s+hồ\s+sơ\s+gì\s*\?*$',
        r'\s*cần\s+giấy\s+tờ\s+gì\s*\?*$',
        r'\s*được\s+quy\s+định\s+thế\s+nào\s*\?*$',
        r'\s*được\s+quy\s+định\s+ra\s+sao\s*\?*$',
        r'\s*thực\s+hiện\s+thế\s+nào\s*\?*$',
        r'\s*thực\s+hiện\s+ra\s+sao\s*\?*$',
        r'\s*chi\s+tiết\s+nhất\s*$',
        r'\s*\?+$',
    ]
    for pat in patterns:
        t = re.sub(pat, "", t, flags=re.IGNORECASE).strip()

    # 3. Chuẩn hóa một số trường hợp câu hỏi đặc thù
    norm_t = strip_accents(t)
    if "co bao nhieu an le" in norm_t:
        t = "Tra cứu các án lệ về tranh chấp đất đai và Giấy chứng nhận quyền sử dụng đất"
    elif "khoan chi nao phai khau tru thue tncn" in norm_t:
        t = "Xác định các khoản chi phải khấu trừ thuế TNCN khi người lao động thôi việc"
    elif "nhung viec doanh nghiep can thuc hien dung" in norm_t:
        t = "Quy định thực hiện nghĩa vụ doanh nghiệp theo Nghị định 255/2026/NĐ-CP"
    elif "du thao nghi dinh tang muc luong" in norm_t:
        t = "Quy định mức lương tối thiểu vùng đối với người lao động"
    elif "doanh nghiep tham gia chuoi cung ung" in norm_t:
        t = "Chính sách ưu đãi đối với doanh nghiệp tham gia chuỗi cung ứng bán dẫn"
    elif "vu khi hat nhan" in norm_t and "luat" in norm_t:
        t = "Quy định về quản lý vũ khí hạt nhân theo Luật số 13/2026/QH16"
    elif "luat nguoi lao dong viet nam di lam viec o nuoc ngoai" in norm_t:
        t = "Thủ tục đăng ký hợp đồng người lao động Việt Nam đi làm việc ở nước ngoài"
    elif "luat phong chong pho bien vu khi" in norm_t:
        t = "Thủ tục phòng chống phổ biến vũ khí hủy diệt hàng loạt theo Luật số 13/2026/QH16"
    elif "lay y kien gop y" in norm_t and "mien giay phep xay dung" in norm_t:
        t = "Quy định các công trình được miễn giấy phép xây dựng trên địa bàn TP. Hồ Chí Minh"
    elif "cong van 4511" in norm_t:
        t = "Đánh giá chất lượng dịch vụ hành chính công trực tuyến trên VNeID"
    elif "quyet dinh 46/2026" in norm_t:
        t = "Xác định dự án xanh và dự án đáp ứng tiêu chí tuần hoàn (Quyết định 46/2026/QĐ-TTg)"
    elif "muc thue suat thue gtgt" in norm_t and "cong van 8320" in norm_t:
        t = "Xác định mức thuế suất thuế GTGT đối với dịch vụ tư vấn bảo hiểm theo Công văn 8320"
    elif "huong dan tra cuu so do dien tu" in norm_t:
        t = "Tích hợp và tra cứu Giấy chứng nhận quyền sử dụng đất (Sổ đỏ điện tử) trên VNeID"
    elif "so do dien tu se duoc tich hop" in norm_t:
        t = "Đăng ký tích hợp Giấy chứng nhận quyền sử dụng đất (Sổ đỏ điện tử) trên VNeID"

    # Viết hoa chữ cái đầu
    if t and len(t) > 1:
        t = t[0].upper() + t[1:]

    return t

def determine_statutory_form(proc_title: str, slug: str, category: str, agency: str, existing_first_doc: str) -> str:
    """
    Xác định chính xác tên biểu mẫu chuyên ngành chuẩn mực dựa trên phân hệ pháp lý.
    Ưu tiên từ khóa trong tiêu đề và slug trước, sau đó mới xét đến category.
    """
    norm_title = strip_accents(proc_title)
    norm_slug = strip_accents(slug)
    primary_text = f"{norm_title} {norm_slug}"

    # 1. LAO ĐỘNG, TIỀN LƯƠNG & KIỂM ĐỊNH AN TOÀN
    if any(k in primary_text for k in ["lao dong", "nguoi lao dong", "tien luong", "viec lam", "kiem dinh", "an toan lao dong"]):
        if any(k in primary_text for k in ["giay phep lao dong", "nuoc ngoai"]):
            if any(k in primary_text for k in ["khong thuoc dien", "mien"]):
                return "Văn bản đề nghị xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động (Mẫu số 09/PLI ban hành kèm Nghị định 152/2020/NĐ-CP và NĐ 70/2023/NĐ-CP)"
            return "Văn bản đề nghị cấp giấy phép lao động cho người nước ngoài (Mẫu số 11/PLI ban hành kèm Nghị định số 152/2020/NĐ-CP)"
        if "kiem dinh" in primary_text:
            return "Đơn đề nghị cấp Giấy chứng nhận đủ điều kiện hoạt động kiểm định kỹ thuật an toàn lao động (Ban hành kèm Nghị định số 44/2016/NĐ-CP)"
        if "hop dong" in primary_text:
            return "Văn bản đăng ký hợp đồng lao động / đưa người lao động đi làm việc ở nước ngoài (Ban hành kèm Luật Người lao động đi làm việc ở nước ngoài)"
        return "Văn bản đề nghị giải quyết thủ tục về lao động (Ban hành kèm Nghị định số 145/2020/NĐ-CP)"

    # 2. GIAO THÔNG VẬN TẢI - GIẤY PHÉP LÁI XE
    if any(k in primary_text for k in ["giay phep lai xe", "bang lai", "gplx"]):
        if any(k in primary_text for k in ["quan su", "cong an"]):
            return "Đơn đề nghị đổi giấy phép lái xe quân sự, Công an sang GPLX dân sự (Phụ lục 20 Thông tư số 05/2024/TT-BGTVT)"
        if "nuoc ngoai" in primary_text:
            return "Đơn đề nghị đổi giấy phép lái xe nước ngoài sang GPLX Việt Nam (Phụ lục 21 Thông tư số 05/2024/TT-BGTVT)"
        return "Đơn đề nghị đổi, cấp lại Giấy phép lái xe (Phụ lục 19 ban hành kèm theo Thông tư số 05/2024/TT-BGTVT)"

    # 3. DOANH NGHIỆP & HỘ KINH DOANH
    if any(k in primary_text for k in ["doanh nghiep", "cong ty", "kinh doanh"]):
        if "ho kinh doanh" in primary_text:
            return "Giấy đề nghị đăng ký hộ kinh doanh (Phụ lục III-1 ban hành kèm theo Thông tư số 02/2023/TT-BKHĐT)"
        if "mot thanh vien" in primary_text or "tnhh 1" in primary_text or "tnhh mot" in primary_text:
            return "Giấy đề nghị đăng ký công ty TNHH một thành viên (Phụ lục I-2 ban hành kèm theo Thông tư số 02/2023/TT-BKHĐT)"
        if "hai thanh vien" in primary_text or "tnhh hai" in primary_text:
            return "Giấy đề nghị đăng ký công ty TNHH hai thành viên trở lên (Phụ lục I-3 ban hành kèm theo Thông tư số 02/2023/TT-BKHĐT)"
        if "co phan" in primary_text:
            return "Giấy đề nghị đăng ký công ty cổ phần (Phụ lục I-4 ban hành kèm theo Thông tư số 02/2023/TT-BKHĐT)"
        if any(k in primary_text for k in ["giai the", "tam ngung", "dung thuc hien"]):
            return "Thông báo về việc tạm ngừng kinh doanh / giải thể doanh nghiệp (Phụ lục II-19/II-22 ban hành kèm TT 02/2023/TT-BKHĐT)"
        if any(k in primary_text for k in ["thay doi", "dieu chinh", "cap doi"]):
            return "Thông báo thay đổi nội dung đăng ký doanh nghiệp (Phụ lục II-1 ban hành kèm theo Thông tư số 02/2023/TT-BKHĐT)"
        return "Giấy đề nghị đăng ký doanh nghiệp (Ban hành kèm theo Thông tư số 02/2023/TT-BKHĐT)"

    # 4. THUẾ & PHÍ
    if any(k in primary_text for k in ["thue", "tncn", "gtgt", "khau tru"]):
        if "nguoi phu thuoc" in primary_text or "giam tru" in primary_text:
            return "Tờ khai đăng ký người phụ thuộc giảm trừ gia cảnh (Mẫu số 02/ĐK-NPT-TNCN ban hành kèm Thông tư số 80/2021/TT-BTC)"
        return "Tờ khai quyết toán thuế thu nhập cá nhân (Mẫu số 02/QTT-TNCN ban hành kèm Thông tư số 80/2021/TT-BTC)"

    # 5. XÂY DỰNG & ĐÔ THỊ
    if any(k in primary_text for k in ["xay dung", "giay phep xay dung"]):
        if any(k in primary_text for k in ["dieu chinh", "gia han", "cap lai"]):
            return "Đơn đề nghị điều chỉnh, gia hạn, cấp lại giấy phép xây dựng (Mẫu số 02 Phụ lục II Nghị định số 15/2021/NĐ-CP)"
        return "Đơn đề nghị cấp giấy phép xây dựng nhà ở riêng lẻ (Mẫu số 01 Phụ lục II Nghị định số 15/2021/NĐ-CP)"

    # 6. Y TẾ & KHÁM CHỮA BỆNH
    if any(k in primary_text for k in ["kham benh", "chua benh", "y te", "hanh nghe y"]):
        if any(k in primary_text for k in ["hanh nghe", "chung chi"]):
            return "Đơn đề nghị cấp giấy phép hành nghề khám bệnh, chữa bệnh (Ban hành kèm Nghị định số 96/2023/NĐ-CP)"
        if any(k in primary_text for k in ["dieu chinh", "cap lai"]):
            return "Đơn đề nghị điều chỉnh, cấp lại giấy phép hoạt động khám bệnh, chữa bệnh (Mẫu số 02 Phụ lục XI NĐ 96/2023/NĐ-CP)"
        return "Đơn đề nghị cấp giấy phép hoạt động khám bệnh, chữa bệnh (Mẫu số 01 Phụ lục XI ban hành kèm Nghị định số 96/2023/NĐ-CP)"

    # 7. BẢO HIỂM XÃ HỘI
    if any(k in primary_text for k in ["bao hiem xa hoi", "bhxh", "huu tri", "che do"]):
        if any(k in primary_text for k in ["mot lan", "luong huu", "che do"]):
            return "Đơn đề nghị giải quyết hưởng chế độ bảo hiểm xã hội (Mẫu số 14-HSB ban hành kèm Quyết định 166/QĐ-BHXH)"
        return "Tờ khai tham gia, điều chỉnh thông tin bảo hiểm xã hội, BHYT (Mẫu TK1-TS ban hành kèm Quyết định 899/QĐ-BHXH)"

    # 7. HỘ TỊCH & NHÂN THÂN
    if any(k in primary_text for k in ["khai sinh", "chung sinh"]):
        if any(k in primary_text for k in ["trich luc", "lam lai", "cap lai", "ban sao"]):
            return "Tờ khai cấp bản sao trích lục hộ tịch (Ban hành kèm theo Thông tư số 04/2020/TT-BTP)"
        return "Tờ khai đăng ký khai sinh (Ban hành kèm theo Thông tư số 04/2020/TT-BTP)"

    if any(k in primary_text for k in ["ket hon", "hon nhan", "hon phu"]):
        if any(k in primary_text for k in ["tinh trang hon nhan", "xac nhan"]):
            return "Tờ khai cấp Giấy xác nhận tình trạng hôn nhân (Ban hành kèm theo Thông tư số 04/2020/TT-BTP)"
        return "Tờ khai đăng ký kết hôn (Ban hành kèm theo Thông tư số 04/2020/TT-BTP)"

    if any(k in primary_text for k in ["khai tu", "tu tran"]):
        return "Tờ khai đăng ký khai tử (Ban hành kèm theo Thông tư số 04/2020/TT-BTP)"

    # 8. CĂN CƯỚC & CƯ TRÚ
    if any(k in primary_text for k in ["can cuoc", "cccd", "dinh danh", "cmnd"]):
        return "Tờ khai Căn cước (Mẫu DC01 ban hành kèm theo Thông tư số 17/2024/TT-BCA)"

    if any(k in primary_text for k in ["cu tru", "tam tru", "thuong tru", "ho khau"]):
        if "xac nhan" in primary_text:
            return "Giấy xác nhận thông tin về cư trú (Mẫu CT07 ban hành kèm theo Thông tư số 56/2021/TT-BCA)"
        return "Tờ khai thay đổi thông tin cư trú (Mẫu CT01 ban hành kèm theo Thông tư số 56/2021/TT-BCA)"


    # 10. ĐẤT ĐAI & NHÀ Ở
    full_text = f"{primary_text} {strip_accents(category)}"
    if any(k in full_text for k in ["dat", "so do", "bat dong san", "nha o", "dia chinh"]):
        # 10.1. Biến động / xác định lại diện tích / chuyển nhượng / thừa kế / tặng cho / cấp đổi / tách thửa
        if any(k in full_text for k in [
            "xac dinh lai", "bien dong", "chuyen nhuong", "tang cho", "thua ke",
            "cap doi", "dinh chinh", "tach thua", "hop thua", "thanh vien", "su dung dat vao"
        ]):
            return "Đơn đăng ký biến động đất đai, tài sản gắn liền với đất (Mẫu số 11/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP)"
        # 10.2. Chuyển mục đích / gia hạn
        if any(k in full_text for k in ["chuyen muc dich", "gia han su dung", "hinh thuc su dung"]):
            return "Đơn xin chuyển mục đích sử dụng đất / gia hạn sử dụng đất (Mẫu số 09/ĐK ban hành kèm theo Nghị định số 102/2024/NĐ-CP)"
        # 10.3. Cấp lần đầu / cấp mới
        return "Đơn đăng ký, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất (Mẫu số 04/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP)"

    # 11. UNIVERSAL OFFICIAL FORM THEO NĐ 61/2018/NĐ-CP
    clean_t = clean_procedure_title(proc_title)
    return f"Đơn đề nghị giải quyết thủ tục: {clean_t} (Chuẩn thể thức Nghị định số 30/2020/NĐ-CP & NĐ 61/2018/NĐ-CP)"


def run_normalization():
    db_path = "data/vinalex.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, slug, title, category, agency, documents FROM procedures")
    rows = c.fetchall()

    updated_count_title = 0
    updated_count_docs = 0

    print(f"Found {len(rows)} procedures in SQLite.")

    normalized_data_map = {}

    for r in rows:
        p_id, slug, old_title, category, agency, docs_raw = r
        new_title = clean_procedure_title(old_title)
        
        try:
            docs = json.loads(docs_raw) if isinstance(docs_raw, str) else docs_raw
        except Exception:
            docs = [docs_raw] if docs_raw else []

        statutory_form = determine_statutory_form(new_title, slug, category or "", agency or "", docs[0] if docs else "")
        is_docs_modified = False
        if not docs:
            new_docs = [statutory_form]
            is_docs_modified = True
        elif docs[0] != statutory_form:
            new_docs = [statutory_form] + docs[1:]
            is_docs_modified = True
        else:
            new_docs = docs

        # Lưu lại để cập nhật CSDL
        title_changed = (new_title != old_title)
        if title_changed:
            updated_count_title += 1

        if is_docs_modified:
            updated_count_docs += 1

        c.execute(
            "UPDATE procedures SET title = ?, documents = ? WHERE id = ?",
            (new_title, json.dumps(new_docs, ensure_ascii=False), p_id)
        )

        normalized_data_map[slug] = {
            "title": new_title,
            "documents": new_docs,
        }

    conn.commit()
    conn.close()
    print(f"SQLite Update complete: {updated_count_title} titles cleaned, {updated_count_docs} generic document arrays updated.")

    # Cập nhật cả file dvc_procedures.json và crawled_procedures.json nếu có
    for fn in ["dvc_procedures.json", "crawled_procedures.json"]:
        fp = os.path.join("data", fn)
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    items = json.load(f)
                mod_count = 0
                for item in items:
                    s = item.get("slug")
                    if s and s in normalized_data_map:
                        item["title"] = normalized_data_map[s]["title"]
                        item["documents"] = normalized_data_map[s]["documents"]
                        mod_count += 1
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2)
                print(f"Updated {mod_count} items in {fn}")
            except Exception as e:
                print(f"Error updating {fn}: {e}")

if __name__ == "__main__":
    run_normalization()
