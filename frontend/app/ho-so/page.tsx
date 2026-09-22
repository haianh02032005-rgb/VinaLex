'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  FolderOpen, Upload, Clock, CheckCircle, AlertCircle,
  Loader2, Download, Bot, Eye, Trash2, Plus, LogIn,
} from 'lucide-react';
import styles from './page.module.css';

// ── Types ──
interface SavedProcedure {
  id: string | number;
  title?: string;
  procedure_title?: string;
  progress: number;
  status: string;
  due_date?: string | null;
  dueDate?: string | null;
  created_at?: string;
}

interface OcrFile {
  id: string;
  name: string;
  type: string;
  size: number;
  status: string;
  uploadedAt: string;
  docType: string | null;
}

// ── Mock data (fallback khi backend offline) ──
const MOCK_FILES: OcrFile[] = [
  { id: '1', name: 'CCCD_MatTruoc.jpg', type: 'image/jpeg', size: 524288, status: 'done', uploadedAt: '2024-06-15T10:30:00', docType: 'Căn cước công dân (Mặt trước)' },
  { id: '2', name: 'HopDong_MuaBan.pdf', type: 'application/pdf', size: 1048576, status: 'done', uploadedAt: '2024-06-15T10:31:00', docType: 'Hợp đồng mua bán' },
  { id: '3', name: 'SoHoKhau.jpg', type: 'image/jpeg', size: 768000, status: 'processing', uploadedAt: '2024-06-15T10:32:00', docType: null },
];

const MOCK_PROCEDURES_SAVED: SavedProcedure[] = [
  { id: '1', title: 'Cấp giấy chứng nhận quyền sử dụng đất', progress: 60, status: 'in_progress', dueDate: '2024-07-15' },
  { id: '2', title: 'Đăng ký tạm trú', progress: 100, status: 'completed', dueDate: '2024-06-20' },
  { id: '3', title: 'Đăng ký thành lập công ty TNHH', progress: 20, status: 'pending', dueDate: '2024-08-01' },
];

const STATUS_CONFIG: Record<string, { label: string; icon: typeof Clock; color: string }> = {
  done: { label: 'Hoàn thành', icon: CheckCircle, color: '#10B981' },
  processing: { label: 'Đang xử lý', icon: Loader2, color: '#F59E0B' },
  error: { label: 'Lỗi', icon: AlertCircle, color: '#EF4444' },
  pending: { label: 'Chờ xử lý', icon: Clock, color: '#94A3B8' },
  in_progress: { label: 'Đang thực hiện', icon: Clock, color: '#4F7FFA' },
  completed: { label: 'Hoàn tất', icon: CheckCircle, color: '#10B981' },
};

// ── Helper: lấy token từ localStorage ──
function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('vinalex_access_token');
}

// ── Fetch user procedures từ backend ──
async function fetchUserProcedures(token: string): Promise<SavedProcedure[]> {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  const res = await fetch(`${API_BASE}/auth/me/procedures`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export default function HoSoPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'files' | 'procedures'>('procedures');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [savedProcs, setSavedProcs] = useState<SavedProcedure[]>(MOCK_PROCEDURES_SAVED);
  const [loadingProcs, setLoadingProcs] = useState(false);
  const [usingMock, setUsingMock] = useState(false);

  // Kiểm tra trạng thái đăng nhập khi component mount & lắng nghe event
  useEffect(() => {
    const updateAuthState = () => {
      const token = getToken();
      const email = localStorage.getItem('vinalex_user_email') || '';
      if (token) {
        setIsLoggedIn(true);
        setUserEmail(email);
        loadUserProcedures(token);
      } else {
        setIsLoggedIn(false);
        setUserEmail('');
        setSavedProcs(MOCK_PROCEDURES_SAVED);
        setUsingMock(true);
      }
    };

    updateAuthState();
    window.addEventListener('vinalex_auth_change', updateAuthState);
    return () => window.removeEventListener('vinalex_auth_change', updateAuthState);
  }, []);

  const loadUserProcedures = async (token: string) => {
    setLoadingProcs(true);
    try {
      const procs = await fetchUserProcedures(token);
      if (procs && procs.length > 0) {
        setSavedProcs(procs);
        setUsingMock(false);
      } else {
        // Tài khoản mới chưa có hồ sơ -> hiển thị rỗng hoặc mock gợi ý
        setSavedProcs([]);
        setUsingMock(false);
      }
    } catch {
      // Backend offline hoặc chưa có db -> dùng mock
      setSavedProcs(MOCK_PROCEDURES_SAVED);
      setUsingMock(true);
    } finally {
      setLoadingProcs(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('vinalex_access_token');
    localStorage.removeItem('vinalex_user_email');
    localStorage.removeItem('vinalex_user_name');
    window.dispatchEvent(new Event('vinalex_auth_change'));
    setIsLoggedIn(false);
    setUserEmail('');
    setSavedProcs(MOCK_PROCEDURES_SAVED);
    setUsingMock(true);
  };

  const handleDeleteProcedure = async (id: string | number) => {
    const token = getToken();
    if (token && typeof id === 'number') {
      try {
        await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/auth/me/procedures/${id}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch {
        // Silently ignore if backend offline
      }
    }
    setSavedProcs((prev) => prev.filter((p) => p.id !== id));
  };


  // Tính stats dựa trên dữ liệu thực
  const statsData = [
    {
      label: 'Hồ sơ đang xử lý',
      value: String(savedProcs.filter((p) => p.status === 'in_progress' || p.status === 'pending').length),
      icon: '📋',
      color: '#4F7FFA',
    },
    {
      label: 'Hoàn thành',
      value: String(savedProcs.filter((p) => p.status === 'completed' || p.status === 'done').length),
      icon: '✅',
      color: '#10B981',
    },
    {
      label: 'Tài liệu đã OCR',
      value: String(MOCK_FILES.filter((f) => f.status === 'done').length),
      icon: '📄',
      color: '#06B6D4',
    },
    { label: 'Biểu mẫu đã tải', value: '5', icon: '⬇️', color: '#8B5CF6' },
  ];

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.pageHeader}>
        <div className={styles.container}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h1 className={styles.pageTitle}>
                <FolderOpen size={28} />
                Hồ sơ của tôi
              </h1>
              <p className={styles.pageSubtitle}>Quản lý tiến trình hồ sơ và tài liệu đã xử lý OCR</p>
            </div>
            {/* Auth state indicator */}
            {isLoggedIn ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{userEmail}</span>
                <button
                  onClick={handleLogout}
                  style={{
                    padding: '0.4rem 0.9rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle)',
                    background: 'transparent',
                    color: 'var(--text-muted)',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                  }}
                >
                  Đăng xuất
                </button>
              </div>
            ) : (
              <Link
                href="/dang-nhap"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.5rem 1rem',
                  borderRadius: '10px',
                  background: 'var(--gradient-primary)',
                  color: '#fff',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  textDecoration: 'none',
                }}
              >
                <LogIn size={15} /> Đăng nhập để đồng bộ
              </Link>
            )}
          </div>

          {/* Demo notice khi dùng mock */}
          {usingMock && (
            <div style={{
              marginTop: '0.75rem',
              padding: '0.6rem 1rem',
              background: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid rgba(245, 158, 11, 0.2)',
              borderRadius: '8px',
              fontSize: '0.8rem',
              color: '#fbbf24',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}>
              <AlertCircle size={14} />
              {isLoggedIn
                ? 'Đang hiển thị dữ liệu mẫu — Backend chưa kết nối.'
                : 'Đăng nhập để xem hồ sơ thực tế của bạn. Hiện đang hiển thị dữ liệu mẫu.'}
            </div>
          )}
        </div>
      </div>

      <div className={styles.container}>
        {/* Stats Row */}
        <div className={styles.statsRow}>
          {statsData.map((stat, i) => (
            <div key={i} className={styles.statCard} style={{ borderColor: `${stat.color}25` }}>
              <span className={styles.statIcon}>{stat.icon}</span>
              <span className={styles.statValue} style={{ color: stat.color }}>{stat.value}</span>
              <span className={styles.statLabel}>{stat.label}</span>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className={styles.tabs}>
          <button
            id="tab-procedures"
            className={`${styles.tab} ${activeTab === 'procedures' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('procedures')}
          >
            <Clock size={15} />
            Tiến trình hồ sơ
          </button>
          <button
            id="tab-files"
            className={`${styles.tab} ${activeTab === 'files' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('files')}
          >
            <FolderOpen size={15} />
            Tài liệu đã OCR
          </button>
        </div>

        {/* Tab: Procedures */}
        {activeTab === 'procedures' && (
          <div className={styles.tabContent}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>Hồ sơ đang theo dõi</h2>
              <Link href="/thu-tuc" className={styles.addBtn}>
                <Plus size={15} /> Thêm hồ sơ mới
              </Link>
            </div>

            {loadingProcs ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '2rem', color: 'var(--text-muted)' }}>
                <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
                Đang tải danh sách hồ sơ...
              </div>
            ) : (
              <div className={styles.procedureList}>
                {savedProcs.map((proc) => {
                  const title = proc.procedure_title ?? proc.title ?? 'Thủ tục hành chính';
                  const dueDate = proc.due_date ?? proc.dueDate;
                  const statusCfg = STATUS_CONFIG[proc.status] ?? STATUS_CONFIG.pending;
                  const StatusIcon = statusCfg.icon;
                  return (
                    <div key={proc.id} className={styles.procedureCard}>
                      <div className={styles.procCardLeft}>
                        <div className={styles.procTitle}>{title}</div>
                        <div className={styles.progressRow}>
                          <div className={styles.progressBar}>
                            <div
                              className={styles.progressFill}
                              style={{
                                width: `${proc.progress}%`,
                                background: proc.progress === 100
                                  ? 'linear-gradient(90deg, #10B981, #34D399)'
                                  : 'var(--gradient-primary)',
                              }}
                            />
                          </div>
                          <span className={styles.progressPct}>{proc.progress}%</span>
                        </div>
                        <div className={styles.procMeta}>
                          <span style={{ color: statusCfg.color }} className={styles.procStatus}>
                            <StatusIcon size={13} />
                            {statusCfg.label}
                          </span>
                          {dueDate && (
                            <span className={styles.procDue}>
                              <Clock size={12} />
                              Hạn: {new Date(dueDate).toLocaleDateString('vi-VN')}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className={styles.procCardRight} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        <Link href="/tro-ly-ai" className={styles.procActionBtn}>
                          <Bot size={14} />
                          Hỏi AI
                        </Link>
                        <button
                          onClick={() => handleDeleteProcedure(proc.id)}
                          className={styles.procDeleteBtn}
                          title="Xóa khỏi danh sách theo dõi"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab: Files */}
        {activeTab === 'files' && (
          <div className={styles.tabContent}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>Tài liệu đã xử lý OCR</h2>
              <Link href="/tro-ly-ai" className={styles.addBtn}>
                <Upload size={15} /> Tải tài liệu mới
              </Link>
            </div>
            <div className={styles.fileTable}>
              <div className={styles.tableHeader}>
                <span>Tên tài liệu</span>
                <span>Loại</span>
                <span>Kích thước</span>
                <span>Trạng thái</span>
                <span>Thời gian</span>
                <span>Thao tác</span>
              </div>
              {MOCK_FILES.map((file) => {
                const cfg = STATUS_CONFIG[file.status] ?? STATUS_CONFIG.pending;
                const Icon = cfg.icon;
                return (
                  <div key={file.id} className={styles.tableRow}>
                    <div className={styles.fileName}>
                      <span className={styles.fileExt}>{file.type.includes('pdf') ? '📄' : '🖼️'}</span>
                      {file.name}
                    </div>
                    <span className={styles.fileType}>{file.docType || '—'}</span>
                    <span className={styles.fileSize}>{(file.size / 1024).toFixed(0)} KB</span>
                    <span className={styles.fileStatus} style={{ color: cfg.color }}>
                      <Icon size={13} />
                      {cfg.label}
                    </span>
                    <span className={styles.fileDate}>
                      {new Date(file.uploadedAt).toLocaleString('vi-VN', {
                        hour: '2-digit', minute: '2-digit',
                        day: '2-digit', month: '2-digit',
                      })}
                    </span>
                    <div className={styles.fileActions}>
                      <button className={styles.actionBtn} title="Xem kết quả OCR">
                        <Eye size={14} />
                      </button>
                      <button className={styles.actionBtn} title="Tải xuống">
                        <Download size={14} />
                      </button>
                      <button className={`${styles.actionBtn} ${styles.actionBtnDanger}`} title="Xóa">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
