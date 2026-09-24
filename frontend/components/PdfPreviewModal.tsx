'use client';

import { useState, useEffect } from 'react';
import {
  X, Download, FileText, Loader2, AlertCircle, Eye,
  ShieldCheck, Printer, ExternalLink
} from 'lucide-react';
import { api } from '@/lib/api';
import styles from './PdfPreviewModal.module.css';

interface PdfPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentName: string;
  procedureSlug: string;
  procedureTitle: string;
}

function cleanDocTitle(raw: string, procTitle: string = '', slug: string = ''): { title: string; legalRef: string } {
  let clean = raw
    .replace(/\s*\([^)]*(nếu có|nếu cần|bản sao|bản chính|do bệnh viện|do cơ sở|tpct|chứng thực|photo)[^)]*\)/gi, '')
    .trim();

  const full = `${raw} ${procTitle} ${slug}`.toLowerCase();

  // 1. Biến động đất đai / Xác định lại diện tích đất ở (Mẫu 11/ĐK)
  if (
    full.includes('11/đk') ||
    full.includes('11-dk') ||
    full.includes('xác định lại') ||
    full.includes('xac dinh lai') ||
    full.includes('biến động') ||
    full.includes('bien dong') ||
    full.includes('tách thửa') ||
    full.includes('thừa kế') ||
    full.includes('chuyển nhượng')
  ) {
    return {
      title: 'Đơn đăng ký biến động đất đai, tài sản (Mẫu 11/ĐK)',
      legalRef: 'Nghị định 101/2024/NĐ-CP & Luật Đất đai 2024',
    };
  }

  // 2. Đăng ký cấp GCN đất đai lần đầu (Mẫu 04/ĐK)
  if (
    full.includes('04/đk') ||
    full.includes('04-dk') ||
    full.includes('cấp giấy chứng nhận') ||
    full.includes('đăng ký đất đai') ||
    (full.includes('đất') && (full.includes('sổ đỏ') || full.includes('sổ hồng') || full.includes('nhà ở')))
  ) {
    return {
      title: 'Đơn đăng ký, cấp GCN QSDĐ, nhà ở (Mẫu 04/ĐK)',
      legalRef: 'Nghị định 101/2024/NĐ-CP & Luật Đất đai 2024',
    };
  }

  // 3. Doanh nghiệp & Hộ kinh doanh
  if (full.includes('doanh nghiệp') || full.includes('doanh nghiep') || full.includes('công ty') || full.includes('hộ kinh doanh')) {
    return {
      title: 'Giấy đề nghị đăng ký doanh nghiệp / Hộ KD',
      legalRef: 'Thông tư 02/2023/TT-BKHĐT & NĐ 01/2021/NĐ-CP',
    };
  }

  // 4. Xây dựng
  if (full.includes('xây dựng') || full.includes('xay dung') || full.includes('gpxd')) {
    return {
      title: 'Đơn đề nghị cấp Giấy phép xây dựng (Mẫu 01)',
      legalRef: 'Nghị định 15/2021/NĐ-CP',
    };
  }

  // 5. Giấy phép lái xe
  if (full.includes('lái xe') || full.includes('lai xe') || full.includes('gplx') || full.includes('bằng lái')) {
    return {
      title: 'Đơn đề nghị đổi, cấp lại GPLX (Phụ lục 19)',
      legalRef: 'Thông tư 05/2024/TT-BGTVT',
    };
  }

  // 6. Y tế & Khám chữa bệnh
  if (full.includes('khám bệnh') || full.includes('chữa bệnh') || full.includes('hành nghề y') || full.includes('y tế')) {
    return {
      title: 'Đơn đề nghị cấp Giấy phép hành nghề / hoạt động KBCB',
      legalRef: 'Nghị định 96/2023/NĐ-CP',
    };
  }

  // 7. Bảo hiểm xã hội
  if (full.includes('bảo hiểm xã hội') || full.includes('bhxh') || full.includes('14-hsb')) {
    return {
      title: 'Đơn đề nghị giải quyết hưởng chế độ BHXH (Mẫu 14-HSB)',
      legalRef: 'Quyết định 166/QĐ-BHXH',
    };
  }

  // 8. Hộ tịch & Cư trú & Căn cước
  if (full.includes('kết hôn')) {
    return {
      title: 'Tờ khai Đăng ký kết hôn',
      legalRef: 'Thông tư 04/2020/TT-BTP',
    };
  }
  if (full.includes('khai sinh')) {
    return {
      title: 'Tờ khai Đăng ký khai sinh',
      legalRef: 'Thông tư 04/2020/TT-BTP',
    };
  }
  if (full.includes('chứng sinh')) {
    return {
      title: 'Giấy cam đoan về việc sinh con',
      legalRef: 'Điều 16 Luật Hộ tịch & TT 04/2020/TT-BTP',
    };
  }
  if (full.includes('cư trú') || full.includes('hộ khẩu') || full.includes('tạm trú')) {
    return {
      title: 'Tờ khai Thay đổi thông tin cư trú (CT01)',
      legalRef: 'Thông tư 56/2021/TT-BCA',
    };
  }
  if (full.includes('căn cước') || full.includes('cccd') || full.includes('cmnd')) {
    return {
      title: 'Tờ khai Căn cước (Mẫu DC01)',
      legalRef: 'Thông tư 17/2024/TT-BCA & Luật Căn cước',
    };
  }

  // 9. Thuế & Lao động
  if (full.includes('thuế') || full.includes('thue') || full.includes('qtt') || full.includes('tncn')) {
    return {
      title: 'Tờ khai Quyết toán thuế TNCN (Mẫu 02/QTT-TNCN)',
      legalRef: 'Thông tư 80/2021/TT-BTC',
    };
  }
  if (full.includes('lao động') || full.includes('người nước ngoài') || full.includes('giấy phép lao động')) {
    return {
      title: 'Văn bản đề nghị về Giấy phép lao động (Mẫu 09/PLI)',
      legalRef: 'Nghị định 152/2020/NĐ-CP & NĐ 70/2023/NĐ-CP',
    };
  }

  const isDon = /^(đơn|tờ khai|bản khai|giấy đề nghị)/i.test(clean);
  return {
    title: isDon ? clean : `Đơn đề nghị: ${clean}`,
    legalRef: 'Nghị định 30/2020/NĐ-CP & NĐ 61/2018/NĐ-CP',
  };
}

export default function PdfPreviewModal({
  isOpen,
  onClose,
  documentName,
  procedureSlug,
  procedureTitle,
}: PdfPreviewModalProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const { title: displayTitle, legalRef } = cleanDocTitle(documentName, procedureTitle, procedureSlug);

  // Load PDF blob when modal opens or retryKey changes
  useEffect(() => {
    if (!isOpen || !documentName) return;

    let isMounted = true;
    setLoading(true);
    setError(null);
    setBlobUrl(null);
    setPdfBlob(null);

    api.downloadDocumentTemplate(documentName, procedureTitle, procedureSlug, true)
      .then((blob) => {
        if (!isMounted) return;
        setPdfBlob(blob);
        const url = URL.createObjectURL(blob);
        setBlobUrl(url);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error('Error fetching preview PDF:', err);
        setError('Không thể tải biểu mẫu PDF để xem trước. Vui lòng kiểm tra máy chủ Backend (FastAPI cổng 8000) và thử lại.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [isOpen, documentName, procedureTitle, procedureSlug, retryKey]);

  if (!isOpen) return null;

  const handleDownload = () => {
    if (!pdfBlob) return;
    const url = URL.createObjectURL(pdfBlob);
    const a = document.createElement('a');
    a.href = url;
    const safeName = displayTitle.replace(/[^a-zA-Z0-9\u00C0-\u1EF9]/g, '_').slice(0, 40);
    a.download = `${safeName}.pdf`;
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  const handleOpenNewTab = () => {
    if (blobUrl) {
      window.open(blobUrl, '_blank');
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <div className={styles.badgeRow}>
              <span className={styles.badge}>
                <Eye size={13} className={styles.badgeIcon} />
                Xem trước biểu mẫu
              </span>
              <span className={styles.subBadge}>
                <ShieldCheck size={13} />
                {legalRef}
              </span>
            </div>
            <h2 className={styles.title}>{displayTitle}</h2>
            <p className={styles.subtitle}>Thủ tục: <strong>{procedureTitle}</strong></p>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Đóng">
            <X size={18} />
          </button>
        </div>

        {/* Body / PDF Viewer */}
        <div className={styles.body}>
          {loading && (
            <div className={styles.loadingContainer}>
              <Loader2 size={40} className={styles.spinner} />
              <p className={styles.loadingText}>Đang tạo và nạp bản xem trước biểu mẫu PDF...</p>
              <span className={styles.loadingSub}>Sinh động theo chuẩn thể thức văn bản hành chính Việt Nam</span>
            </div>
          )}

          {error && (
            <div className={styles.errorContainer}>
              <AlertCircle size={36} className={styles.errorIcon} />
              <p className={styles.errorText}>{error}</p>
              <div style={{ display: 'flex', gap: '10px', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className={styles.retryBtn}
                  style={{ background: '#2563eb', borderColor: '#3b82f6', color: '#ffffff', fontWeight: 600 }}
                  onClick={() => setRetryKey((k) => k + 1)}
                >
                  Thử lại
                </button>
                <button type="button" className={styles.retryBtn} onClick={onClose}>
                  Đóng
                </button>
              </div>
            </div>
          )}

          {!loading && !error && blobUrl && (
            <div className={styles.iframeWrapper}>
              <iframe
                src={`${blobUrl}#toolbar=1&navpanes=0`}
                className={styles.pdfIframe}
                title={`Xem trước ${documentName}`}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <div className={styles.footerInfo}>
            <span className={styles.fileFormatTag}>Định dạng: PDF (Khổ A4)</span>
            {pdfBlob && (
              <span className={styles.fileSizeTag}>
                Kích thước: {(pdfBlob.size / 1024).toFixed(0)} KB
              </span>
            )}
          </div>

          <div className={styles.footerActions}>
            {blobUrl && (
              <button
                type="button"
                className={styles.secondaryBtn}
                onClick={handleOpenNewTab}
                title="Mở toàn màn hình trong tab mới"
              >
                <ExternalLink size={14} />
                <span>Mở tab mới</span>
              </button>
            )}
            <button type="button" className={styles.cancelBtn} onClick={onClose}>
              Đóng
            </button>
            <button
              type="button"
              className={styles.downloadBtn}
              onClick={handleDownload}
              disabled={loading || !pdfBlob}
            >
              <Download size={15} />
              <span>Tải file PDF về máy</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
