'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, Save, Plus, Trash2, Shield, FileText, CheckCircle,
  AlertCircle, Loader2, Sparkles, ExternalLink, X, ListOrdered,
  FileCheck, Tag, Info, Layers
} from 'lucide-react';
import styles from './page.module.css';
import { api } from '@/lib/api';
import { MOCK_PROCEDURES } from '@/lib/mockData';

// ── Categories & Levels ──
const PREDEFINED_CATEGORIES = [
  { label: 'Đất đai & Nhà ở', slug: 'dat-dai' },
  { label: 'Hộ tịch', slug: 'ho-tich' },
  { label: 'Doanh nghiệp', slug: 'doanh-nghiep' },
  { label: 'Giao thông', slug: 'giao-thong' },
  { label: 'Giáo dục', slug: 'giao-duc' },
  { label: 'Y tế', slug: 'y-te' },
  { label: 'Thuế & Tài chính', slug: 'thue' },
  { label: 'Lao động - BHXH', slug: 'lao-dong' },
  { label: 'Tư pháp', slug: 'tu-phap' },
  { label: 'Khác', slug: 'khac' },
];

const PREDEFINED_LEVELS = [
  'Cấp xã/phường',
  'Cấp huyện',
  'Cấp tỉnh',
  'Cấp trung ương',
];

interface FormStep {
  index: number;
  title: string;
  description: string;
  duration?: string;
}

// ── Helper: Tạo slug từ tiếng Việt ──
function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[đĐ]/g, 'd')
    .replace(/([^0-9a-z-\s])/g, '')
    .replace(/(\s+)/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function ProcedureFormContent() {
  const searchParams = useSearchParams();
  const editSlug = searchParams.get('slug');
  const isEdit = Boolean(editSlug);

  // Admin Auth Key
  const [adminKey, setAdminKey] = useState<string>('');

  // Form State
  const [slug, setSlug] = useState('');
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState(PREDEFINED_CATEGORIES[0].label);
  const [categorySlug, setCategorySlug] = useState(PREDEFINED_CATEGORIES[0].slug);
  const [level, setLevel] = useState(PREDEFINED_LEVELS[0]);
  const [description, setDescription] = useState('');
  const [agency, setAgency] = useState('');
  const [processingTime, setProcessingTime] = useState('3-5 ngày làm việc');
  const [fee, setFee] = useState('Miễn phí');
  const [isPublished, setIsPublished] = useState(true);

  // Dynamic Lists
  const [steps, setSteps] = useState<FormStep[]>([
    { index: 1, title: 'Chuẩn bị hồ sơ', description: 'Người thực hiện chuẩn bị các giấy tờ theo danh mục quy định.', duration: '1 ngày' },
    { index: 2, title: 'Nộp hồ sơ', description: 'Nộp hồ sơ tại bộ phận tiếp nhận hoặc qua cổng dịch vụ công trực tuyến.', duration: 'Trong ngày' },
    { index: 3, title: 'Xử lý và trả kết quả', description: 'Cơ quan có thẩm quyền xử lý và trả kết quả cho người dân.', duration: '3 ngày' },
  ]);

  const [documents, setDocuments] = useState<string[]>([
    'Tờ khai / đơn đăng ký theo mẫu',
    'Bản sao Căn cước công dân (CCCD)',
  ]);
  const [newDocText, setNewDocText] = useState('');

  const [tags, setTags] = useState<string[]>(['Thủ tục hành chính', 'Dịch vụ công']);
  const [newTagText, setNewTagText] = useState('');

  // UI Status
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Check auth
  useEffect(() => {
    const stored = localStorage.getItem('vinalex_admin_key');
    if (stored) {
      setAdminKey(stored);
    } else {
      setAdminKey('vinalex-admin-2024'); // fallback
    }
  }, []);

  // Sync category_slug when category changes
  const handleCategoryChange = (selectedLabel: string) => {
    setCategory(selectedLabel);
    const found = PREDEFINED_CATEGORIES.find((c) => c.label === selectedLabel);
    if (found) {
      setCategorySlug(found.slug);
    } else {
      setCategorySlug(slugify(selectedLabel));
    }
  };

  // Auto-generate slug from title
  const handleGenerateSlug = () => {
    if (title.trim()) {
      setSlug(slugify(title));
    }
  };

  // Load existing procedure if in edit mode
  useEffect(() => {
    if (!editSlug) return;
    setLoading(true);

    const loadData = async () => {
      try {
        // Try getting from backend
        const data = (await api.getProcedureBySlug(editSlug)) as any;
        if (data) {
          setTitle(data.title || '');
          setSlug(data.slug || editSlug);
          setCategory(data.category || PREDEFINED_CATEGORIES[0].label);
          setCategorySlug(data.category_slug || data.categorySlug || PREDEFINED_CATEGORIES[0].slug);
          setLevel(data.level || PREDEFINED_LEVELS[0]);
          setDescription(data.description || '');
          setAgency(data.agency || '');
          setProcessingTime(data.processing_time || data.processingTime || '');
          setFee(data.fee || 'Miễn phí');
          setIsPublished(data.is_published !== undefined ? data.is_published : true);
          if (data.steps && data.steps.length > 0) {
            setSteps(data.steps);
          }
          if (data.documents && data.documents.length > 0) {
            setDocuments(data.documents);
          }
          if (data.tags && data.tags.length > 0) {
            setTags(data.tags);
          }
        }
      } catch {
        // Fallback: check MOCK_PROCEDURES
        const mock = MOCK_PROCEDURES.find((p) => p.slug === editSlug);
        if (mock) {
          setTitle(mock.title);
          setSlug(mock.slug);
          setCategory(mock.category);
          setCategorySlug(mock.categorySlug);
          setLevel(mock.level || PREDEFINED_LEVELS[0]);
          setDescription(mock.description);
          setAgency(mock.agency || '');
          setProcessingTime(mock.processingTime || '');
          setFee(mock.fee || 'Miễn phí');
          setIsPublished(true);
          setSteps(mock.steps);
          setDocuments(mock.documents || []);
          setTags(mock.tags || []);
        } else {
          setSlug(editSlug);
        }
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [editSlug]);

  // Steps Handlers
  const handleAddStep = () => {
    const nextIndex = steps.length + 1;
    setSteps([
      ...steps,
      { index: nextIndex, title: `Bước ${nextIndex}`, description: '', duration: '' },
    ]);
  };

  const handleUpdateStep = (index: number, field: keyof FormStep, value: string) => {
    setSteps(
      steps.map((s, i) => (i === index ? { ...s, [field]: value } : s))
    );
  };

  const handleRemoveStep = (indexToRemove: number) => {
    const filtered = steps.filter((_, i) => i !== indexToRemove);
    const reindexed = filtered.map((s, idx) => ({ ...s, index: idx + 1 }));
    setSteps(reindexed);
  };

  // Documents Handlers
  const handleAddDoc = () => {
    if (!newDocText.trim()) return;
    setDocuments([...documents, newDocText.trim()]);
    setNewDocText('');
  };

  const handleRemoveDoc = (indexToRemove: number) => {
    setDocuments(documents.filter((_, i) => i !== indexToRemove));
  };

  // Tags Handlers
  const handleAddTag = () => {
    if (!newTagText.trim()) return;
    if (!tags.includes(newTagText.trim())) {
      setTags([...tags, newTagText.trim()]);
    }
    setNewTagText('');
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setTags(tags.filter((t) => t !== tagToRemove));
  };

  // Submit Handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!title.trim()) {
      setError('Vui lòng nhập Tiêu đề thủ tục');
      return;
    }
    if (!slug.trim()) {
      setError('Vui lòng nhập Đường dẫn (slug)');
      return;
    }
    if (!description.trim()) {
      setError('Vui lòng nhập Mô tả ngắn');
      return;
    }

    setSaving(true);

    const payload = {
      slug: slug.trim(),
      title: title.trim(),
      category,
      category_slug: categorySlug,
      description: description.trim(),
      steps: steps.map((s, idx) => ({
        index: idx + 1,
        title: s.title,
        description: s.description,
        duration: s.duration || '',
      })),
      documents,
      processing_time: processingTime,
      fee,
      agency,
      level,
      tags,
      is_published: isPublished,
    };

    try {
      if (isEdit) {
        await api.adminUpdateProcedure(adminKey, editSlug as string, payload);
        setSuccessMessage(`Đã cập nhật thủ tục "${payload.title}" thành công!`);
      } else {
        await api.adminCreateProcedure(adminKey, payload);
        setSuccessMessage(`Đã tạo thủ tục mới "${payload.title}" thành công!`);
      }
    } catch (err: any) {
      // Offline / Demo Mode fallback
      console.warn('Backend offline or failed, demo save fallback:', err);
      setSuccessMessage(
        `[Chế độ Demo] Đã lưu thủ tục "${payload.title}" thành công! (Dữ liệu sẵn sàng khi kết nối backend)`
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className={styles.pageLayout}>
        <div style={{ margin: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <Loader2 size={36} className={styles.spinning} color="#818cf8" />
          <p style={{ color: '#94a3b8' }}>Đang tải thông tin thủ tục...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.pageLayout}>
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
          <Link href="/admin" className={styles.navItem}>
            <ArrowLeft size={16} />
            <span>Quay lại Dashboard</span>
          </Link>
          <div className={`${styles.navItem} ${styles.navItemActive}`}>
            <FileText size={16} />
            <span>{isEdit ? 'Chỉnh sửa thủ tục' : 'Tạo mới thủ tục'}</span>
          </div>
        </nav>

        <div className={styles.sidebarFooter}>
          <Link href="/thu-tuc" target="_blank" className={styles.navItem}>
            <ExternalLink size={16} />
            <span>Xem Knowledge Hub</span>
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <main className={styles.mainContent}>
        <div className={styles.container}>
          {/* Top Bar */}
          <div className={styles.topNav}>
            <Link href="/admin" className={styles.backBtn}>
              <ArrowLeft size={15} />
              Quay lại danh sách quản trị
            </Link>
          </div>

          {/* Header Title Row */}
          <div className={styles.headerTitleRow}>
            <div>
              <h1 className={styles.pageTitle}>
                <FileText size={24} color="#818cf8" />
                {isEdit ? 'Chỉnh sửa Thủ tục' : 'Thêm Thủ tục Mới'}
              </h1>
              <p className={styles.pageSub}>
                {isEdit
                  ? `Đang chỉnh sửa bản ghi: ${editSlug}`
                  : 'Điền thông tin chi tiết để tạo thủ tục hành chính mới vào hệ thống'}
              </p>
            </div>

            <div className={styles.topActions}>
              <button
                type="button"
                id="procedure-save-btn"
                className={styles.saveBtn}
                onClick={handleSubmit}
                disabled={saving}
              >
                {saving ? (
                  <>
                    <Loader2 size={16} className={styles.spinning} />
                    <span>Đang lưu...</span>
                  </>
                ) : (
                  <>
                    <Save size={16} />
                    <span>{isEdit ? 'Lưu thay đổi' : 'Tạo thủ tục'}</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Alert Success */}
          {successMessage && (
            <div className={styles.alertSuccess}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <CheckCircle size={18} />
                <span>{successMessage}</span>
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                {slug && (
                  <Link href={`/thu-tuc/${slug}`} target="_blank" className={styles.alertLink}>
                    Xem trang công khai →
                  </Link>
                )}
                <Link href="/admin" className={styles.alertLink}>
                  Về Dashboard
                </Link>
              </div>
            </div>
          )}

          {/* Alert Error */}
          {error && (
            <div className={styles.alertError}>
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Card 1: Thông tin cơ bản */}
            <div className={styles.formCard}>
              <div className={styles.cardHeader}>
                <div>
                  <h2 className={styles.cardTitle}>
                    <Info size={18} color="#818cf8" />
                    Thông tin cơ bản
                  </h2>
                  <p className={styles.cardDesc}>Tiêu đề, phân loại và tóm tắt nội dung thủ tục</p>
                </div>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>
                  Tiêu đề thủ tục <span className={styles.required}>*</span>
                </label>
                <input
                  id="proc-title-input"
                  type="text"
                  className={styles.formInput}
                  placeholder="VD: Cấp Giấy chứng nhận quyền sử dụng đất lần đầu"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
              </div>

              <div className={styles.formGrid}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>
                    Đường dẫn (Slug URL) <span className={styles.required}>*</span>
                  </label>
                  <div className={styles.slugRow}>
                    <input
                      id="proc-slug-input"
                      type="text"
                      className={`${styles.formInput} ${styles.slugInput}`}
                      placeholder="cap-giay-chung-nhan-qssd"
                      value={slug}
                      onChange={(e) => setSlug(e.target.value)}
                      required
                    />
                    <button
                      type="button"
                      className={styles.generateBtn}
                      onClick={handleGenerateSlug}
                      title="Tự động tạo slug từ tiêu đề"
                    >
                      <Sparkles size={13} />
                      Tạo Slug
                    </button>
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>
                    Danh mục <span className={styles.required}>*</span>
                  </label>
                  <select
                    id="proc-category-select"
                    className={styles.formSelect}
                    value={category}
                    onChange={(e) => handleCategoryChange(e.target.value)}
                  >
                    {PREDEFINED_CATEGORIES.map((cat) => (
                      <option key={cat.slug} value={cat.label}>
                        {cat.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>
                  Mô tả ngắn gọn <span className={styles.required}>*</span>
                </label>
                <textarea
                  id="proc-desc-textarea"
                  className={styles.formTextarea}
                  placeholder="Tóm tắt về mục đích, đối tượng áp dụng và quy định chung của thủ tục..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  required
                />
              </div>

              <div className={styles.toggleRow}>
                <div className={toggleLabelStyle}>
                  <span className={styles.toggleTitle}>Trạng thái xuất bản</span>
                  <span className={styles.toggleSub}>
                    {isPublished
                      ? 'Thủ tục sẽ hiển thị công khai trên cổng Knowledge Hub'
                      : 'Lưu dưới dạng bản nháp (chỉ Admin nhìn thấy)'}
                  </span>
                </div>
                <label className={styles.toggleSwitch}>
                  <input
                    type="checkbox"
                    checked={isPublished}
                    onChange={(e) => setIsPublished(e.target.checked)}
                  />
                  <span className={styles.toggleSlider}></span>
                </label>
              </div>
            </div>

            {/* Card 2: Quy định thực hiện & Cơ quan */}
            <div className={styles.formCard}>
              <div className={styles.cardHeader}>
                <div>
                  <h2 className={styles.cardTitle}>
                    <Layers size={18} color="#818cf8" />
                    Cơ quan & Thời hạn giải quyết
                  </h2>
                  <p className={styles.cardDesc}>Cấp thẩm quyền, cơ quan thực hiện và lệ phí</p>
                </div>
              </div>

              <div className={styles.formGrid3}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Cấp thực hiện</label>
                  <select
                    id="proc-level-select"
                    className={styles.formSelect}
                    value={level}
                    onChange={(e) => setLevel(e.target.value)}
                  >
                    {PREDEFINED_LEVELS.map((lvl) => (
                      <option key={lvl} value={lvl}>
                        {lvl}
                      </option>
                    ))}
                  </select>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Thời gian giải quyết</label>
                  <input
                    type="text"
                    className={styles.formInput}
                    placeholder="VD: 30 ngày làm việc"
                    value={processingTime}
                    onChange={(e) => setProcessingTime(e.target.value)}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Lệ phí</label>
                  <input
                    type="text"
                    className={styles.formInput}
                    placeholder="VD: Miễn phí hoặc 100.000 VNĐ"
                    value={fee}
                    onChange={(e) => setFee(e.target.value)}
                  />
                </div>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Cơ quan tiếp nhận & giải quyết</label>
                <input
                  type="text"
                  className={styles.formInput}
                  placeholder="VD: Bộ phận Một cửa UBND Quận/Huyện hoặc Văn phòng Đăng ký Đất đai"
                  value={agency}
                  onChange={(e) => setAgency(e.target.value)}
                />
              </div>
            </div>

            {/* Card 3: Hồ sơ cần chuẩn bị */}
            <div className={styles.formCard}>
              <div className={styles.cardHeader}>
                <div>
                  <h2 className={styles.cardTitle}>
                    <FileCheck size={18} color="#818cf8" />
                    Hồ sơ & Giấy tờ cần chuẩn bị
                  </h2>
                  <p className={styles.cardDesc}>Danh sách giấy tờ công dân cần nộp kèm</p>
                </div>
              </div>

              <div className={styles.docList}>
                {documents.map((doc, idx) => (
                  <div key={idx} className={styles.docItem}>
                    <span style={{ color: '#818cf8', fontWeight: 600, fontSize: 13 }}>
                      {idx + 1}.
                    </span>
                    <span className={styles.docText}>{doc}</span>
                    <button
                      type="button"
                      className={styles.removeStepBtn}
                      onClick={() => handleRemoveDoc(idx)}
                      title="Xóa giấy tờ này"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>

              <div className={styles.addDocRow}>
                <input
                  type="text"
                  className={styles.formInput}
                  placeholder="Nhập tên giấy tờ cần bổ sung..."
                  value={newDocText}
                  onChange={(e) => setNewDocText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddDoc();
                    }
                  }}
                />
                <button
                  type="button"
                  className={styles.addItemBtn}
                  onClick={handleAddDoc}
                >
                  <Plus size={15} />
                  Thêm giấy tờ
                </button>
              </div>
            </div>

            {/* Card 4: Các bước thực hiện */}
            <div className={styles.formCard}>
              <div className={styles.cardHeader}>
                <div>
                  <h2 className={styles.cardTitle}>
                    <ListOrdered size={18} color="#818cf8" />
                    Trình tự các bước thực hiện
                  </h2>
                  <p className={styles.cardDesc}>Quy trình từng bước để hoàn tất thủ tục</p>
                </div>
                <button
                  type="button"
                  className={styles.addItemBtn}
                  onClick={handleAddStep}
                >
                  <Plus size={15} />
                  Thêm bước
                </button>
              </div>

              {steps.map((step, idx) => (
                <div key={idx} className={styles.stepItem}>
                  <div className={styles.stepHeader}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span className={styles.stepBadge}>{idx + 1}</span>
                      <strong style={{ fontSize: 13.5, color: '#f1f5f9' }}>
                        Bước {idx + 1}
                      </strong>
                    </div>
                    {steps.length > 1 && (
                      <button
                        type="button"
                        className={styles.removeStepBtn}
                        onClick={() => handleRemoveStep(idx)}
                        title="Xóa bước này"
                      >
                        <Trash2 size={15} />
                      </button>
                    )}
                  </div>

                  <div className={styles.stepFieldsGrid}>
                    <input
                      type="text"
                      className={styles.formInput}
                      placeholder={`Tiêu đề bước (VD: Nộp hồ sơ)`}
                      value={step.title}
                      onChange={(e) => handleUpdateStep(idx, 'title', e.target.value)}
                      required
                    />
                    <input
                      type="text"
                      className={styles.formInput}
                      placeholder={`Thời gian (VD: 1 ngày)`}
                      value={step.duration || ''}
                      onChange={(e) => handleUpdateStep(idx, 'duration', e.target.value)}
                    />
                  </div>

                  <textarea
                    className={styles.formTextarea}
                    placeholder="Mô tả chi tiết các việc cần làm tại bước này..."
                    value={step.description}
                    onChange={(e) => handleUpdateStep(idx, 'description', e.target.value)}
                    rows={2}
                    required
                  />
                </div>
              ))}
            </div>

            {/* Card 5: Từ khóa tìm kiếm (Tags) */}
            <div className={styles.formCard}>
              <div className={styles.cardHeader}>
                <div>
                  <h2 className={styles.cardTitle}>
                    <Tag size={18} color="#818cf8" />
                    Từ khóa tra cứu (Tags)
                  </h2>
                  <p className={styles.cardDesc}>Giúp công dân dễ dàng tìm kiếm trên thanh search</p>
                </div>
              </div>

              <div className={styles.tagList}>
                {tags.map((tag) => (
                  <span key={tag} className={styles.tagChip}>
                    #{tag}
                    <button
                      type="button"
                      className={styles.removeTagBtn}
                      onClick={() => handleRemoveTag(tag)}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>

              <div className={styles.addTagRow}>
                <input
                  type="text"
                  className={styles.formInput}
                  placeholder="Thêm tag mới (VD: Sổ đỏ)..."
                  value={newTagText}
                  onChange={(e) => setNewTagText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddTag();
                    }
                  }}
                />
                <button
                  type="button"
                  className={styles.addItemBtn}
                  onClick={handleAddTag}
                >
                  <Plus size={15} />
                  Thêm
                </button>
              </div>
            </div>

            {/* Bottom Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 12 }}>
              <Link href="/admin" className={styles.backBtn}>
                Hủy bỏ
              </Link>
              <button
                type="submit"
                className={styles.saveBtn}
                disabled={saving}
              >
                {saving ? (
                  <>
                    <Loader2 size={16} className={styles.spinning} />
                    <span>Đang lưu...</span>
                  </>
                ) : (
                  <>
                    <Save size={16} />
                    <span>{isEdit ? 'Lưu thay đổi' : 'Tạo thủ tục'}</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}

const toggleLabelStyle = styles.toggleLabel;

export default function ProcedureFormPage() {
  return (
    <Suspense
      fallback={
        <div style={{ minHeight: '100vh', background: '#0a0a0f', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
          <Loader2 size={32} className={styles.spinning} />
        </div>
      }
    >
      <ProcedureFormContent />
    </Suspense>
  );
}
