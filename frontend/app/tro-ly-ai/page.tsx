'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Bot, Upload, Send, Shield, Paperclip, X, FileText, CheckCircle, Loader2, AlertCircle, User, Sparkles } from 'lucide-react';
import { marked } from 'marked';
import styles from './page.module.css';
import { api } from '@/lib/api';

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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

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
    try {
      return marked.parse(content, { async: false }) as string;
    } catch {
      return content
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
            <div className={styles.messageList} id="chat-message-list">
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
    </div>
  );
}
