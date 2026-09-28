"""
VinaLex — API Routes: Tra Cứu Địa Điểm & Chỉ Đường Cơ Quan Hành Chính
Prefix: /api/v1/locations (Đăng ký trong main.py)

Tuân thủ:
- ARCHITECTURE.md Lớp 2 (FastAPI Async/Await Gateway)
- Nghị định 13/2023/NĐ-CP (Không lưu toạ độ người dùng)
- Độc lập 100% với các router khác
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Path

from backend.services.agency_location_service import agency_location_service

router = APIRouter()


@router.get("/divisions", summary="Lấy danh mục Đơn vị Hành chính theo phân cấp (Tỉnh / Huyện / Xã)")
async def get_divisions(
    level: Optional[str] = Query(None, description="Cấp hành chính: province | district | ward"),
    parent_code: Optional[str] = Query(None, description="Mã đơn vị hành chính cấp cha"),
):
    """Trả về danh mục đơn vị hành chính chuẩn hóa quốc gia mới nhất."""
    items = agency_location_service.get_divisions(level=level, parent_code=parent_code)
    return {"total": len(items), "items": items}


@router.get("/mergers/resolve", summary="Phân giải biến động sáp nhập đơn vị hành chính (2023 - 2025)")
async def resolve_merger(
    query_name: str = Query(..., description="Tên xã, phường, thị trấn hoặc quận huyện cũ cần tra cứu"),
    province_name: Optional[str] = Query(None, description="Tên tỉnh/thành phố để lọc chính xác"),
    district_name: Optional[str] = Query(None, description="Tên quận/huyện cũ"),
):
    """
    Tra cứu thông tin sáp nhập nếu tên người dùng tra cứu là tên cũ.
    Giúp người dân cầm CCCD cũ hoặc địa chỉ cũ tìm đúng trụ sở Một cửa mới.
    """
    merger = agency_location_service.resolve_merger(
        query_name=query_name,
        province_name=province_name,
        district_name=district_name,
    )
    if not merger:
        return {
            "found": False,
            "message": f"Không phát hiện biến động sáp nhập cho địa danh '{query_name}'. Địa danh này có thể đang là đơn vị hành chính hiện hữu.",
            "data": None,
        }
    return {
        "found": True,
        "message": f"Địa bàn '{merger['old_unit_name']}' đã được sáp nhập vào '{merger['new_unit_name']}' theo Nghị quyết {merger['resolution_code']}.",
        "data": merger,
    }


@router.get("/agencies", summary="Tra cứu danh sách cơ quan hành chính theo phân cấp hoặc từ khoá")
async def list_agencies(
    keyword: Optional[str] = Query(None, description="Từ khoá tìm kiếm tên cơ quan, địa chỉ, phường xã (hỗ trợ không dấu)"),
    province_code: Optional[str] = Query(None, description="Mã tỉnh/thành phố"),
    district_code: Optional[str] = Query(None, description="Mã quận/huyện"),
    ward_code: Optional[str] = Query(None, description="Mã phường/xã"),
    agency_type: Optional[str] = Query(None, description="Loại cơ quan: one_stop_ward, one_stop_district, land_registry, police, tax, one_stop_province"),
    level: Optional[str] = Query(None, description="Cấp hành chính: ward | district | province | central"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng bản ghi tối đa"),
    offset: int = Query(0, ge=0, description="Vị trí bắt đầu"),
):
    """Tra cứu các cơ quan tiếp nhận giải quyết thủ tục hành chính."""
    result = agency_location_service.search_agencies(
        keyword=keyword,
        province_code=province_code,
        district_code=district_code,
        ward_code=ward_code,
        agency_type=agency_type,
        level=level,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/agencies/nearby", summary="Tìm kiếm cơ quan hành chính gần toạ độ GPS của người dùng")
async def get_nearby_agencies(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Vĩ độ hiện tại của người dùng"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Kinh độ hiện tại của người dùng"),
    radius_km: float = Query(10.0, ge=0.5, le=50.0, description="Bán kính tìm kiếm quanh vị trí (km)"),
    limit: int = Query(20, ge=1, le=50, description="Số lượng cơ quan tối đa trả về"),
    agency_type: Optional[str] = Query(None, description="Lọc theo loại cơ quan"),
    province_code: Optional[str] = Query(None, description="Lọc theo mã tỉnh/thành"),
):
    """
    Tính cự ly thời gian thực từ vị trí của người dân đến các trụ sở cơ quan hành chính,
    sắp xếp tăng dần theo khoảng cách và trả kèm liên kết dẫn đường Google Maps.
    """
    result = agency_location_service.find_nearby_agencies(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        limit=limit,
        agency_type=agency_type,
        province_code=province_code,
    )
    return result


@router.get("/agencies/{agency_id}", summary="Lấy chi tiết trụ sở cơ quan hành chính")
async def get_agency_detail(
    agency_id: int = Path(..., description="ID cơ quan hành chính"),
):
    """Chi tiết thông tin liên hệ, địa chỉ, giờ làm việc và các lĩnh vực phục vụ."""
    detail = agency_location_service.get_agency_detail(agency_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy cơ quan hành chính")
    return detail


@router.get("/directions-url", summary="Tạo liên kết chỉ đường Google Maps Universal URL")
async def get_directions_url(
    agency_id: int = Query(..., description="ID cơ quan hành chính đích đến"),
    origin_lat: Optional[float] = Query(None, description="Vĩ độ xuất phát của người dùng"),
    origin_lng: Optional[float] = Query(None, description="Kinh độ xuất phát của người dùng"),
    travel_mode: str = Query("driving", description="Phương tiện: driving | walking | transit"),
):
    """
    Sinh đường dẫn Universal Directions URL chuẩn của Google Maps.
    Khi mở trên Mobile sẽ tự bật App Google Maps, trên Desktop sẽ mở tab mới có lộ trình.
    """
    result = agency_location_service.generate_directions_url(
        agency_id=agency_id,
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        travel_mode=travel_mode,
    )
    if "error" in result and result["error"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/stats", summary="Thống kê CSDL Địa điểm & Cơ quan hành chính")
async def get_stats():
    """Xem số lượng tỉnh thành, quận huyện, xã phường và trụ sở cơ quan trong CSDL."""
    return agency_location_service.get_statistics()
