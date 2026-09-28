"""
VinaLex — Agency Location & Navigation Service
Cung cấp nghiệp vụ tra cứu địa điểm cơ quan hành chính công,
tính cự ly GPS thời gian thực, phân giải biến động sáp nhập và tạo liên kết Google Maps.

Tuân thủ ARCHITECTURE.md & Nghị định 13/2023/NĐ-CP:
- Xử lý in-memory cự ly, không lưu trữ toạ độ GPS cá nhân người dùng
- Cơ chế giải quyết sáp nhập (Merger Resolution Engine) chuẩn hoá 2023-2025
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote

from backend.db.agency_location_db import agency_location_db, AgencyLocationDatabase
from backend.services.agency_crawler import (
    calculate_haversine_distance,
    build_google_maps_directions_url,
    build_google_maps_search_url,
)


class AgencyLocationService:
    """Service nghiệp vụ điều phối tra cứu cơ quan hành chính & dẫn đường Google Maps."""

    def __init__(self, db: Optional[AgencyLocationDatabase] = None):
        self.db = db or agency_location_db

    def get_divisions(self, level: Optional[str] = None, parent_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy danh mục đơn vị hành chính theo cấp (province, district, ward) hoặc mã cha."""
        return self.db.get_administrative_units(level=level, parent_code=parent_code)

    def resolve_merger(self, query_name: str, province_name: Optional[str] = None, district_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Phân giải biến động sáp nhập cho tên xã/phường/huyện cũ."""
        if not query_name or not query_name.strip():
            return None
        return self.db.resolve_merger(query_name=query_name, province_name=province_name, district_name=district_name)

    def search_agencies(
        self,
        keyword: Optional[str] = None,
        province_code: Optional[str] = None,
        district_code: Optional[str] = None,
        ward_code: Optional[str] = None,
        agency_type: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Tìm kiếm cơ quan hành chính theo bộ lọc phân cấp hành chính hoặc từ khoá FTS5."""
        agencies, total = self.db.query_agencies(
            province_code=province_code,
            district_code=district_code,
            ward_code=ward_code,
            agency_type=agency_type,
            level=level,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )

        # Kiểm tra biến động sáp nhập nếu có keyword
        merger_info = None
        if keyword and keyword.strip():
            merger_info = self.resolve_merger(keyword.strip())

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "merger_notice": merger_info,
            "items": agencies,
        }

    def find_nearby_agencies(
        self,
        lat: float,
        lng: float,
        radius_km: float = 10.0,
        limit: int = 20,
        agency_type: Optional[str] = None,
        province_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tìm các cơ quan hành chính xung quanh toạ độ người dùng trong bán kính radius_km.
        Sắp xếp theo cự ly tăng dần và gắn sẵn link dẫn đường Google Maps.
        """
        all_candidates = self.db.get_all_agencies_for_geo(province_code=province_code)
        nearby_results = []

        for item in all_candidates:
            if agency_type and item.get("agency_type") != agency_type:
                continue

            dist = calculate_haversine_distance(lat, lng, item["latitude"], item["longitude"])
            if dist <= radius_km:
                item_copy = dict(item)
                item_copy["distance_km"] = dist
                # Sinh URL chỉ đường xuất phát từ vị trí người dùng đến cơ quan
                item_copy["google_maps_directions_url"] = build_google_maps_directions_url(
                    dest_lat=item["latitude"],
                    dest_lng=item["longitude"],
                    origin_lat=lat,
                    origin_lng=lng
                )
                nearby_results.append(item_copy)

        # Sắp xếp tăng dần theo khoảng cách
        nearby_results.sort(key=lambda x: x["distance_km"])
        paged_results = nearby_results[:limit]

        return {
            "origin": {"lat": lat, "lng": lng},
            "radius_km": radius_km,
            "total_found": len(nearby_results),
            "items": paged_results,
        }

    def get_agency_detail(self, agency_id: int) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết một cơ quan hành chính kèm dịch vụ liên kết."""
        agency = self.db.get_agency_by_id(agency_id)
        if not agency:
            return None

        # Sinh Google Maps Navigation URL mặc định
        agency["google_maps_directions_url"] = build_google_maps_directions_url(
            dest_lat=agency["latitude"],
            dest_lng=agency["longitude"]
        )
        return agency

    def generate_directions_url(
        self,
        agency_id: int,
        origin_lat: Optional[float] = None,
        origin_lng: Optional[float] = None,
        travel_mode: str = "driving"
    ) -> Dict[str, Any]:
        """Sinh URL chỉ đường chuẩn Universal Directions URL của Google Maps."""
        agency = self.db.get_agency_by_id(agency_id)
        if not agency:
            return {"error": "Không tìm thấy cơ quan hành chính", "url": None}

        dest_lat = agency["latitude"]
        dest_lng = agency["longitude"]

        if origin_lat is not None and origin_lng is not None:
            url = f"https://www.google.com/maps/dir/?api=1&origin={origin_lat:.6f},{origin_lng:.6f}&destination={dest_lat:.6f},{dest_lng:.6f}&travelmode={travel_mode}"
            dist = calculate_haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
        else:
            url = f"https://www.google.com/maps/dir/?api=1&destination={dest_lat:.6f},{dest_lng:.6f}&travelmode={travel_mode}"
            dist = None

        return {
            "agency_id": agency_id,
            "agency_name": agency["name"],
            "agency_address": agency["address"],
            "destination": {"lat": dest_lat, "lng": dest_lng},
            "distance_km": dist,
            "travel_mode": travel_mode,
            "directions_url": url,
            "search_url": build_google_maps_search_url(agency["name"], agency["address"]),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Lấy thống kê hiện trạng CSDL địa điểm."""
        return self.db.get_statistics()


# Singleton instance
agency_location_service = AgencyLocationService()
