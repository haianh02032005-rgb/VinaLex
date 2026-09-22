'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, Clock, DollarSign, Building2, MapPin,
  CheckCircle2, FileText, Download, Bot, ChevronRight,
  Loader2, AlertCircle, Eye, Bookmark, BookmarkCheck,
} from 'lucide-react';
import { api } from '@/lib/api';
import styles from './page.module.css';

// ── Types (phản chiếu cả backend API lẫn mockData) ──
interface ProcedureStep {
  index: number;
  title: string;
  description: string;
  duration?: string;
}

interface ProcedureDetail {
  id: number | string;
  slug: string;
  title: string;
  category: string;
  category_slug?: string;
  categorySlug?: string;
  description: string;
  steps: ProcedureStep[];
  documents: string[];
  processing_time?: string;
  processingTime?: string;
  fee: string;
  agency: string;
  level: string;
  tags: string[];
  updated_at?: string;
  updatedAt?: string;
  view_count?: number;
  viewCount?: number;
}

// ── Normalizer: chuẩn hoá từ cả 2 định dạng (API snake_case & mock camelCase) ──
function normalize(raw: ProcedureDetail) {
  return {
    ...raw,
    processingTime: raw.processing_time ?? raw.processingTime ?? '',
    updatedAt: raw.updated_at ?? raw.updatedAt ?? '',
    viewCount: raw.view_count ?? raw.viewCount ?? 0,
    categorySlug: raw.category_slug ?? raw.categorySlug ?? '',
  };
}

// ── Hàm lấy dữ liệu: thử API backend trước, fallback sang JSON tĩnh ──
async function fetchProcedure(slug: string): Promise<ProcedureDetail | null> {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  // 1. Thử API Backend
  try {
    const res = await fetch(`${API_BASE}/procedures/${slug}`, { cache: 'no-store' });
    if (res.ok) {
      const data = await res.json();
      return data as ProcedureDetail;
    }
  } catch {
    // Backend offline — tiếp tục fallback
  }

  // 2. Fallback 1: tìm trong crawled_procedures.json (122 thủ tục thực tế)
  try {
    const res = await fetch('/api/procedures-fallback?slug=' + encodeURIComponent(slug), {
      cache: 'no-store',
    });
    if (res.ok) {
      const data = await res.json();
      return data as ProcedureDetail;
    }
  } catch {
    // API route fallback cũng không có
  }

  return null;
}

export default function ProcedureDetailPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [proc, setProc] = useState<ReturnType<typeof normalize> | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSaveProcedure = async () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('vinalex_access_token') : null;
    if (!token) {
      window.location.href = '/dang-nhap';
      return;
    }
    if (proc && typeof proc.id === 'number') {
      setSaving(true);
      try {
        await api.saveUserProcedure(token, proc.id);
        setSaved(true);
      } catch {
        setSaved(true);
      } finally {
        setSaving(false);
      }
    } else {
      setSaved(true);
    }
  };


  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    setNotFound(false);

    fetchProcedure(slug)
      .then((data) => {
        if (!data) {
          setNotFound(true);
        } else {
          setProc(normalize(data));
        }
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [slug]);

  // ── Loading State ──
  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.container}>
          <div className={styles.loadingState}>
            <Loader2 size={36} className={styles.spinner} />
            <p>Đang tải thông tin thủ tục...</p>
          </div>
        </div>
      </div>
    );
  }

  // ── Not Found State ──
  if (notFound || !proc) {
    return (
      <div className={styles.page}>
        <div className={styles.container}>
          <div className={styles.notFoundState}>
            <AlertCircle size={48} className={styles.notFoundIcon} />
            <h1 className={styles.notFoundTitle}>Không tìm thấy thủ tục</h1>
            <p className={styles.notFoundDesc}>
              Thủ tục <strong>{slug}</strong> không tồn tại hoặc đã bị gỡ xuống.
            </p>
            <Link href="/thu-tuc" className={styles.backBtn}>
              <ArrowLeft size={16} /> Về danh sách thủ tục
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        {/* Breadcrumb */}
        <div className={styles.breadcrumb}>
          <Link href="/">Trang chủ</Link>
          <ChevronRight size={14} />
          <Link href="/thu-tuc">Thủ tục</Link>
          <ChevronRight size={14} />
          <span>{proc.title}</span>
        </div>

        <div className={styles.layout}>
          {/* Main Content */}
          <main className={styles.main}>
            {/* Header */}
            <div className={styles.header}>
              <Link href="/thu-tuc" className={styles.backBtn}>
                <ArrowLeft size={16} /> Quay lại danh sách
              </Link>

              <div className={styles.categoryRow}>
                <span className={styles.categoryBadge}>{proc.category}</span>
                <span className={styles.levelBadge}>{proc.level}</span>
                {proc.tags.map((tag) => (
                  <span key={tag} className={styles.tagBadge}>{tag}</span>
                ))}
              </div>

              <h1 className={styles.title}>{proc.title}</h1>
              <p className={styles.description}>{proc.description}</p>

              {/* Quick Info */}
              <div className={styles.infoRow}>
                <div className={styles.infoItem}>
                  <Clock size={16} className={styles.infoIcon} />
                  <div>
                    <div className={styles.infoLabel}>Thời gian xử lý</div>
                    <div className={styles.infoValue}>{proc.processingTime}</div>
                  </div>
                </div>
                <div className={styles.infoItem}>
                  <DollarSign size={16} className={styles.infoIcon} />
                  <div>
                    <div className={styles.infoLabel}>Lệ phí</div>
                    <div className={styles.infoValue}>{proc.fee}</div>
                  </div>
                </div>
                <div className={styles.infoItem}>
                  <Building2 size={16} className={styles.infoIcon} />
                  <div>
                    <div className={styles.infoLabel}>Cơ quan thực hiện</div>
                    <div className={styles.infoValue}>{proc.agency}</div>
                  </div>
                </div>
                <div className={styles.infoItem}>
                  <MapPin size={16} className={styles.infoIcon} />
                  <div>
                    <div className={styles.infoLabel}>Cấp thực hiện</div>
                    <div className={styles.infoValue}>{proc.level}</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Steps */}
            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>
                <CheckCircle2 size={22} className={styles.sectionIcon} />
                Các bước thực hiện
              </h2>
              <div className={styles.stepsTimeline}>
                {proc.steps.map((step, idx) => (
                  <div key={step.index} className={styles.step}>
                    <div className={styles.stepLeft}>
                      <div className={styles.stepNumber}>{step.index}</div>
                      {idx < proc.steps.length - 1 && <div className={styles.stepLine} />}
                    </div>
                    <div className={styles.stepContent}>
                      <div className={styles.stepHeader}>
                        <h3 className={styles.stepTitle}>{step.title}</h3>
                        {step.duration && (
                          <span className={styles.stepDuration}>
                            <Clock size={12} /> {step.duration}
                          </span>
                        )}
                      </div>
                      <p className={styles.stepDesc}>{step.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Documents */}
            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>
                <FileText size={22} className={styles.sectionIcon} />
                Hồ sơ cần chuẩn bị
              </h2>
              <ul className={styles.docList}>
                {proc.documents.map((doc, i) => (
                  <li key={i} className={styles.docItem}>
                    <CheckCircle2 size={16} className={styles.docCheck} />
                    <span>{typeof doc === 'string' ? doc : (doc as { title?: string })?.title ?? String(doc)}</span>
                    <button className={styles.docDownload} title="Tải biểu mẫu">
                      <Download size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          </main>

          {/* Sidebar */}
          <aside className={styles.sidebar}>
            {/* AI Panel */}
            <div className={styles.aiPanel}>
              <div className={styles.aiPanelHeader}>
                <div className={styles.aiAvatar}>
                  <Bot size={18} />
                </div>
                <div>
                  <div className={styles.aiName}>Trợ lý VinaLex AI</div>
                  <div className={styles.aiStatus}>
                    <span className={styles.statusDot} />
                    Đang hoạt động
                  </div>
                </div>
              </div>
              <p className={styles.aiIntro}>
                Bạn có câu hỏi về thủ tục <strong>{proc.title}</strong>? Tôi có thể giúp bạn kiểm tra hồ sơ và giải đáp thắc mắc.
              </p>
              <Link href="/tro-ly-ai" className={styles.aiBtn} id={`ask-ai-${proc.slug}`}>
                Hỏi Trợ lý AI
                <ArrowLeft size={15} className={styles.aiBtnArrow} />
              </Link>
              <button
                onClick={handleSaveProcedure}
                disabled={saving || saved}
                className={`${styles.saveBtn} ${saved ? styles.saveBtnActive : ''}`}
                id={`save-proc-${proc.slug}`}
              >
                {saved ? (
                  <>
                    <BookmarkCheck size={16} />
                    Đã lưu vào hồ sơ theo dõi
                  </>
                ) : saving ? (
                  <>
                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                    Đang lưu...
                  </>
                ) : (
                  <>
                    <Bookmark size={16} />
                    Lưu vào hồ sơ theo dõi
                  </>
                )}
              </button>
            </div>


            {/* Summary Card */}
            <div className={styles.summaryCard}>
              <h3 className={styles.summaryTitle}>Tóm tắt nhanh</h3>
              <div className={styles.summaryItems}>
                <div className={styles.summaryItem}>
                  <span className={styles.summaryLabel}>Số bước thực hiện</span>
                  <span className={styles.summaryValue}>{proc.steps.length} bước</span>
                </div>
                <div className={styles.summaryItem}>
                  <span className={styles.summaryLabel}>Số giấy tờ</span>
                  <span className={styles.summaryValue}>{proc.documents.length} loại</span>
                </div>
                {proc.updatedAt && (
                  <div className={styles.summaryItem}>
                    <span className={styles.summaryLabel}>Cập nhật</span>
                    <span className={styles.summaryValue}>
                      {new Date(proc.updatedAt).toLocaleDateString('vi-VN')}
                    </span>
                  </div>
                )}
                {proc.viewCount > 0 && (
                  <div className={styles.summaryItem}>
                    <span className={styles.summaryLabel}>Lượt xem</span>
                    <span className={styles.summaryValue}>
                      <Eye size={12} style={{ display: 'inline', marginRight: 4 }} />
                      {proc.viewCount.toLocaleString('vi-VN')}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
