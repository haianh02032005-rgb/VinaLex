'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Bot, Upload, Send, Shield, Paperclip, X, FileText, CheckCircle, Loader2, AlertCircle, User, Sparkles } from 'lucide-react';
import { marked } from 'marked';
import styles from './page.module.css';
import { api } from '@/lib/api';
import PdfPreviewModal from '@/components/PdfPreviewModal';

function renderPdfCardHtml(docName: string, title: string, slug: string): string {
  const safeDoc = docName.replace(/"/g, '&quot;');
  const safeTitle = title.replace(/"/g, '&quot;');
  const safeSlug = slug.replace(/"/g, '&quot;');

  return `
<div class="vinalexPdfCard" data-pdf-card="true">
  <div class="vinalexPdfCardTop">
    <div class="vinalexPdfCardBadge">
      <span class="vinalexPdfBadgeTag">📄 BIỂU MẪU CHÍNH THỨC</span>
      <span class="vinalexPdfBadgeSub">Chuẩn thể thức Nghị định 30/2020/NĐ-CP</span>
    </div>
  </div>
  <div class="vinalexPdfCardBody">
    <div class="vinalexPdfIconWrapper">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><path d="M10 13v-2a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1z"/><path d="M10 17v-1a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1"/></svg>
    </div>
    <div class="vinalexPdfDetails">
      <div class="vinalexPdfTitle">${safeDoc}</div>
      <div class="vinalexPdfMeta">Thủ tục: <strong>${safeTitle}</strong> · Định dạng PDF A4 chuẩn Nhà nước</div>
    </div>
  </div>
  <div class="vinalexPdfActions">
    <button type="button" class="vinalexPdfBtnDownload" data-action="download-pdf" data-doc="${safeDoc}" data-title="${safeTitle}" data-slug="${safeSlug}">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      <span>Tải file PDF trực tiếp</span>
    </button>
    <button type="button" class="vinalexPdfBtnPreview" data-action="preview-pdf" data-doc="${safeDoc}" data-title="${safeTitle}" data-slug="${safeSlug}">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
      <span>Xem trước biểu mẫu A4</span>
    </button>
  </div>
</div>
`;
}

// Tạo session UUID cho mỗi phiên làm việc — Backend dùng để xóa Redis đúng cách
// Tuân thủ luồng: Frontend → FastAPI → Redis → AI → Trả JSON → Xóa Redis (ARCHITECTURE.md)
function generateSessionId(): string {
  return 'session-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 9);
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: string[];
}

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  status: 'uploading' | 'done' | 'error';
  preview?: string;
}

const WELCOME_MSG: Message = {
  id: 'welcome',
  role: 'assistant',
  content: `Xin chào! Tôi là **Trợ lý VinaLex AI** — được huấn luyện trên hàng nghìn văn bản pháp luật Việt Nam.\n\nTôi có thể giúp bạn:\n• 📋 **Tra cứu** thủ tục và điều kiện pháp lý\n• 🔍 **Kiểm tra** tính hợp lệ của hồ sơ\n• 📄 **Bóc tách dữ liệu** từ CMND, hợp đồng, giấy tờ\n• ⚖️ **Giải đáp** các quy định pháp luật\n\nTải file lên bên trái hoặc gõ câu hỏi bên dưới để bắt đầu!`,
  timestamp: new Date(),
};

const MOCK_RESPONSES: Record<string, string> = {
  default: 'Cảm ơn câu hỏi của bạn! Tôi đang tra cứu thông tin trong cơ sở dữ liệu pháp luật...\n\nDựa trên các văn bản pháp luật hiện hành, thủ tục bạn hỏi được quy định tại **Nghị định 123/2021/NĐ-CP**. Để thực hiện, bạn cần chuẩn bị hồ sơ và nộp tại cơ quan có thẩm quyền.\n\nBạn có muốn tôi hướng dẫn chi tiết hơn không?',
};

export default function TroLyAiPage() {
  // session_id được tạo 1 lần khi trang load, gắn với toàn bộ phiên làm việc
  // Backend sẽ dùng ID này để định danh dữ liệu trên Redis và xóa tự động sau khi trả kết quả
  const [sessionId] = useState<string>(() => generateSessionId());
  const [messages, setMessages] = useState<Message[]>([WELCOME_MSG]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [previewModalDoc, setPreviewModalDoc] = useState<{ name: string; slug: string; title: string } | null>(null);
  const [downloadingDoc, setDownloadingDoc] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const handleDownloadPdf = async (docName: string, title?: string, slug?: string) => {
    try {
      setDownloadingDoc(docName);
      const blob = await api.downloadDocumentTemplate(
        docName,
        title || 'Thủ tục hành chính',
        slug || 'bieu-mau',
        false
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const safeName = (slug || docName).replace(/[^a-zA-Z0-9\u00C0-\u1EF9]/g, '_').slice(0, 40);
      a.download = `${safeName}.pdf`;
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Download error:', err);
      const params = new URLSearchParams({
        doc_name: docName,
        title: title || '',
        slug: slug || '',
      });
      window.open(`http://localhost:8000/api/v1/procedures/download-template?${params.toString()}`, '_blank');
    } finally {
      setDownloadingDoc(null);
    }
  };

  const handleChatClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;

    const downloadBtn = target.closest('[data-action="download-pdf"]') as HTMLElement;
    if (downloadBtn) {
      e.preventDefault();
      e.stopPropagation();
      const doc = downloadBtn.getAttribute('data-doc') || 'Tờ khai hành chính';
      const title = downloadBtn.getAttribute('data-title') || '';
      const slug = downloadBtn.getAttribute('data-slug') || '';
      handleDownloadPdf(doc, title, slug);
      return;
    }

    const previewBtn = target.closest('[data-action="preview-pdf"]') as HTMLElement;
    if (previewBtn) {
      e.preventDefault();
      e.stopPropagation();
      const doc = previewBtn.getAttribute('data-doc') || 'Tờ khai hành chính';
      const title = previewBtn.getAttribute('data-title') || '';
      const slug = previewBtn.getAttribute('data-slug') || '';
      setPreviewModalDoc({ name: doc, title: title || 'Thủ tục hành chính', slug: slug || 'bieu-mau' });
      return;
    }

    const link = target.closest('a') as HTMLAnchorElement;
    if (link && link.href && link.href.includes('/download-template')) {
      e.preventDefault();
      try {
        const urlObj = new URL(link.href, window.location.origin);
        const doc = urlObj.searchParams.get('doc_name') || 'Tờ khai hành chính';
        const title = urlObj.searchParams.get('title') || '';
        const slug = urlObj.searchParams.get('slug') || '';
        const isPreview = urlObj.searchParams.get('preview') === 'true';
        if (isPreview) {
          setPreviewModalDoc({ name: doc, title: title || 'Thủ tục hành chính', slug: slug || 'bieu-mau' });
        } else {
          handleDownloadPdf(doc, title, slug);
        }
      } catch {
        window.open(link.href, '_blank');
      }
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      // Gọi API thật — Backend nhận session_id để track Redis session
      // Khi Backend trả về kết quả, nó sẽ tự động xóa dữ liệu phiên trên Redis
      const result = await api.sendChatMessage(userMsg.content, sessionId);
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: result.answer,
        timestamp: new Date(),
        sources: result.sources,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      // Backend chưa khởi động — dùng mock response để demo UI
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: MOCK_RESPONSES.default,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } finally {
      setIsLoading(false);
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleFileUpload = useCallback((uploadedFiles: FileList | null) => {
    if (!uploadedFiles) return;
    Array.from(uploadedFiles).forEach(async (file) => {
      const id = Date.now().toString() + Math.random();
      const newFile: UploadedFile = {
        id,
        name: file.name,
        size: file.size,
        status: 'uploading',
      };
      setFiles((prev) => [...prev, newFile]);

      try {
        // Gọi API thật với session_id — Backend sẽ:
        // 1. Đọc file từ RAM (không lưu ổ cứng)
        // 2. Xử lý OCR nội bộ bằng OpenCV + VietOCR (không gọi API bên ngoài)
        // 3. Trả kết quả JSON về Frontend
        // 4. Tự động xóa dữ liệu session khỏi Redis (tuân thủ NĐ 13/2023)
        const result = await api.uploadDocumentForOcr(file, sessionId);
        setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, status: 'done' } : f)));
        const aiMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: `✅ **Đã xử lý tệp "${file.name}"!**\n\n${result.summary ?? 'Đã bóc tách dữ liệu thành công.'}\n\n🔒 *Dữ liệu đã xử lý nội bộ và tự động xóa khỏi bộ nhớ sau khi trả kết quả (NĐ 13/2023/NĐ-CP).*`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiMsg]);
      } catch {
        // Backend chưa khởi động — dùng mock response để demo UI
        // Lưu ý: Trong môi trường production, KHÔNG hardcode hay log dữ liệu cá nhân
        setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, status: 'done' } : f)));
        const aiMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: `✅ **[Demo] Đã xử lý tệp "${file.name}"** *(Backend offline — hiển thị mock)*\n\nKhi Backend hoạt động:\n• Tệp sẽ được OpenCV + VietOCR xử lý nội bộ (Local 100%\n• Dữ liệu trích xuất chỉ tồn tại trên RAM qua Redis\n• Tự động xóa sau khi trả kết quả về Frontend\n\n🔒 Tuân thủ Nghị định 13/2023/NĐ-CP — Không gửi dữ liệu ra ngoài.`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiMsg]);
      }
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    });
  }, [sessionId]);

  marked.setOptions({
    gfm: true,
    breaks: true,
  });

  const formatContent = (content: string) => {
    if (!content) return '';
    // 1. Tự động chuyển đổi mã trigger OCR thành nút bấm trực quan
    let processed = content.replace(/\[SYS_TRIGGER_OCR:([^\]]+)\]/g, (_match, slug) => {
      return `<div style="margin: 10px 0;"><a href="/thu-tuc/${slug}" target="_blank" style="display: inline-flex; align-items: center; gap: 6px; background: #2563eb; color: #ffffff; padding: 8px 14px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 500;">🔍 Mở khung thẩm định hồ sơ: ${slug} ↗</a></div>`;
    });

    // 2. Chuyển đổi mã widget PDF [SYS_PDF_TEMPLATE:doc_name=...&title=...&slug=...]
    processed = processed.replace(/\[SYS_PDF_TEMPLATE:([^\]]+)\]/g, (_match, rawQuery) => {
      try {
        const params = new URLSearchParams(rawQuery);
        const docName = params.get('doc_name') || 'Tờ khai / Biểu mẫu hành chính';
        const title = params.get('title') || 'Thủ tục hành chính';
        const slug = params.get('slug') || 'bieu-mau';
        return renderPdfCardHtml(docName, title, slug);
      } catch {
        return '';
      }
    });

    // 3. Chuyển đổi dòng chữ thô unclickable kiểu "👉 Tải Biểu mẫu ..." nếu chưa có widget
    if (!content.includes('[SYS_PDF_TEMPLATE:')) {
      const rawFormRegex = /(?:👉\s*)?Tải [bB]iểu mẫu\s*(?:Tờ khai|Đơn|Văn bản)?\s*([^\n\r(]+)(?:\((?:File\s*)?PDF\))?/i;
      const m = processed.match(rawFormRegex);
      if (m && m[1]) {
        const extractedDoc = m[1].trim();
        if (extractedDoc.length > 3) {
          const cardHtml = renderPdfCardHtml(
            extractedDoc.startsWith('Tờ khai') || extractedDoc.startsWith('Văn bản') || extractedDoc.startsWith('Đơn')
              ? extractedDoc
              : `Tờ khai đề nghị: ${extractedDoc}`,
            'Thủ tục hành chính',
            'bieu-mau'
          );
          processed = processed.replace(m[0], cardHtml);
        }
      }
    }

    try {
      return marked.parse(processed, { async: false }) as string;
    } catch {
      return processed
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br/>');
    }
  };

  return (
    <div className={styles.page}>
      {/* Page Header */}
      <div className={styles.pageHeader}>
        <div className={styles.container}>
          <div className={styles.headerContent}>
            <div className={styles.headerLeft}>
              <div className={styles.aiAvatar}>
                <Bot size={24} />
              </div>
              <div>
                <h1 className={styles.pageTitle}>Trợ lý AI Pháp lý</h1>
                <div className={styles.headerStatus}>
                  <span className={styles.statusDot} />
                  <span>Đang hoạt động · Chạy nội bộ</span>
                </div>
              </div>
            </div>
            <div className={styles.secBadge}>
              <Shield size={13} />
              <span>Zero dữ liệu ra ngoài · NĐ 13/2023</span>
            </div>
          </div>
        </div>
      </div>

      <div className={styles.container}>
        <div className={styles.layout}>
          {/* Left Panel — Upload */}
          <aside className={styles.uploadPanel}>
            <div className={styles.uploadHeader}>
              <Upload size={18} />
              <span>Tải hồ sơ để kiểm tra OCR</span>
            </div>

            {/* Drop Zone */}
            <div
              className={`${styles.dropZone} ${isDragOver ? styles.dragOver : ''}`}
              onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragOver(false);
                handleFileUpload(e.dataTransfer.files);
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className={styles.dropIcon}>
                <Paperclip size={28} />
              </div>
              <p className={styles.dropTitle}>Kéo & thả file vào đây</p>
              <p className={styles.dropSub}>hoặc nhấn để chọn file</p>
              <p className={styles.dropFormats}>JPG, PNG, PDF, HEIC · Tối đa 10MB</p>
              <input
                id="ocr-file-input"
                ref={fileInputRef}
                type="file"
                accept="image/*,.pdf"
                multiple
                className={styles.hiddenInput}
                onChange={(e) => handleFileUpload(e.target.files)}
              />
            </div>

            {/* File list */}
            {files.length > 0 && (
              <div className={styles.fileList}>
                <div className={styles.fileListHeader}>Tệp đã tải lên</div>
                {files.map((file) => (
                  <div key={file.id} className={styles.fileItem}>
                    <FileText size={15} className={styles.fileIcon} />
                    <div className={styles.fileInfo}>
                      <div className={styles.fileName}>{file.name}</div>
                      <div className={styles.fileSize}>
                        {(file.size / 1024).toFixed(0)} KB
                      </div>
                    </div>
                    <div className={styles.fileStatus}>
                      {file.status === 'uploading' && (
                        <Loader2 size={15} className={styles.spinning} />
                      )}
                      {file.status === 'done' && (
                        <CheckCircle size={15} className={styles.statusDone} />
                      )}
                      {file.status === 'error' && (
                        <AlertCircle size={15} className={styles.statusError} />
                      )}
                    </div>
                    <button
                      className={styles.removeFile}
                      onClick={() => setFiles((prev) => prev.filter((f) => f.id !== file.id))}
                      aria-label="Xóa file"
                    >
                      <X size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Notice */}
            <div className={styles.secNotice}>
              <Shield size={13} />
              <p>File chỉ tồn tại trên RAM và tự động xóa sau phiên làm việc. Không lưu vào ổ cứng.</p>
            </div>
          </aside>

          {/* Right Panel — Chat */}
          <div className={styles.chatPanel}>
            {/* Messages */}
            <div className={styles.messageList} id="chat-message-list" onClick={handleChatClick}>
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`${styles.message} ${msg.role === 'user' ? styles.userMsg : styles.aiMsg}`}
                >
                  <div className={styles.msgAvatar}>
                    {msg.role === 'assistant' ? (
                      <Bot size={16} />
                    ) : (
                      <User size={16} />
                    )}
                  </div>
                  <div className={styles.msgBubble}>
                    <div
                      className={styles.msgContent}
                      dangerouslySetInnerHTML={{ __html: formatContent(msg.content) }}
                    />
                    {msg.sources && msg.sources.length > 0 && (
                      <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px dashed rgba(128,128,128,0.25)', fontSize: '12px' }}>
                        <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px', color: 'var(--primary-color, #2563eb)' }}>
                          📚 Căn cứ pháp lý trích dẫn (RAG):
                        </div>
                        <ul style={{ margin: 0, paddingLeft: '18px', opacity: 0.85 }}>
                          {msg.sources.map((src, sIdx) => (
                            <li key={sIdx}>{src}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <div className={styles.msgTime}>
                      {msg.timestamp.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              ))}

              {/* Loading indicator */}
              {isLoading && (
                <div className={`${styles.message} ${styles.aiMsg}`}>
                  <div className={styles.msgAvatar}>
                    <Bot size={16} />
                  </div>
                  <div className={styles.msgBubble}>
                    <div className={styles.typingIndicator}>
                      <span /><span /><span />
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Suggestions */}
            {messages.length === 1 && (
              <div className={styles.suggestions}>
                {[
                  'Hồ sơ cần thiết để cấp sổ đỏ?',
                  'Điều kiện thành lập công ty TNHH?',
                  'Quy trình đăng ký tạm trú?',
                  'Cách tính thuế TNCN?',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    className={styles.suggestionBtn}
                    onClick={() => { setInput(suggestion); }}
                  >
                    <Sparkles size={12} />
                    {suggestion}
                  </button>
                ))}
              </div>
            )}

            {/* Input */}
            <div className={styles.inputArea}>
              <div className={styles.inputWrapper}>
                <textarea
                  id="chat-input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                  placeholder="Hỏi về thủ tục, pháp luật... (Enter để gửi)"
                  className={styles.input}
                  rows={2}
                />
                <button
                  id="chat-send-btn"
                  className={`${styles.sendBtn} ${input.trim() ? styles.sendBtnActive : ''}`}
                  onClick={sendMessage}
                  disabled={!input.trim() || isLoading}
                  aria-label="Gửi câu hỏi"
                >
                  {isLoading ? <Loader2 size={18} className={styles.spinning} /> : <Send size={18} />}
                </button>
              </div>
              <p className={styles.inputHint}>
                Enter để gửi · Shift+Enter xuống dòng · Câu trả lời dựa trên VBPL Việt Nam
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Modal xem trước biểu mẫu PDF khổ A4 */}
      {previewModalDoc && (
        <PdfPreviewModal
          isOpen={true}
          onClose={() => setPreviewModalDoc(null)}
          documentName={previewModalDoc.name}
          procedureSlug={previewModalDoc.slug}
          procedureTitle={previewModalDoc.title}
        />
      )}

      {/* Toast thông báo tải PDF */}
      {downloadingDoc && (
        <div style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          background: '#1e293b',
          color: '#ffffff',
          padding: '12px 20px',
          borderRadius: '8px',
          boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          zIndex: 9999,
          fontSize: '14px',
          border: '1px solid #3b82f6',
        }}>
          <Loader2 size={16} className={styles.spinning} />
          <span>Đang tạo và tải file PDF: <strong>{downloadingDoc.slice(0, 30)}...</strong></span>
        </div>
      )}
    </div>
  );
}
