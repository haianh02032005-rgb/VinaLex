'use client';

import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { Search, SlidersHorizontal, Eye, Clock, ArrowRight, X, Loader2 } from 'lucide-react';
import { MOCK_PROCEDURES, CATEGORIES } from '@/lib/mockData';
import styles from './page.module.css';
import type { Procedure } from '@/types';

// ── Utilities ──────────────────────────────────────────────

function stripAccents(str: string): string {
  return str
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();
}

/** Nối array an toàn — xử lý cả object (ProcedureStep) lẫn string */
function safeJoin(arr: unknown[] | undefined | null): string {
  if (!arr || !Array.isArray(arr)) return '';
  return arr
    .map((item) => {
      if (typeof item === 'string') return item;
      if (typeof item === 'object' && item !== null) {
        // ProcedureStep: lấy title + description
        const obj = item as Record<string, unknown>;
        return [obj.title, obj.description].filter(Boolean).join(' ');
      }
      return '';
    })
    .join(' ');
}

// Semantic aliases mapping query concepts to related terms and boosted categories
const SEMANTIC_ALIASES: Array<{
  queries: string[];
  terms: string[];
  preferredCategories: string[];
}> = [
  {
    queries: ['so do', 'so hong', 'dat dai', 'nha dat', 'quyen su dung dat'],
    terms: ['so do', 'so hong', 'quyen su dung dat', 'gcnqsdd', 'dat dai', 'nha dat', 'dia chinh', 'thua dat'],
    preferredCategories: ['dat-dai', 'bat-dong-san'],
  },
  {
    queries: ['can cuoc', 'cccd', 'cmnd', 'can cuoc cong dan', 'dinh danh'],
    terms: ['can cuoc', 'cccd', 'cmnd', 'dinh danh dien tu', 'vneid', 'the can cuoc'],
    preferredCategories: ['ho-tich'],
  },
  {
    queries: ['khai sinh', 'giay khai sinh', 'dang ky khai sinh'],
    terms: ['khai sinh', 'giay khai sinh', 'chung sinh'],
    preferredCategories: ['ho-tich'],
  },
  {
    queries: ['ket hon', 'hon nhan', 'dang ky ket hon', 'ly hon'],
    terms: ['ket hon', 'hon nhan', 'tinh trang hon nhan', 'ly hon', 'hon thu'],
    preferredCategories: ['ho-tich'],
  },
  {
    queries: ['bang lai', 'gplx', 'lai xe', 'giay phep lai xe'],
    terms: ['bang lai', 'gplx', 'lai xe', 'giay phep lai xe', 'doi bang lai'],
    preferredCategories: ['giao-thong', 'giao-thong-van-tai'],
  },
  {
    queries: ['tam tru', 'ho khau', 'thuong tru', 'cu tru', 'dang ky tam tru'],
    terms: ['tam tru', 'ho khau', 'thuong tru', 'cu tru', 'so ho khau'],
    preferredCategories: ['ho-tich'],
  },
  {
    queries: ['thue', 'thue tncn', 'thue gtgt', 'ma so thue', 'dang ky thue', 'quyet toan thue'],
    terms: ['thue', 'nop thue', 'ke khai thue', 'dang ky thue', 'ma so thue', 'quyet toan thue', 'thue tncn', 'thue gtgt', 'thue tndn'],
    preferredCategories: ['thue', 'thue-phi-le-phi'],
  },
  {
    queries: ['thanh lap cong ty', 'dang ky doanh nghiep', 'mo cong ty', 'doanh nghiep', 'giay phep kinh doanh'],
    terms: ['thanh lap cong ty', 'thanh lap doanh nghiep', 'dang ky kinh doanh', 'giay phep kinh doanh', 'doanh nghiep'],
    preferredCategories: ['doanh-nghiep'],
  },
];

function calculateRelevanceScore(p: Procedure, search: string): number {
  if (!search.trim()) return 1;

  const q = search.trim().toLowerCase();
  const qClean = stripAccents(q);

  const title = (p.title || '').toLowerCase();
  const titleClean = stripAccents(title);

  const cat = (p.category || '').toLowerCase();
  const catSlug = (p.categorySlug || '').toLowerCase();
  const catClean = stripAccents(cat);

  const tagsArr = Array.isArray(p.tags) ? (p.tags as string[]) : [];
  const tagsStr = tagsArr.join(' ').toLowerCase();
  const tagsClean = stripAccents(tagsStr);

  const desc = (p.description || '').toLowerCase();
  const descClean = stripAccents(desc);

  const docsAndSteps = [
    safeJoin(p.documents as unknown[]),
    safeJoin(p.steps as unknown[]),
  ].join(' ').toLowerCase();
  const docsClean = stripAccents(docsAndSteps);

  let score = 0;

  // 1. Khớp cụm từ chính xác (Exact phrase)
  if (title.includes(q)) score += 120;
  else if (titleClean.includes(qClean)) score += 100;

  if (tagsStr.includes(q)) score += 70;
  else if (tagsClean.includes(qClean)) score += 60;

  if (cat.includes(q) || catSlug.includes(qClean)) score += 50;

  if (desc.includes(q)) score += 30;
  else if (descClean.includes(qClean)) score += 25;

  if (docsAndSteps.includes(q) || docsClean.includes(qClean)) score += 10;

  // 2. Tách từ khóa loại bỏ stop-words
  const stopWords = new Set([
    'thu', 'tuc', 'lam', 'xin', 'cap', 'cho',
    'cua', 'tai', 'o', 've', 'giay', 'va', 'cac', 'mot',
    'nhung', 'duoc', 'co', 'la', 'toi', 'muon', 'can', 'hoi',
  ]);

  const rawTokens = qClean.split(/\s+/).filter(Boolean);
  const keywords = rawTokens.filter((tok) => !stopWords.has(tok) && tok.length > 1);
  const searchTokens = keywords.length > 0 ? keywords : rawTokens;

  let allTokensInTitle = true;
  let allTokensInFull = true;

  for (const token of searchTokens) {
    const inTitle = titleClean.includes(token);
    const inTags = tagsClean.includes(token);
    const inCat = catClean.includes(token);
    const inDesc = descClean.includes(token);

    if (inTitle) score += 25;
    else allTokensInTitle = false;

    if (inTags) score += 15;
    if (inCat) score += 15;
    if (inDesc) score += 6;

    if (!inTitle && !inTags && !inCat && !inDesc && !docsClean.includes(token)) {
      allTokensInFull = false;
    }
  }

  if (searchTokens.length > 1 && allTokensInTitle) score += 40;
  if (searchTokens.length > 1 && allTokensInFull) score += 20;

  // 3. Khớp ngữ nghĩa thực thể (Semantic Aliases)
  for (const alias of SEMANTIC_ALIASES) {
    const isQueryMatch = alias.queries.some((aq) => qClean.includes(aq) || aq.includes(qClean));
    if (isQueryMatch) {
      // Ưu tiên danh mục tương ứng
      if (alias.preferredCategories.includes(catSlug)) {
        score += 80;
      }
      // Ưu tiên các từ liên quan xuất hiện trong title hoặc tags
      for (const term of alias.terms) {
        if (titleClean.includes(term)) score += 60;
        if (tagsClean.includes(term)) score += 40;
      }
    }
  }

  return score;
}

/** Highlight từ khóa trong văn bản */
function highlightText(text: string, search: string): React.ReactNode {
  if (!search.trim() || !text) return text;
  const q = search.trim();
  // Escape regex special chars
  const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escaped})`, 'gi');
  const parts = text.split(regex);
  if (parts.length <= 1) return text;
  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark key={i} className={styles.highlight}>
        {part}
      </mark>
    ) : (
      part
    )
  );
}

// ── Main Component ──────────────────────────────────────────

export default function ProceduresPage() {
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState(''); // debounced value
  const [activeCategory, setActiveCategory] = useState('');
  const [allProcedures, setAllProcedures] = useState<Procedure[]>(MOCK_PROCEDURES);
  const [isLoading, setIsLoading] = useState(true);
  const [backendError, setBackendError] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce search input 300ms
  const handleSearchChange = useCallback((value: string) => {
    setSearchInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearch(value);
    }, 300);
  }, []);

  // Fetch từ backend một lần khi mount
  useEffect(() => {
    async function loadBackendProcedures() {
      setIsLoading(true);
      setBackendError(false);
      try {
        const res = await fetch('http://localhost:8000/api/v1/procedures?limit=100');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.items && Array.isArray(data.items) && data.items.length > 0) {
          const existingSlugs = new Set(MOCK_PROCEDURES.map((p) => p.slug));
          const merged: Procedure[] = [...MOCK_PROCEDURES];

          for (const item of data.items) {
            if (!item.slug) continue;
            if (existingSlugs.has(item.slug)) continue;

            merged.push({
              id: String(item.id),
              slug: item.slug,
              title: item.title || '',
              category: item.category || '',
              categorySlug: item.category_slug || '',
              description: item.description || '',
              steps: Array.isArray(item.steps) ? item.steps : [],
              documents: Array.isArray(item.documents) ? item.documents : [],
              processingTime: item.processing_time || 'Đang cập nhật',
              fee: item.fee || 'Miễn phí',
              agency: item.agency || 'Cơ quan nhà nước',
              level: item.level || 'Cơ sở',
              tags: Array.isArray(item.tags) ? item.tags : [],
              updatedAt: item.updated_at ? item.updated_at.split('T')[0] : '2026-09-22',
              viewCount: item.view_count || 0,
            });
          }

          setAllProcedures(merged);
        }
      } catch {
        // Backend chưa sẵn sàng — giữ MOCK_PROCEDURES
        setBackendError(true);
      } finally {
        setIsLoading(false);
      }
    }

    loadBackendProcedures();

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const filtered = useMemo(() => {
    const isSearching = Boolean(search.trim());

    return allProcedures
      .map((p) => ({
        procedure: p,
        score: isSearching ? calculateRelevanceScore(p, search) : 1,
      }))
      .filter(({ procedure: p, score }) => {
        // Nếu đang tìm kiếm, loại trừ các thủ tục không liên quan (score <= 0)
        if (isSearching && score <= 0) return false;
        // Khớp danh mục nếu đang lọc theo tab
        const matchCat = !activeCategory || p.categorySlug === activeCategory;
        return matchCat;
      })
      .sort((a, b) => {
        if (isSearching) {
          // Ưu tiên độ liên quan cao nhất
          if (b.score !== a.score) return b.score - a.score;
        }
        // Khi điểm bằng nhau hoặc không tìm kiếm -> xếp theo lượt xem
        return b.procedure.viewCount - a.procedure.viewCount;
      })
      .map(({ procedure }) => procedure);
  }, [allProcedures, search, activeCategory]);

  const clearSearch = () => {
    setSearchInput('');
    setSearch('');
    if (debounceRef.current) clearTimeout(debounceRef.current);
  };

  return (
    <div className={styles.page}>
      {/* Page Header */}
      <div className={styles.pageHeader}>
        <div className={styles.container}>
          <div className={styles.breadcrumb}>
            <Link href="/">Trang chủ</Link>
            <span>/</span>
            <span>Thủ tục hành chính</span>
          </div>
          <h1 className={styles.pageTitle}>
            Tra cứu{' '}
            <span className="text-gradient">Thủ tục Hành chính</span>
          </h1>
          <p className={styles.pageSubtitle}>
            Hơn 2.500 thủ tục hành chính công được cập nhật theo văn bản pháp luật mới nhất.
          </p>

          {/* Search */}
          <div className={styles.searchWrapper}>
            {isLoading ? (
              <Loader2 size={18} className={`${styles.searchIcon} ${styles.spinning}`} />
            ) : (
              <Search size={18} className={styles.searchIcon} />
            )}
            <input
              id="procedure-search-input"
              type="text"
              value={searchInput}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Tìm tên thủ tục, danh mục, từ khóa... (VD: khai sinh, căn cước, sổ đỏ)"
              className={styles.searchInput}
              autoComplete="off"
              spellCheck={false}
            />
            {searchInput && (
              <button
                onClick={clearSearch}
                className={styles.clearBtn}
                aria-label="Xóa tìm kiếm"
              >
                <X size={16} />
              </button>
            )}
          </div>

          {/* Search hints khi ô trống */}
          {!searchInput && (
            <div className={styles.searchHints}>
              <span className={styles.hintLabel}>Gợi ý:</span>
              {['Khai sinh', 'Căn cước', 'Sổ đỏ', 'Kết hôn', 'Bằng lái xe', 'Tạm trú'].map((hint) => (
                <button
                  key={hint}
                  className={styles.hintChip}
                  onClick={() => {
                    setSearchInput(hint);
                    setSearch(hint);
                  }}
                >
                  {hint}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className={styles.container}>
        {/* Categories */}
        <div className={styles.catRow}>
          <button
            className={`${styles.catBtn} ${!activeCategory ? styles.catBtnActive : ''}`}
            onClick={() => setActiveCategory('')}
          >
            Tất cả
          </button>
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              className={`${styles.catBtn} ${activeCategory === cat.slug ? styles.catBtnActive : ''}`}
              onClick={() => setActiveCategory(cat.slug === activeCategory ? '' : cat.slug)}
              style={
                activeCategory === cat.slug
                  ? { borderColor: cat.color, color: cat.color, background: `${cat.color}15` }
                  : {}
              }
            >
              <span>{cat.icon}</span>
              {cat.label}
              <span className={styles.catCount}>{cat.count}</span>
            </button>
          ))}
        </div>

        {/* Results Summary */}
        <div className={styles.resultsSummary}>
          <span>
            {isLoading ? (
              <span className={styles.loadingText}>Đang tải dữ liệu...</span>
            ) : (
              <>
                Tìm thấy <strong>{filtered.length}</strong> thủ tục
                {activeCategory &&
                  ` trong "${CATEGORIES.find((c) => c.slug === activeCategory)?.label}"`}
                {search && ` cho "${search}"`}
                {backendError && (
                  <span className={styles.offlineBadge} title="Đang dùng dữ liệu ngoại tuyến">
                    · Offline
                  </span>
                )}
              </>
            )}
          </span>
          <div className={styles.sortRow}>
            <SlidersHorizontal size={14} />
            <span>Sắp xếp: Xem nhiều nhất</span>
          </div>
        </div>

        {/* Grid */}
        {isLoading ? (
          <div className={styles.skeletonGrid}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className={styles.skeletonCard} />
            ))}
          </div>
        ) : filtered.length > 0 ? (
          <div className={styles.grid}>
            {filtered.map((proc) => (
              <Link
                key={proc.id}
                href={`/thu-tuc/${proc.slug}`}
                className={styles.card}
              >
                <div className={styles.cardTop}>
                  <span className={styles.cardCategory}>{proc.category}</span>
                  <span className={styles.cardLevel}>{proc.level}</span>
                </div>
                <h2 className={styles.cardTitle}>
                  {highlightText(proc.title, search)}
                </h2>
                <p className={styles.cardDesc}>
                  {highlightText(proc.description, search)}
                </p>
                <div className={styles.cardTags}>
                  {proc.tags.slice(0, 4).map((tag) => (
                    <span key={tag} className={styles.tag}>
                      # {highlightText(tag, search)}
                    </span>
                  ))}
                </div>
                <div className={styles.cardMeta}>
                  <div className={styles.metaItem}>
                    <Clock size={13} />
                    {proc.processingTime}
                  </div>
                  <div className={styles.metaItem}>
                    <Eye size={13} />
                    {proc.viewCount.toLocaleString('vi-VN')} lượt
                  </div>
                  <span className={styles.fee}>{proc.fee}</span>
                </div>
                <div className={styles.cardCta}>
                  Xem chi tiết <ArrowRight size={14} />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>🔍</div>
            <h3>Không tìm thấy thủ tục nào</h3>
            <p>
              {search
                ? `Không có kết quả cho "${search}". Thử thay đổi từ khóa hoặc gõ không dấu.`
                : 'Thử thay đổi từ khóa hoặc bỏ bộ lọc danh mục'}
            </p>
            <button
              className={styles.resetBtn}
              onClick={() => {
                clearSearch();
                setActiveCategory('');
              }}
            >
              Xóa bộ lọc
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
