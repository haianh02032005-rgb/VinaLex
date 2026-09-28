'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  MapPin,
  Navigation,
  Search,
  Building2,
  Phone,
  Clock,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Copy,
  Compass,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import { buildApiUrl } from '@/lib/apiConfig';
import styles from './page.module.css';

interface AdministrativeUnit {
  code: string;
  name: string;
  level: string;
  parent_code: string | null;
  full_name: string;
}

interface MergerNotice {
  old_unit_name: string;
  old_district: string;
  old_province: string;
  new_unit_name: string;
  resolution_code: string;
  effective_date: string;
  headquarters_address: string;
  notes: string;
}

interface Agency {
  id: number;
  name: string;
  short_name?: string;
  agency_type: string;
  level: string;
  province_name: string;
  district_name?: string;
  ward_name?: string;
  address: string;
  latitude: number;
  longitude: number;
  phone?: string;
  email?: string;
  working_hours?: string;
  distance_km?: number;
  google_maps_directions_url?: string;
  google_maps_url?: string;
}

export default function AgencyLocationPage() {
  const [keyword, setKeyword] = useState('');
  const [provinces, setProvinces] = useState<AdministrativeUnit[]>([]);
  const [districts, setDistricts] = useState<AdministrativeUnit[]>([]);
  const [wards, setWards] = useState<AdministrativeUnit[]>([]);

  const [selectedProvince, setSelectedProvince] = useState<string>('01'); // Default Hà Nội
  const [selectedDistrict, setSelectedDistrict] = useState<string>('');
  const [selectedWard, setSelectedWard] = useState<string>('');

  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [mergerNotice, setMergerNotice] = useState<MergerNotice | null>(null);

  const [userCoords, setUserCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [isLocating, setIsLocating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  // Helper fetch an toàn qua proxy hoặc backend trực tiếp
  const apiFetch = async (endpoint: string) => {
    try {
      const url = endpoint.startsWith('http')
        ? endpoint
        : endpoint.startsWith('/api/v1')
        ? buildApiUrl(endpoint.substring('/api/v1'.length))
        : buildApiUrl(endpoint);
      const res = await fetch(url);
      if (res.ok) return await res.json();
    } catch (err) {
      console.error('API Fetch error:', err);
    }
    return null;
  };

  // 1. Tải danh mục 63 tỉnh thành
  useEffect(() => {
    const fetchProvinces = async () => {
      const data = await apiFetch('/api/v1/locations/divisions?level=province');
      if (data && data.items) {
        setProvinces(data.items);
      }
    };
    fetchProvinces();
  }, []);

  // 2. Tải danh mục quận/huyện khi tỉnh thay đổi
  useEffect(() => {
    if (!selectedProvince) {
      setDistricts([]);
      setSelectedDistrict('');
      return;
    }
    const fetchDistricts = async () => {
      const data = await apiFetch(`/api/v1/locations/divisions?level=district&parent_code=${selectedProvince}`);
      if (data && data.items) {
        setDistricts(data.items);
      } else {
        setDistricts([]);
      }
      setSelectedDistrict('');
      setWards([]);
      setSelectedWard('');
    };
    fetchDistricts();
  }, [selectedProvince]);

  // 3. Tải danh mục phường/xã khi quận thay đổi
  useEffect(() => {
    if (!selectedDistrict) {
      setWards([]);
      setSelectedWard('');
      return;
    }
    const fetchWards = async () => {
      const data = await apiFetch(`/api/v1/locations/divisions?level=ward&parent_code=${selectedDistrict}`);
      if (data && data.items) {
        setWards(data.items);
      } else {
        setWards([]);
      }
      setSelectedWard('');
    };
    fetchWards();
  }, [selectedDistrict]);

  // 4. Tìm kiếm cơ quan hành chính theo bộ lọc hoặc từ khoá
  const loadAgencies = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      if (userCoords) {
        // Chế độ GPS gần nhất
        const data = await apiFetch(
          `/api/v1/locations/agencies/nearby?lat=${userCoords.lat}&lng=${userCoords.lng}&radius_km=15`
        );
        if (data && data.items) {
          setAgencies(data.items);
          setMergerNotice(null);
        }
      } else {
        // Chế độ theo phân cấp hành chính hoặc từ khoá
        const params = new URLSearchParams();
        if (keyword.trim()) params.append('keyword', keyword.trim());
        if (selectedProvince) params.append('province_code', selectedProvince);
        if (selectedDistrict) params.append('district_code', selectedDistrict);
        if (selectedWard) params.append('ward_code', selectedWard);

        const data = await apiFetch(`/api/v1/locations/agencies?${params.toString()}`);
        if (data) {
          setAgencies(data.items || []);
          setMergerNotice(data.merger_notice || null);
        }
      }
    } catch {
      setErrorMsg('Không thể nạp dữ liệu cơ quan hành chính. Vui lòng kiểm tra lại kết nối máy chủ.');
    } finally {
      setLoading(false);
    }
  }, [userCoords, keyword, selectedProvince, selectedDistrict, selectedWard]);

  useEffect(() => {
    loadAgencies();
  }, [loadAgencies]);

  // 5. Kích hoạt lấy vị trí GPS hiện tại của người dùng
  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      alert('Trình duyệt của bạn không hỗ trợ chức năng định vị Geolocation.');
      return;
    }
    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserCoords({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        });
        setIsLocating(false);
      },
      (err) => {
        setIsLocating(false);
        alert(
          'Không thể truy cập vị trí hiện tại của bạn. Vui lòng cấp quyền vị trí hoặc chọn tỉnh/thành phố thủ công.'
        );
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  // 6. Xóa chế độ GPS để quay lại chọn địa bàn thủ công
  const handleClearLocation = () => {
    setUserCoords(null);
  };

  // 7. Copy địa chỉ trụ sở vào Clipboard
  const handleCopyAddress = (id: number, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2500);
  };

  // Helper hiển thị badge loại cơ quan
  const renderBadge = (type: string) => {
    switch (type) {
      case 'one_stop_ward':
        return <span className={`${styles.agencyBadge} ${styles.badgeWard}`}>Một cửa Cấp Xã / Phường</span>;
      case 'one_stop_district':
        return <span className={`${styles.agencyBadge} ${styles.badgeDistrict}`}>Một cửa Cấp Quận / Huyện</span>;
      case 'land_registry':
        return <span className={`${styles.agencyBadge} ${styles.badgeLand}`}>Văn phòng Đăng ký Đất đai</span>;
      case 'police':
        return <span className={`${styles.agencyBadge} ${styles.badgePolice}`}>Công an / Quản lý Hành chính</span>;
      case 'tax':
        return <span className={`${styles.agencyBadge} ${styles.badgeTax}`}>Chi cục Thuế</span>;
      default:
        return <span className={`${styles.agencyBadge} ${styles.badgeDistrict}`}>Bộ phận Một Cửa</span>;
    }
  };

  // Helper tạo Google Maps URL
  const getGoogleMapsUrl = (agency: Agency) => {
    if (userCoords) {
      return `https://www.google.com/maps/dir/?api=1&origin=${userCoords.lat},${userCoords.lng}&destination=${agency.latitude},${agency.longitude}&travelmode=driving`;
    }
    if (agency.google_maps_directions_url) {
      return agency.google_maps_directions_url;
    }
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(agency.name + ', ' + agency.address)}`;
  };

  return (
    <div className={styles.pageWrapper}>
      <div className={styles.container}>
        {/* ── Header ── */}
        <header className={styles.heroHeader}>
          <div className={styles.badge}>
            <Compass size={16} />
            <span>Cập nhật Địa giới Sáp nhập 2023 — 2025</span>
          </div>
          <h1 className={styles.title}>
            Tra Cứu Địa Điểm & Đường Đi Đến{' '}
            <span className={styles.titleGradient}>Cơ Quan Dịch Vụ Công</span>
          </h1>
          <p className={styles.subtitle}>
            Xác định chính xác trụ sở Bộ phận Một cửa, UBND, Chi nhánh Đăng ký Đất đai, Công an nơi bạn sinh sống.
            Dẫn đường trực tiếp qua Google Maps chỉ với 1-click.
          </p>
        </header>

        {/* ── Thanh Công Cụ Tra Cứu (Search & Filter) ── */}
        <section className={styles.searchSection} aria-label="Bộ lọc tìm kiếm cơ quan">
          <div className={styles.searchGrid}>
            {/* Input từ khóa */}
            <div className={styles.inputGroup}>
              <Search className={styles.inputIcon} size={18} />
              <input
                type="text"
                className={styles.searchInput}
                placeholder="Gõ tên phường cũ/mới, quận huyện hoặc tên cơ quan (VD: Trung Phụng, Sổ đỏ Đống Đa...)"
                value={keyword}
                onChange={(e) => {
                  setKeyword(e.target.value);
                  if (userCoords) setUserCoords(null);
                }}
              />
            </div>

            {/* Chọn Tỉnh/Thành */}
            <div>
              <select
                className={styles.selectInput}
                value={selectedProvince}
                onChange={(e) => {
                  setSelectedProvince(e.target.value);
                  if (userCoords) setUserCoords(null);
                }}
              >
                <option value="">Tất cả Tỉnh / Thành</option>
                {provinces.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Chọn Quận/Huyện */}
            <div>
              <select
                className={styles.selectInput}
                value={selectedDistrict}
                onChange={(e) => {
                  setSelectedDistrict(e.target.value);
                  if (userCoords) setUserCoords(null);
                }}
                disabled={!selectedProvince}
              >
                <option value="">Tất cả Quận / Huyện</option>
                {districts.map((d) => (
                  <option key={d.code} value={d.code}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Chọn Phường/Xã */}
            <div>
              <select
                className={styles.selectInput}
                value={selectedWard}
                onChange={(e) => {
                  setSelectedWard(e.target.value);
                  if (userCoords) setUserCoords(null);
                }}
                disabled={!selectedDistrict}
              >
                <option value="">Tất cả Phường / Xã</option>
                {wards.map((w) => (
                  <option key={w.code} value={w.code}>
                    {w.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Nút GPS định vị gần tôi */}
            <div>
              {userCoords ? (
                <button
                  type="button"
                  className={styles.geoButton}
                  style={{ background: 'rgba(239, 68, 68, 0.85)' }}
                  onClick={handleClearLocation}
                  title="Hủy chế độ GPS để chọn thủ công"
                >
                  <MapPin size={18} />
                  <span>Đang bật GPS (Hủy)</span>
                </button>
              ) : (
                <button
                  type="button"
                  className={styles.geoButton}
                  onClick={handleGetLocation}
                  disabled={isLocating}
                >
                  <Navigation size={18} />
                  <span>{isLocating ? 'Đang định vị...' : 'Gần tôi nhất'}</span>
                </button>
              )}
            </div>
          </div>
        </section>

        {/* ── Banner Thông Báo Biến Động Sáp Nhập (Nghị Quyết UBTVQH) ── */}
        {mergerNotice && (
          <aside className={styles.mergerBanner} aria-label="Thông báo biến động sáp nhập đơn vị hành chính">
            <div className={styles.mergerIcon}>
              <ShieldAlert size={26} />
            </div>
            <div className={styles.mergerContent}>
              <h4>
                Thông Báo Sáp Nhập Đơn Vị Hành Chính
                <span className={styles.mergerResCode}>NQ {mergerNotice.resolution_code}</span>
              </h4>
              <p>
                Địa bàn <span className={styles.mergerHighlight}>{mergerNotice.old_unit_name}</span> ({mergerNotice.old_district}) đã chính thức sáp nhập vào{' '}
                <span className={styles.mergerHighlight}>{mergerNotice.new_unit_name}</span> (Có hiệu lực từ {mergerNotice.effective_date}).
              </p>
              <p>
                🏛️ <strong>Trụ sở tiếp nhận hồ sơ chính thức mới:</strong> {mergerNotice.headquarters_address}
              </p>
              <p style={{ color: '#94A3B8', fontSize: '0.85rem' }}>
                ℹ️ <em>{mergerNotice.notes}</em>
              </p>
            </div>
          </aside>
        )}

        {/* ── Danh Sách Cơ Quan Hành Chính ── */}
        <main className={styles.contentGrid}>
          {loading ? (
            <div className={styles.stateBox}>
              <div className={styles.spinner} />
              <p>Đang tra cứu danh bạ cơ quan và đường đi gần nhất...</p>
            </div>
          ) : errorMsg ? (
            <div className={styles.stateBox}>
              <AlertCircle size={40} className={styles.stateIcon} style={{ color: '#EF4444' }} />
              <p>{errorMsg}</p>
            </div>
          ) : agencies.length === 0 ? (
            <div className={styles.stateBox}>
              <Building2 size={40} className={styles.stateIcon} />
              <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                Không tìm thấy cơ quan hành chính phù hợp
              </h3>
              <p>
                Vui lòng thử tìm kiếm với tên phường/xã khác, nới rộng bán kính hoặc chọn theo Tỉnh/Thành phố.
              </p>
            </div>
          ) : (
            agencies.map((agency) => {
              const mapsUrl = getGoogleMapsUrl(agency);
              return (
                <article key={agency.id} className={styles.agencyCard}>
                  <div className={styles.cardHeader}>
                    <div>
                      <h2 className={styles.agencyName}>{agency.name}</h2>
                      {agency.short_name && (
                        <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                          {agency.short_name}
                        </p>
                      )}
                    </div>
                    {renderBadge(agency.agency_type)}
                  </div>

                  <div className={styles.cardBody}>
                    <div className={styles.infoRow}>
                      <MapPin className={styles.infoIcon} size={16} />
                      <span>{agency.address}</span>
                      {agency.distance_km !== undefined && (
                        <span className={styles.distanceBadge}>
                          📍 {agency.distance_km} km
                        </span>
                      )}
                    </div>

                    <div className={styles.infoRow}>
                      <Clock className={styles.infoIcon} size={16} />
                      <span>{agency.working_hours || '08:00 - 11:30 | 13:30 - 17:00 (Thứ 2 - Thứ 6)'}</span>
                    </div>

                    {agency.phone && (
                      <div className={styles.infoRow}>
                        <Phone className={styles.infoIcon} size={16} />
                        <a href={`tel:${agency.phone.replace(/[^0-9]/g, '')}`} style={{ color: 'var(--text-accent)', textDecoration: 'none' }}>
                          {agency.phone}
                        </a>
                      </div>
                    )}
                  </div>

                  <div className={styles.cardActions}>
                    <a
                      href={mapsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.directionBtn}
                      id={`gmap-dir-btn-${agency.id}`}
                    >
                      <Navigation size={16} />
                      <span>Chỉ đường trên Google Maps</span>
                      <ExternalLink size={14} style={{ opacity: 0.8 }} />
                    </a>

                    <button
                      type="button"
                      className={styles.copyBtn}
                      onClick={() => handleCopyAddress(agency.id, agency.address)}
                    >
                      {copiedId === agency.id ? (
                        <>
                          <CheckCircle2 size={15} style={{ color: '#10B981' }} />
                          <span style={{ color: '#10B981' }}>Đã sao chép</span>
                        </>
                      ) : (
                        <>
                          <Copy size={15} />
                          <span>Sao chép địa chỉ</span>
                        </>
                      )}
                    </button>
                  </div>
                </article>
              );
            })
          )}
        </main>
      </div>
    </div>
  );
}
