'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, Clock, DollarSign, Building2, MapPin,
  CheckCircle2, FileText, Download, Bot, ChevronRight,
  Loader2, AlertCircle, Eye, Bookmark, BookmarkCheck,
  Upload,
} from 'lucide-react';
import { api } from '@/lib/api';
import { CATEGORIES, MOCK_PROCEDURES } from '@/lib/mockData';
import DocumentVerificationModal from '@/components/DocumentVerificationModal';
import PdfPreviewModal from '@/components/PdfPreviewModal';
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

  // 3. Fallback 2: tìm trong danh mục MOCK_PROCEDURES cốt lõi
  const mockFound = MOCK_PROCEDURES.find((p) => p.slug === slug);
  if (mockFound) {
    return mockFound as unknown as ProcedureDetail;
  }

  return null;
}

export default function ProcedureDetailPage() {
  const params = useParams();
  const router = useRouter();
  const slug = params.slug as string;

  const [proc, setProc] = useState<ReturnType<typeof normalize> | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  // ── Quản lý trạng thái thẩm định & tải biểu mẫu cho từng giấy tờ ──
  const [docStatuses, setDocStatuses] = useState<Record<number, { isVerified: boolean; details?: any }>>({});
  const [downloadingDocIndex, setDownloadingDocIndex] = useState<number | null>(null);
  const [uploadModalDoc, setUploadModalDoc] = useState<{ index: number; name: string } | null>(null);
  const [downloadNotification, setDownloadNotification] = useState<string | null>(null);
  const [previewModalDoc, setPreviewModalDoc] = useState<{ name: string } | null>(null);

  // Tải trạng thái thẩm định từ localStorage khi mở trang
  useEffect(() => {
    if (!slug) return;
    try {
      const savedStatus = localStorage.getItem(`vinalex_proc_docs_${slug}`);
      if (savedStatus) {
        setDocStatuses(JSON.parse(savedStatus));
      }
    } catch {
      // Bỏ qua lỗi localStorage
    }
  }, [slug]);

  // Xử lý tải file biểu mẫu PDF về máy (Mũi tên đi xuống)
  const handleDownloadTemplate = async (docName: string, index: number) => {
    if (!proc) return;
    setDownloadingDocIndex(index);
    try {
      const blob = await api.downloadDocumentTemplate(docName, proc.title, proc.slug);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const safeName = docName.replace(/[^a-zA-Z0-9\u00C0-\u1EF9]/g, '_').slice(0, 40);
      a.download = `bieu_mau_${safeName}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setDownloadNotification(`Đã tải biểu mẫu "${docName}" thành công!`);
      setTimeout(() => setDownloadNotification(null), 4000);
    } catch (err) {
      console.error(err);
      alert('Không thể tải biểu mẫu lúc này. Vui lòng thử lại sau.');
    } finally {
      setDownloadingDocIndex(null);
    }
  };

  // Xử lý khi OCR thẩm định thành công (Mũi tên đi lên -> Modal xác nhận)
  const handleSuccessVerified = (docName: string, result: any) => {
    if (uploadModalDoc === null) return;
    const idx = uploadModalDoc.index;
    const updated = {
      ...docStatuses,
      [idx]: { isVerified: true, details: result },
    };
    setDocStatuses(updated);
    try {
      localStorage.setItem(`vinalex_proc_docs_${slug}`, JSON.stringify(updated));
    } catch {
      // ignore
    }

    // Tự động đồng bộ tiến độ lên backend nếu người dùng đã lưu thủ tục
    const token = typeof window !== 'undefined' ? localStorage.getItem('vinalex_access_token') : null;
    if (token && proc && typeof proc.id === 'number') {
      const verifiedCount = Object.values(updated).filter((s) => s.isVerified).length;
      const totalDocs = proc.documents.length;
      api.saveUserProcedure(token, proc.id, `Tiến độ: ${verifiedCount}/${totalDocs} giấy tờ đã hoàn thành`).catch(() => {});
    }
  };

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

    // Nếu slug trùng với slug của Danh mục (ví dụ: dat-dai, thue, ho-tich...),
    // tự động chuyển hướng người dùng đến danh sách thủ tục của danh mục đó
    const matchedCategory = CATEGORIES.find((c) => c.slug === slug);
    if (matchedCategory) {
      router.replace(`/thu-tuc?category=${slug}`);
      return;
    }

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
  }, [slug, router]);

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
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '16px', flexWrap: 'wrap' }}>
              <Link href="/thu-tuc" className={styles.backBtn}>
                <ArrowLeft size={16} /> Về danh sách thủ tục
              </Link>
              <Link
                href={`/thu-tuc?q=${encodeURIComponent(slug.replace(/-/g, ' '))}`}
                className={styles.backBtn}
                style={{ background: 'var(--primary-color, #2563eb)', color: '#fff' }}
              >
                🔍 Tìm thủ tục liên quan
              </Link>
            </div>
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
              <div className={styles.sectionHeaderFlex}>
                <h2 className={styles.sectionTitle}>
                  <FileText size={22} className={styles.sectionIcon} />
                  Hồ sơ cần chuẩn bị
                </h2>
                {proc.documents.length > 0 && (
                  <span className={styles.progressBadge}>
                    Đã chuẩn bị: {Object.values(docStatuses).filter((s) => s.isVerified).length}/{proc.documents.length}
                  </span>
                )}
              </div>

              {/* Progress bar */}
              {proc.documents.length > 0 && (
                <div className={styles.docProgressBarContainer}>
                  <div
                    className={styles.docProgressBarFill}
                    style={{
                      width: `${Math.round(
                        (Object.values(docStatuses).filter((s) => s.isVerified).length / proc.documents.length) * 100
                      )}%`,
                    }}
                  />
                </div>
              )}

              {downloadNotification && (
                <div className={styles.downloadToast}>
                  <CheckCircle2 size={16} />
                  <span>{downloadNotification}</span>
                </div>
              )}

              <ul className={styles.docList}>
                {proc.documents.map((doc, i) => {
                  const docTitle = typeof doc === 'string' ? doc : (doc as { title?: string })?.title ?? String(doc);
                  const isVerified = Boolean(docStatuses[i]?.isVerified);
                  const isDownloading = downloadingDocIndex === i;

                  return (
                    <li
                      key={i}
                      className={`${styles.docItem} ${isVerified ? styles.docItemVerified : ''}`}
                    >
                      <div className={styles.docLeft}>
                        <CheckCircle2
                          size={18}
                          className={`${styles.docCheck} ${isVerified ? styles.docCheckVerified : ''}`}
                        />
                        <div className={styles.docInfo}>
                          <span className={`${styles.docTitleText} ${isVerified ? styles.docTitleVerified : ''}`}>
                            {docTitle}
                          </span>
                          {isVerified && (
                            <span className={styles.docVerifiedTag}>
                              ✓ Đã thẩm định đạt chuẩn
                            </span>
                          )}
                        </div>
                      </div>

                      <div className={styles.docActions}>
                        {/* Mũi tên đi lên: Tải file lên để OCR phân tích & thẩm định */}
                        <button
                          className={`${styles.docActionBtn} ${styles.docUploadBtn} ${
                            isVerified ? styles.docUploadBtnVerified : ''
                          }`}
                          title="Tải lên giấy tờ để OCR đối soát & kiểm tra tính hợp lệ"
                          onClick={() => setUploadModalDoc({ index: i, name: docTitle })}
                        >
                          <Upload size={14} />
                          <span className={styles.btnText}>Nộp & Thẩm định</span>
                        </button>

                        {/* Mũi tên đi xuống: Xem trước mẫu biểu mẫu trước khi tải về máy */}
                        <button
                          className={`${styles.docActionBtn} ${styles.docDownloadBtn}`}
                          title="Xem trước mẫu biểu mẫu và tải file PDF về máy"
                          onClick={() => setPreviewModalDoc({ name: docTitle })}
                        >
                          <Download size={14} />
                          <span className={styles.btnText}>Xem & Tải mẫu</span>
                        </button>
                      </div>
                    </li>
                  );
                })}
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

      {/* Modal thẩm định giấy tờ bằng AI OCR */}
      {uploadModalDoc && (
        <DocumentVerificationModal
          isOpen={true}
          onClose={() => setUploadModalDoc(null)}
          documentName={uploadModalDoc.name}
          procedureSlug={proc.slug}
          procedureTitle={proc.title}
          onSuccessVerified={handleSuccessVerified}
        />
      )}

      {/* Modal xem trước biểu mẫu PDF trước khi tải về */}
      {previewModalDoc && (
        <PdfPreviewModal
          isOpen={true}
          onClose={() => setPreviewModalDoc(null)}
          documentName={previewModalDoc.name}
          procedureSlug={proc.slug}
          procedureTitle={proc.title}
        />
      )}
    </div>
  );
}

