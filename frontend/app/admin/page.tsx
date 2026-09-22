'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  LayoutDashboard, FileText, Database, LogOut, RefreshCw,
  Plus, Pencil, Trash2, Eye, EyeOff, CheckCircle, XCircle,
  AlertCircle, Loader2, BarChart3, Globe, Shield, ChevronRight,
  BookOpen, Upload, Search, X,
} from 'lucide-react';
import styles from './page.module.css';
import { api } from '@/lib/api';

// ── Types ──
interface Procedure {
  id: number;
  slug: string;
  title: string;
  category: string;
  level: string;
  view_count: number;
  is_published: boolean;
  updated_at: string;
}

interface Stats {
  procedures: { total: number; published: number; draft: number };
  total_views: number;
  vector_db: { status: string };
}

type Tab = 'dashboard' | 'procedures' | 'sync';

// ── Mock data khi backend offline ──
const MOCK_STATS: Stats = {
  procedures: { total: 12, published: 10, draft: 2 },
  total_views: 25430,
  vector_db: { status: 'demo_mode' },
};

const MOCK_PROCEDURES: Procedure[] = [
  { id: 1, slug: 'cap-so-do', title: 'Cấp giấy chứng nhận QSDĐ (Sổ đỏ)', category: 'Đất đai', level: 'Cấp huyện', view_count: 5320, is_published: true, updated_at: '2024-12-01T00:00:00' },
  { id: 2, slug: 'dang-ky-kinh-doanh', title: 'Đăng ký thành lập hộ kinh doanh', category: 'Doanh nghiệp', level: 'Cấp huyện', view_count: 4100, is_published: true, updated_at: '2024-11-20T00:00:00' },
  { id: 3, slug: 'dang-ky-tam-tru', title: 'Đăng ký tạm trú', category: 'Hộ khẩu', level: 'Cấp xã/phường', view_count: 3800, is_published: true, updated_at: '2024-11-15T00:00:00' },
  { id: 4, slug: 'cap-cccd', title: 'Cấp thẻ Căn cước công dân', category: 'Hộ khẩu', level: 'Cấp tỉnh', view_count: 3200, is_published: false, updated_at: '2024-10-10T00:00:00' },
];

// ── Login Screen ──
function LoginScreen({ onLogin }: { onLogin: (key: string) => void }) {
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!key.trim()) return;
    setLoading(true);
    setError('');
    try {
      // Thử gọi API stats để xác nhận key
      await api.adminGetStats(key.trim());
      onLogin(key.trim());
    } catch {
      // Backend offline → vẫn cho vào với key mặc định để demo
      if (key.trim() === 'vinalex-admin-2024') {
        onLogin(key.trim());
      } else {
        setError('Admin key không đúng. Key demo: vinalex-admin-2024');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.loginPage}>
      <div className={styles.loginCard}>
        <div className={styles.loginLogo}>
          <Shield size={32} />
        </div>
        <h1 className={styles.loginTitle}>VinaLex Admin</h1>
        <p className={styles.loginSub}>Nhập Admin Key để truy cập hệ thống quản trị</p>
        <form onSubmit={handleSubmit} className={styles.loginForm}>
          <input
            id="admin-key-input"
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="Nhập Admin Key..."
            className={styles.loginInput}
            autoFocus
          />
          {error && (
            <div className={styles.loginError}>
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}
          <button
            id="admin-login-btn"
            type="submit"
            className={styles.loginBtn}
            disabled={!key.trim() || loading}
          >
            {loading ? <Loader2 size={16} className={styles.spinning} /> : <Shield size={16} />}
            {loading ? 'Đang xác thực...' : 'Truy cập Admin'}
          </button>
        </form>
        <p className={styles.loginHint}>
          Key demo: <code>vinalex-admin-2024</code>
        </p>
      </div>
    </div>
  );
}

// ── Main Dashboard ──
export default function AdminPage() {
  const [adminKey, setAdminKey] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

  // Stats
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // Procedures
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [procLoading, setProcLoading] = useState(false);
  const [procSearch, setProcSearch] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  // Sync
  const [syncContent, setSyncContent] = useState('');
  const [syncSource, setSyncSource] = useState('');
  const [syncDocType, setSyncDocType] = useState('Văn bản pháp luật');
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncResult, setSyncResult] = useState<{ success: boolean; message: string; chunks?: number } | null>(null);
  const [dbStatus, setDbStatus] = useState<{ status: string } | null>(null);

  // ── Check stored key ──
  useEffect(() => {
    const stored = localStorage.getItem('vinalex_admin_key');
    if (stored) setAdminKey(stored);
  }, []);

  const handleLogin = (key: string) => {
    localStorage.setItem('vinalex_admin_key', key);
    setAdminKey(key);
  };

  const handleLogout = () => {
    localStorage.removeItem('vinalex_admin_key');
    setAdminKey(null);
  };

  // ── Load stats ──
  const loadStats = useCallback(async () => {
    if (!adminKey) return;
    setStatsLoading(true);
    try {
      const data = await api.adminGetStats(adminKey);
      setStats(data);
    } catch {
      setStats(MOCK_STATS);
    } finally {
      setStatsLoading(false);
    }
  }, [adminKey]);

  // ── Load procedures ──
  const loadProcedures = useCallback(async () => {
    if (!adminKey) return;
    setProcLoading(true);
    try {
      const data = await api.adminGetAllProcedures(adminKey);
      setProcedures((data.items as Procedure[]) ?? []);
    } catch {
      setProcedures(MOCK_PROCEDURES);
    } finally {
      setProcLoading(false);
    }
  }, [adminKey]);

  useEffect(() => {
    if (adminKey) {
      loadStats();
      loadProcedures();
    }
  }, [adminKey, loadStats, loadProcedures]);

  // ── Load DB status ──
  const loadDbStatus = useCallback(async () => {
    if (!adminKey) return;
    try {
      const data = await api.adminGetSyncStatus(adminKey);
      setDbStatus(data);
    } catch {
      setDbStatus({ status: 'offline (demo mode)' });
    }
  }, [adminKey]);

  useEffect(() => {
    if (activeTab === 'sync') loadDbStatus();
  }, [activeTab, loadDbStatus]);

  // ── Delete procedure ──
  const handleDelete = async (slug: string) => {
    if (!adminKey) return;
    try {
      await api.adminDeleteProcedure(adminKey, slug);
      setProcedures((prev) => prev.filter((p) => p.slug !== slug));
    } catch {
      setProcedures((prev) => prev.filter((p) => p.slug !== slug)); // demo
    }
    setDeleteTarget(null);
  };

  // ── Sync Vector DB ──
  const handleSync = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminKey || !syncContent.trim() || !syncSource.trim()) return;
    setSyncLoading(true);
    setSyncResult(null);
    try {
      const result = await api.adminSyncLegalDoc(adminKey, syncContent, syncSource, syncDocType);
      setSyncResult({ success: true, message: result.message, chunks: result.chunks_synced });
      setSyncContent('');
      setSyncSource('');
    } catch {
      setSyncResult({ success: false, message: 'Backend offline — không thể đồng bộ trong chế độ demo.' });
    } finally {
      setSyncLoading(false);
    }
  };

  // ── Filter procedures ──
  const filteredProcedures = procedures.filter((p) =>
    !procSearch || p.title.toLowerCase().includes(procSearch.toLowerCase()) || p.category.toLowerCase().includes(procSearch.toLowerCase())
  );

  if (!adminKey) {
    return <LoginScreen onLogin={handleLogin} />;
  }

  return (
    <div className={styles.adminLayout}>
      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <div className={styles.sidebarLogo}>
            <Shield size={20} />
          </div>
          <div>
            <div className={styles.sidebarTitle}>VinaLex</div>
            <div className={styles.sidebarSub}>Admin CMS</div>
          </div>
        </div>

        <nav className={styles.sidebarNav}>
          {([
            { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
            { id: 'procedures', label: 'Thủ tục', icon: FileText },
            { id: 'sync', label: 'Vector DB', icon: Database },
          ] as { id: Tab; label: string; icon: React.ElementType }[]).map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              id={`admin-tab-${id}`}
              className={`${styles.navItem} ${activeTab === id ? styles.navItemActive : ''}`}
              onClick={() => setActiveTab(id)}
            >
              <Icon size={18} />
              <span>{label}</span>
              {activeTab === id && <ChevronRight size={14} className={styles.navArrow} />}
            </button>
          ))}
        </nav>

        <div className={styles.sidebarFooter}>
          <Link href="/" className={styles.navItem} style={{ textDecoration: 'none' }}>
            <Globe size={18} />
            <span>Xem trang chủ</span>
          </Link>
          <button id="admin-logout-btn" className={`${styles.navItem} ${styles.navItemDanger}`} onClick={handleLogout}>
            <LogOut size={18} />
            <span>Đăng xuất</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className={styles.mainContent}>

        {/* ── TAB: Dashboard ── */}
        {activeTab === 'dashboard' && (
          <div className={styles.tabContent}>
            <div className={styles.pageHeader}>
              <h1 className={styles.pageTitle}>Dashboard</h1>
              <button className={styles.refreshBtn} onClick={loadStats} disabled={statsLoading}>
                <RefreshCw size={15} className={statsLoading ? styles.spinning : ''} />
                Làm mới
              </button>
            </div>

            {/* Stats Grid */}
            <div className={styles.statsGrid}>
              {[
                {
                  icon: FileText,
                  label: 'Tổng thủ tục',
                  value: stats?.procedures.total ?? '–',
                  sub: `${stats?.procedures.published ?? 0} đã đăng · ${stats?.procedures.draft ?? 0} nháp`,
                  color: '#6366f1',
                },
                {
                  icon: Eye,
                  label: 'Tổng lượt xem',
                  value: stats ? stats.total_views.toLocaleString('vi-VN') : '–',
                  sub: 'Tích lũy toàn hệ thống',
                  color: '#06b6d4',
                },
                {
                  icon: Database,
                  label: 'Vector DB',
                  value: stats?.vector_db.status === 'connected' ? 'Online' : 'Offline',
                  sub: 'Qdrant · vinalex_legal_docs',
                  color: stats?.vector_db.status === 'connected' ? '#10b981' : '#f59e0b',
                },
                {
                  icon: BarChart3,
                  label: 'Đã đăng',
                  value: stats ? `${Math.round((stats.procedures.published / (stats.procedures.total || 1)) * 100)}%` : '–',
                  sub: 'Tỷ lệ nội dung hoạt động',
                  color: '#8b5cf6',
                },
              ].map(({ icon: Icon, label, value, sub, color }) => (
                <div key={label} className={styles.statCard}>
                  <div className={styles.statIcon} style={{ background: `${color}20`, color }}>
                    <Icon size={22} />
                  </div>
                  <div className={styles.statBody}>
                    <div className={styles.statValue}>{value}</div>
                    <div className={styles.statLabel}>{label}</div>
                    <div className={styles.statSub}>{sub}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Quick Actions */}
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>Thao tác nhanh</h2>
            </div>
            <div className={styles.quickActions}>
              <button
                className={styles.quickAction}
                onClick={() => { setActiveTab('procedures'); }}
              >
                <Plus size={20} />
                <span>Thêm thủ tục mới</span>
              </button>
              <button
                className={styles.quickAction}
                onClick={() => setActiveTab('sync')}
              >
                <Upload size={20} />
                <span>Đồng bộ Vector DB</span>
              </button>
              <Link href="/thu-tuc" className={styles.quickAction}>
                <BookOpen size={20} />
                <span>Xem Knowledge Hub</span>
              </Link>
            </div>
          </div>
        )}

        {/* ── TAB: Procedures ── */}
        {activeTab === 'procedures' && (
          <div className={styles.tabContent}>
            <div className={styles.pageHeader}>
              <h1 className={styles.pageTitle}>Quản lý Thủ tục</h1>
              <div className={styles.headerActions}>
                <button className={styles.refreshBtn} onClick={loadProcedures} disabled={procLoading}>
                  <RefreshCw size={15} className={procLoading ? styles.spinning : ''} />
                  Làm mới
                </button>
                <Link href="/admin/procedure-form" className={styles.primaryBtn}>
                  <Plus size={16} />
                  Thêm mới
                </Link>
              </div>
            </div>

            {/* Search */}
            <div className={styles.tableSearch}>
              <Search size={16} className={styles.tableSearchIcon} />
              <input
                id="admin-proc-search"
                type="text"
                value={procSearch}
                onChange={(e) => setProcSearch(e.target.value)}
                placeholder="Tìm theo tên, danh mục..."
                className={styles.tableSearchInput}
              />
              {procSearch && (
                <button onClick={() => setProcSearch('')} className={styles.tableSearchClear}>
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Table */}
            <div className={styles.tableWrapper}>
              {procLoading ? (
                <div className={styles.loadingState}>
                  <Loader2 size={28} className={styles.spinning} />
                  <span>Đang tải dữ liệu...</span>
                </div>
              ) : (
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Tiêu đề</th>
                      <th>Danh mục</th>
                      <th>Cấp</th>
                      <th>Lượt xem</th>
                      <th>Trạng thái</th>
                      <th>Cập nhật</th>
                      <th>Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredProcedures.map((proc) => (
                      <tr key={proc.id}>
                        <td>
                          <div className={styles.procTitle}>
                            <span>{proc.title}</span>
                            <code className={styles.procSlug}>{proc.slug}</code>
                          </div>
                        </td>
                        <td><span className={styles.catBadge}>{proc.category}</span></td>
                        <td><span className={styles.levelBadge}>{proc.level}</span></td>
                        <td>{proc.view_count.toLocaleString('vi-VN')}</td>
                        <td>
                          {proc.is_published ? (
                            <span className={styles.badgePublished}>
                              <CheckCircle size={12} /> Đã đăng
                            </span>
                          ) : (
                            <span className={styles.badgeDraft}>
                              <EyeOff size={12} /> Nháp
                            </span>
                          )}
                        </td>
                        <td className={styles.dateCell}>
                          {new Date(proc.updated_at).toLocaleDateString('vi-VN')}
                        </td>
                        <td>
                          <div className={styles.actionBtns}>
                            <Link
                              href={`/admin/procedure-form?slug=${proc.slug}`}
                              className={styles.editBtn}
                              title="Sửa"
                            >
                              <Pencil size={14} />
                            </Link>
                            <Link
                              href={`/thu-tuc/${proc.slug}`}
                              target="_blank"
                              className={styles.viewBtn}
                              title="Xem"
                            >
                              <Eye size={14} />
                            </Link>
                            <button
                              className={styles.deleteBtn}
                              title="Xóa"
                              onClick={() => setDeleteTarget(proc.slug)}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filteredProcedures.length === 0 && (
                      <tr>
                        <td colSpan={7} className={styles.emptyRow}>
                          Không tìm thấy thủ tục nào
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              )}
            </div>

            {/* Delete Confirm Modal */}
            {deleteTarget && (
              <div className={styles.modalOverlay}>
                <div className={styles.modal}>
                  <div className={styles.modalIcon}><Trash2 size={24} /></div>
                  <h3 className={styles.modalTitle}>Xác nhận xóa</h3>
                  <p className={styles.modalDesc}>
                    Bạn có chắc muốn xóa thủ tục <strong>{deleteTarget}</strong>?
                    Hành động này không thể hoàn tác.
                  </p>
                  <div className={styles.modalActions}>
                    <button className={styles.cancelBtn} onClick={() => setDeleteTarget(null)}>
                      Hủy
                    </button>
                    <button
                      id="confirm-delete-btn"
                      className={styles.confirmDeleteBtn}
                      onClick={() => handleDelete(deleteTarget)}
                    >
                      <Trash2 size={14} /> Xóa
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── TAB: Sync Vector DB ── */}
        {activeTab === 'sync' && (
          <div className={styles.tabContent}>
            <div className={styles.pageHeader}>
              <h1 className={styles.pageTitle}>Đồng bộ Vector DB</h1>
              <div className={styles.dbStatusBadge} data-status={dbStatus?.status}>
                <span className={styles.dbDot} />
                <span>
                  {dbStatus
                    ? `Qdrant · ${dbStatus.status}`
                    : 'Đang kiểm tra...'}
                </span>
              </div>
            </div>

            <p className={styles.syncDesc}>
              Nhập toàn văn văn bản pháp luật để đưa vào cơ sở kiến thức AI.
              Hệ thống sẽ tự động phân tách, embed và lưu vào Qdrant Vector DB.
              Chatbot RAG sẽ có thể tra cứu ngay lập tức.
            </p>

            <form onSubmit={handleSync} className={styles.syncForm}>
              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label htmlFor="sync-source" className={styles.formLabel}>
                    Tên / Mã số văn bản <span className={styles.required}>*</span>
                  </label>
                  <input
                    id="sync-source"
                    type="text"
                    value={syncSource}
                    onChange={(e) => setSyncSource(e.target.value)}
                    placeholder="VD: Nghị định 13/2023/NĐ-CP"
                    className={styles.formInput}
                    required
                  />
                </div>
                <div className={styles.formGroup}>
                  <label htmlFor="sync-doc-type" className={styles.formLabel}>
                    Loại văn bản
                  </label>
                  <select
                    id="sync-doc-type"
                    value={syncDocType}
                    onChange={(e) => setSyncDocType(e.target.value)}
                    className={styles.formSelect}
                  >
                    {['Văn bản pháp luật', 'Nghị định', 'Thông tư', 'Luật', 'Quyết định', 'Thông báo'].map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="sync-content" className={styles.formLabel}>
                  Nội dung văn bản <span className={styles.required}>*</span>
                </label>
                <textarea
                  id="sync-content"
                  value={syncContent}
                  onChange={(e) => setSyncContent(e.target.value)}
                  placeholder="Dán toàn văn văn bản pháp luật vào đây..."
                  className={styles.formTextarea}
                  rows={14}
                  required
                />
                <div className={styles.charCount}>
                  {syncContent.length.toLocaleString('vi-VN')} ký tự
                  {syncContent.length > 0 && (
                    <span> · ~{Math.ceil(syncContent.length / 400)} chunks dự kiến</span>
                  )}
                </div>
              </div>

              {syncResult && (
                <div className={`${styles.syncResult} ${syncResult.success ? styles.syncSuccess : styles.syncError}`}>
                  {syncResult.success ? <CheckCircle size={16} /> : <XCircle size={16} />}
                  <div>
                    <strong>{syncResult.message}</strong>
                    {syncResult.chunks && (
                      <div className={styles.syncResultSub}>
                        Đã tạo {syncResult.chunks} chunks · Chatbot có thể tra cứu ngay
                      </div>
                    )}
                  </div>
                </div>
              )}

              <button
                id="sync-submit-btn"
                type="submit"
                className={styles.syncBtn}
                disabled={!syncContent.trim() || !syncSource.trim() || syncLoading}
              >
                {syncLoading ? (
                  <><Loader2 size={16} className={styles.spinning} /> Đang đồng bộ...</>
                ) : (
                  <><Database size={16} /> Đồng bộ vào Vector DB</>
                )}
              </button>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
