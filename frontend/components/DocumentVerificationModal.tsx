'use client';

import { useState, useRef, useEffect, DragEvent } from 'react';
import {
  X, Upload, FileText, CheckCircle2, AlertCircle, Loader2,
  RefreshCw, ShieldCheck, ArrowRight, Eye, AlertTriangle
} from 'lucide-react';
import { api } from '@/lib/api';
import styles from './DocumentVerificationModal.module.css';

interface VerificationResult {
  is_valid: boolean;
  status: 'passed' | 'rejected';
  document_type: string;
  expected_document: string;
  extracted_fields: Record<string, string>;
  validation_checks: Array<{ check: string; status: 'passed' | 'failed' | 'warning'; note: string }>;
  errors: string[];
  suggestions: string;
  processing_time_ms: number;
}

interface DocumentVerificationModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentName: string;
  procedureSlug: string;
  procedureTitle: string;
  onSuccessVerified: (docName: string, result: VerificationResult) => void;
}

function generateSessionId(): string {
  return 'verify-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
}

export default function DocumentVerificationModal({
  isOpen,
  onClose,
  documentName,
  procedureSlug,
  procedureTitle,
  onSuccessVerified,
}: DocumentVerificationModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState(1);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setSelectedFile(null);
      setPreviewUrl(null);
      setResult(null);
      setErrorMessage(null);
      setIsProcessing(false);
      setProcessingStep(1);
    }
  }, [isOpen, documentName]);

  // Clean up preview object URL
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  if (!isOpen) return null;

  const handleFileChange = (file: File) => {
    const validTypes = ['image/jpeg', 'image/png', 'image/heic', 'application/pdf'];
    if (!validTypes.includes(file.type)) {
      setErrorMessage('Định dạng tệp không được hỗ trợ. Vui lòng chọn ảnh JPG, PNG hoặc PDF.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage('Kích thước tệp vượt quá 10MB. Vui lòng chọn tệp dung lượng nhỏ hơn.');
      return;
    }

    setErrorMessage(null);
    setSelectedFile(file);
    setResult(null);

    if (file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleStartVerification = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setErrorMessage(null);
    setResult(null);

    // Multi-step visual progress simulation
    setProcessingStep(1);
    const step2Timer = setTimeout(() => setProcessingStep(2), 1200);
    const step3Timer = setTimeout(() => setProcessingStep(3), 2800);

    try {
      const sessionId = generateSessionId();
      const res = await api.verifyDocument(
        selectedFile,
        documentName,
        procedureSlug,
        procedureTitle,
        sessionId
      );

      clearTimeout(step2Timer);
      clearTimeout(step3Timer);
      setResult(res);
    } catch (err: unknown) {
      clearTimeout(step2Timer);
      clearTimeout(step3Timer);
      const msg = err instanceof Error ? err.message : 'Lỗi không xác định khi thẩm định hồ sơ';
      setErrorMessage(msg);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleConfirmCompletion = () => {
    if (result && result.is_valid) {
      onSuccessVerified(documentName, result);
      onClose();
    }
  };

  const handleResetForNewFile = () => {
    setSelectedFile(null);
    setPreviewUrl(null);
    setResult(null);
    setErrorMessage(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <div className={styles.badge}>
              <ShieldCheck size={14} className={styles.badgeIcon} />
              VinaLex AI Thẩm định hồ sơ
            </div>
            <h2 className={styles.title}>Nộp & Thẩm định giấy tờ</h2>
            <div className={styles.targetDoc}>
              <FileText size={14} className={styles.targetDocIcon} />
              <span>Yêu cầu: <strong>{documentName}</strong></span>
            </div>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Đóng">
            <X size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div className={styles.body}>
          {errorMessage && (
            <div className={styles.alertError}>
              <AlertCircle size={18} className={styles.alertIcon} />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* STEP 1: Upload & Select File */}
          {!isProcessing && !result && (
            <div>
              <div
                className={`${styles.dropZone} ${isDragging ? styles.dropZoneActive : ''}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/heic,application/pdf"
                  className={styles.fileInput}
                  onChange={(e) => e.target.files?.[0] && handleFileChange(e.target.files[0])}
                />

                {selectedFile ? (
                  <div className={styles.fileSelected}>
                    {previewUrl ? (
                      <div className={styles.previewContainer}>
                        <img src={previewUrl} alt="Xem trước" className={styles.previewImg} />
                      </div>
                    ) : (
                      <div className={styles.pdfIconWrapper}>
                        <FileText size={40} className={styles.pdfIcon} />
                      </div>
                    )}
                    <div className={styles.fileMeta}>
                      <span className={styles.fileName}>{selectedFile.name}</span>
                      <span className={styles.fileSize}>
                        {(selectedFile.size / 1024).toFixed(0)} KB • {selectedFile.type || 'Tệp tài liệu'}
                      </span>
                    </div>
                    <button
                      type="button"
                      className={styles.changeFileBtn}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleResetForNewFile();
                      }}
                    >
                      <RefreshCw size={13} /> Đổi tệp khác
                    </button>
                  </div>
                ) : (
                  <div className={styles.uploadPrompt}>
                    <div className={styles.uploadIconCircle}>
                      <Upload size={24} />
                    </div>
                    <p className={styles.uploadTitle}>Kéo thả tệp vào đây hoặc nhấn để chọn tệp</p>
                    <p className={styles.uploadSub}>Hỗ trợ định dạng: JPG, PNG, HEIC hoặc PDF (Tối đa 10MB)</p>
                  </div>
                )}
              </div>

              {/* Security & Guideline Note */}
              <div className={styles.guideNote}>
                <div className={styles.guideHeader}>
                  <ShieldCheck size={14} className={styles.guideIcon} />
                  <span>Quy tắc thẩm định bảo mật (NĐ 13/2023/NĐ-CP):</span>
                </div>
                <ul className={styles.guideList}>
                  <li>Tài liệu chỉ được xử lý tạm thời trên bộ nhớ RAM và tự hủy ngay sau khi thẩm định.</li>
                  <li>Chụp ảnh rõ 4 góc, đủ ánh sáng, không bị lóa hoặc che khuất thông tin.</li>
                  <li>Hệ thống sẽ đối soát loại giấy tờ với yêu cầu của thủ tục hành chính.</li>
                </ul>
              </div>
            </div>
          )}

          {/* STEP 2: Processing State */}
          {isProcessing && (
            <div className={styles.processingState}>
              <div className={styles.spinnerWrapper}>
                <Loader2 size={44} className={styles.spinner} />
              </div>
              <h3 className={styles.processingTitle}>Đang phân tích & Thẩm định giấy tờ...</h3>
              <p className={styles.processingSub}>Hệ thống AI đang thực hiện đối soát tự động</p>

              <div className={styles.stepsList}>
                <div className={`${styles.stepItem} ${processingStep >= 1 ? styles.stepItemActive : ''}`}>
                  <div className={styles.stepDot}>1</div>
                  <span>Tiền xử lý hình ảnh & Kiểm tra độ nét (OpenCV)</span>
                </div>
                <div className={`${styles.stepItem} ${processingStep >= 2 ? styles.stepItemActive : ''}`}>
                  <div className={styles.stepDot}>2</div>
                  <span>Bóc tách nội dung ký tự tiếng Việt (VietOCR)</span>
                </div>
                <div className={`${styles.stepItem} ${processingStep >= 3 ? styles.stepItemActive : ''}`}>
                  <div className={styles.stepDot}>3</div>
                  <span>Đối soát quy chuẩn với thành phần hồ sơ thủ tục</span>
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: Verification Result */}
          {!isProcessing && result && (
            <div className={styles.resultContainer}>
              {/* Outcome Banner */}
              {result.is_valid ? (
                <div className={styles.successBanner}>
                  <div className={styles.bannerIcon}>
                    <CheckCircle2 size={26} />
                  </div>
                  <div>
                    <h3 className={styles.bannerTitle}>Hồ sơ hợp lệ & Khớp với yêu cầu!</h3>
                    <p className={styles.bannerDesc}>
                      Tài liệu được xác nhận là <strong>{result.document_type}</strong> và đáp ứng đầy đủ điều kiện của thủ tục.
                    </p>
                  </div>
                </div>
              ) : (
                <div className={styles.rejectedBanner}>
                  <div className={styles.bannerIconReject}>
                    <AlertTriangle size={26} />
                  </div>
                  <div>
                    <h3 className={styles.bannerTitleReject}>Hồ sơ chưa đạt yêu cầu!</h3>
                    <p className={styles.bannerDescReject}>
                      Phát hiện sự không khớp hoặc thiếu sót thông tin so với quy định thủ tục.
                    </p>
                  </div>
                </div>
              )}

              {/* Errors List (if any) */}
              {result.errors && result.errors.length > 0 && (
                <div className={styles.errorBox}>
                  <div className={styles.errorBoxTitle}>
                    <AlertCircle size={15} />
                    Các vấn đề cần khắc phục:
                  </div>
                  <ul className={styles.errorList}>
                    {result.errors.map((err, idx) => (
                      <li key={idx} className={styles.errorItem}>{err}</li>
                    ))}
                  </ul>
                  {result.suggestions && (
                    <div className={styles.suggestionsBox}>
                      <strong>💡 Gợi ý giải pháp:</strong> {result.suggestions}
                    </div>
                  )}
                </div>
              )}

              {/* Validation Criteria Checks */}
              {result.validation_checks && result.validation_checks.length > 0 && (
                <div className={styles.checksSection}>
                  <h4 className={styles.sectionHeader}>Kết quả kiểm tra tiêu chí:</h4>
                  <div className={styles.checksGrid}>
                    {result.validation_checks.map((c, i) => (
                      <div key={i} className={styles.checkCard}>
                        <div className={styles.checkCardHeader}>
                          {c.status === 'passed' && <CheckCircle2 size={16} className={styles.checkPass} />}
                          {c.status === 'failed' && <AlertCircle size={16} className={styles.checkFail} />}
                          {c.status === 'warning' && <AlertTriangle size={16} className={styles.checkWarn} />}
                          <span className={styles.checkTitle}>{c.check}</span>
                        </div>
                        <span className={styles.checkNote}>{c.note}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Extracted Fields Table */}
              {result.extracted_fields && Object.keys(result.extracted_fields).length > 0 && (
                <div className={styles.fieldsSection}>
                  <h4 className={styles.sectionHeader}>Thông tin bóc tách được từ tài liệu:</h4>
                  <div className={styles.fieldsTable}>
                    {Object.entries(result.extracted_fields).map(([label, val], idx) => (
                      <div key={idx} className={styles.fieldRow}>
                        <span className={styles.fieldLabel}>{label}:</span>
                        <span className={styles.fieldVal}>{val}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className={styles.footer}>
          {!isProcessing && !result && (
            <>
              <button type="button" className={styles.cancelBtn} onClick={onClose}>
                Hủy bỏ
              </button>
              <button
                type="button"
                className={styles.primaryBtn}
                disabled={!selectedFile}
                onClick={handleStartVerification}
              >
                <span>Bắt đầu thẩm định</span>
                <ArrowRight size={15} />
              </button>
            </>
          )}

          {!isProcessing && result && result.is_valid && (
            <>
              <button type="button" className={styles.cancelBtn} onClick={handleResetForNewFile}>
                <RefreshCw size={13} /> Thẩm định lại
              </button>
              <button
                type="button"
                className={styles.successBtn}
                onClick={handleConfirmCompletion}
              >
                <CheckCircle2 size={15} />
                Xác nhận hoàn thành mục này
              </button>
            </>
          )}

          {!isProcessing && result && !result.is_valid && (
            <>
              <button type="button" className={styles.cancelBtn} onClick={onClose}>
                Đóng
              </button>
              <button
                type="button"
                className={styles.primaryBtn}
                onClick={handleResetForNewFile}
              >
                <RefreshCw size={15} />
                Tải lên lại tài liệu mới
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
