'use client';

import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import {
  Search,
  SlidersHorizontal,
  Eye,
  Clock,
  ArrowRight,
  X,
  Loader2,
  FileText,
  BookOpen,
  ExternalLink,
  Calendar,
  Building,
  Copy,
  Check,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { MOCK_PROCEDURES, CATEGORIES } from '@/lib/mockData';
import styles from './page.module.css';
import type { Procedure, LegalDocument } from '@/types';

// ── Utilities ──────────────────────────────────────────────

function stripAccents(str: string): string {
  return str
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();
}

function hasWord(pattern: string, text: string): boolean {
  if (!pattern || !text) return false;
  const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(?:\\b|^)${escaped}(?:\\b|$)`, 'i');
  return regex.test(text);
}

const COMPOUND_PHRASES = [
  'khai sinh', 'khai tu', 'ket hon', 'ly hon', 'tam tru', 'thuong tru',
  'ho khau', 'can cuoc', 'can cuoc cong dan', 'chung minh nhan dan',
  'so do', 'so hong', 'quyen su dung dat', 'gcnqsdd',
  'bang lai', 'bang lai xe', 'giay phep lai xe', 'dang ky xe', 'bien so xe',
  'thanh lap cong ty', 'dang ky kinh doanh', 'dang ky doanh nghiep',
  'bao hiem xa hoi', 'bhxh', 'bao hiem y te', 'bhyt', 'that nghiep',
  'ho chieu', 'visa', 'xuat nhap canh', 'ly lich tu phap',
  'thue thu nhap', 'thue tncn', 'quyet toan thue', 'ma so thue',
  'giay phep xay dung', 'chuyen nhuong', 'tang cho', 'thua ke'
];

// Semantic aliases mapping query concepts to related terms and boosted categories
const SEMANTIC_ALIASES: Array<{
  queries: string[];
  terms: string[];
  preferredCategories: string[];
}> = [
  {
    queries: ['so do', 'so hong', 'gcnqsdd'],
    terms: ['so do', 'so hong', 'quyen su dung dat', 'gcnqsdd', 'giay chung nhan quyen su dung dat'],
    preferredCategories: ['dat-dai', 'bat-dong-san'],
  },
  {
    queries: ['dat dai', 'nha dat'],
    terms: ['dat dai', 'nha dat', 'dia chinh', 'thua dat', 'bat dong san'],
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
    queries: ['ket hon', 'hon nhan', 'dang ky ket hon'],
    terms: ['ket hon', 'hon nhan', 'tinh trang hon nhan', 'hon thu'],
    preferredCategories: ['ho-tich'],
  },
  {
    queries: ['ly hon'],
    terms: ['ly hon', 'don phuong ly hon', 'thuan tinh ly hon'],
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
  {
    queries: ['bao hiem xa hoi', 'bhxh'],
    terms: ['bao hiem xa hoi', 'bhxh', 'so bhxh', 'che do bhxh'],
    preferredCategories: ['lao-dong'],
  },
];

function calculateRelevanceScore(p: Procedure, search: string): number {
  if (!search.trim()) return 1;

  const q = search.trim().toLowerCase();
  const qClean = stripAccents(q);

  const title = (p.title || '').toLowerCase();
  const titleClean = stripAccents(title);

  const catSlug = (p.categorySlug || '').toLowerCase();

  const tagsArr = Array.isArray(p.tags) ? (p.tags as string[]) : [];
  const tagsStr = tagsArr.join(' ').toLowerCase();
  const tagsClean = stripAccents(tagsStr);

  const desc = (p.description || '').toLowerCase();
  const descClean = stripAccents(desc);

  // 1. Tách từ khóa & loại bỏ stop-words
  const stopWords = new Set([
    'thu', 'tuc', 'lam', 'xin', 'cap', 'cho',
    'cua', 'tai', 'o', 've', 'giay', 'va', 'cac', 'mot',
    'nhung', 'duoc', 'co', 'la', 'toi', 'muon', 'can', 'hoi',
    'theo', 'den', 'tu', 'trong', 'de', 'ngay', 'nam',
  ]);

  const rawTokens = qClean.split(/[\s,\.\?\!\:\;]+/).filter(Boolean);
  const keywords = rawTokens.filter((tok) => !stopWords.has(tok) && tok.length > 1);
  const searchTokens = keywords.length > 0 ? keywords : rawTokens;

  // ── TẦNG 1: BỘ LỌC BẮT BUỘC (Hard Pruning Filter) ──
  const matchedCompounds = COMPOUND_PHRASES.filter((cp) => hasWord(cp, qClean));
  let isStrictMatch = false;

  if (matchedCompounds.length > 0) {
    for (const cp of matchedCompounds) {
      if (hasWord(cp, titleClean) || hasWord(cp, tagsClean)) {
        isStrictMatch = true;
        break;
      }
      for (const alias of SEMANTIC_ALIASES) {
        if (alias.queries.some((aq) => cp.includes(aq) || aq.includes(cp))) {
          if (alias.terms.some((term) => hasWord(term, titleClean) || hasWord(term, tagsClean))) {
            isStrictMatch = true;
            break;
          }
        }
      }
      if (isStrictMatch) break;
    }
  } else {
    const exactInTitleOrTags = hasWord(qClean, titleClean) || hasWord(qClean, tagsClean);
    const allTokensInTitleOrTags =
      searchTokens.length > 0 &&
      searchTokens.every((tok) => hasWord(tok, titleClean) || hasWord(tok, tagsClean));

    let synonymMatch = false;
    for (const alias of SEMANTIC_ALIASES) {
      if (alias.queries.some((aq) => qClean.includes(aq) || aq.includes(qClean))) {
        if (alias.terms.some((term) => hasWord(term, titleClean) || hasWord(term, tagsClean))) {
          synonymMatch = true;
          break;
        }
      }
    }

    let multiTokenPartial = false;
    if (searchTokens.length >= 2) {
      const hasAtLeastOneInTitle = searchTokens.some((tok) => hasWord(tok, titleClean) || hasWord(tok, tagsClean));
      const hasAllInFull = searchTokens.every(
        (tok) => hasWord(tok, titleClean) || hasWord(tok, tagsClean) || hasWord(tok, descClean)
      );
      if (hasAtLeastOneInTitle && hasAllInFull) {
        multiTokenPartial = true;
      }
    }

    isStrictMatch =
      exactInTitleOrTags ||
      allTokensInTitleOrTags ||
      synonymMatch ||
      multiTokenPartial;
  }

  // NẾU KHÔNG THỎA MÃN TẦNG 1 -> LOẠI BỎ TRIỆT ĐỂ (Score = 0)
  if (!isStrictMatch) {
    return 0;
  }

  // ── TẦNG 2: CHẤM ĐIỂM XẾP HẠNG (Relevance Ranking) ──
  let score = 0;

  if (title.includes(q)) score += 150;
  else if (hasWord(qClean, titleClean)) score += 120;

  if (hasWord(qClean, tagsClean)) score += 70;

  for (const cp of matchedCompounds) {
    if (hasWord(cp, titleClean)) score += 80;
    if (hasWord(cp, tagsClean)) score += 50;
  }

  for (const token of searchTokens) {
    if (hasWord(token, titleClean)) score += 20;
    if (hasWord(token, tagsClean)) score += 15;
    if (hasWord(token, descClean)) score += 5;
  }

  for (const alias of SEMANTIC_ALIASES) {
    const isQueryMatch = alias.queries.some((aq) => qClean.includes(aq) || aq.includes(qClean));
    if (isQueryMatch && alias.preferredCategories.includes(catSlug)) {
      score += 15;
    }
  }

  return score;
}

/** Chấm điểm & lọc cho Văn bản Thông tư, Nghị định */
function calculateDocRelevanceScore(doc: LegalDocument, search: string): number {
  if (!search.trim()) return 1;

  const q = search.trim().toLowerCase();
  const qClean = stripAccents(q);

  const title = (doc.title || '').toLowerCase();
  const titleClean = stripAccents(title);

  const docNumber = (doc.doc_number || '').toLowerCase();
  const docNumberClean = stripAccents(docNumber);

  const summary = (doc.summary || '').toLowerCase();
  const summaryClean = stripAccents(summary);

  const excerpt = (doc.excerpt || '').toLowerCase();
  const excerptClean = stripAccents(excerpt);

  const rawTokens = qClean.split(/[\s,\.\?\!\:\;]+/).filter(Boolean);
  const stopWords = new Set([
    'thu', 'tuc', 'lam', 'xin', 'cap', 'cho',
    'cua', 'tai', 'o', 've', 'giay', 'va', 'cac', 'mot',
    'nhung', 'duoc', 'co', 'la', 'toi', 'muon', 'can', 'hoi',
    'theo', 'den', 'tu', 'trong', 'de', 'ngay', 'nam',
  ]);
  const searchTokens = rawTokens.filter((tok) => !stopWords.has(tok) && tok.length > 1);
  const tokens = searchTokens.length > 0 ? searchTokens : rawTokens;

  // Khớp số hiệu văn bản (e.g. 6093, 6093/QĐ-UBND, 2026)
  const matchDocNum = docNumberClean.includes(qClean);
  const matchExactTitle = titleClean.includes(qClean);
  const matchTokensInTitle = tokens.length > 0 && tokens.every((tok) => hasWord(tok, titleClean));
  const matchAnyInExcerpt = (excerptClean && excerptClean.includes(qClean)) || (summaryClean && summaryClean.includes(qClean));
  const matchTokensInFull =
    tokens.length > 0 &&
    tokens.every(
      (tok) =>
        hasWord(tok, titleClean) ||
        hasWord(tok, summaryClean) ||
        hasWord(tok, excerptClean) ||
        hasWord(tok, docNumberClean)
    );

  if (!matchDocNum && !matchExactTitle && !matchTokensInTitle && !matchAnyInExcerpt && !matchTokensInFull) {
    return 0;
  }

  let score = 0;
  if (matchDocNum) score += 200;
  if (matchExactTitle) score += 150;
  if (matchTokensInTitle) score += 100;
  if (matchAnyInExcerpt) score += 60;

  for (const tok of tokens) {
    if (hasWord(tok, titleClean)) score += 25;
    if (hasWord(tok, excerptClean)) score += 15;
    if (hasWord(tok, summaryClean)) score += 10;
  }

  return score;
}

/** Khớp thủ tục với danh mục được chọn */
function matchCategory(p: Procedure, activeCat: string): boolean {
  if (!activeCat) return true;
  const target = activeCat.toLowerCase();
  const pSlug = (p.categorySlug || '').toLowerCase();
  const pCat = (p.category || '').toLowerCase();

  switch (target) {
    case 'thue':
      return (
        pSlug === 'thue' ||
        pSlug === 'thue-phi-le-phi' ||
        pSlug === 'tai-chinh-nha-nuoc' ||
        pCat.includes('thuế') ||
        pCat.includes('tài chính')
      );
    case 'dat-dai':
      return (
        pSlug === 'dat-dai' ||
        pSlug === 'bat-dong-san' ||
        pCat.includes('đất') ||
        pCat.includes('nhà') ||
        pCat.includes('bất động sản')
      );
    case 'ho-tich':
      return (
        pSlug === 'ho-tich' ||
        pCat.includes('hộ tịch') ||
        pCat.includes('căn cước')
      );
    case 'doanh-nghiep':
      return (
        pSlug === 'doanh-nghiep' ||
        pSlug === 'thuong-mai' ||
        pCat.includes('doanh nghiệp') ||
        pCat.includes('thương mại')
      );
    case 'giao-thong':
      return (
        pSlug === 'giao-thong' ||
        pSlug === 'giao-thong-van-tai' ||
        pCat.includes('giao thông') ||
        pCat.includes('vận tải')
      );
    case 'lao-dong':
      return (
        pSlug === 'lao-dong' ||
        pSlug === 'lao-dong-tien-luong' ||
        pCat.includes('lao động') ||
        pCat.includes('tiền lương') ||
        pCat.includes('bhxh')
      );
    case 'giao-duc':
      return pSlug === 'giao-duc' || pCat.includes('giáo dục');
    case 'y-te':
      return pSlug === 'y-te' || pCat.includes('y tế');
    default:
      return pSlug === target || pCat.includes(target);
  }
}

/** Highlight từ khóa trong văn bản */
function highlightText(text: string, search: string): React.ReactNode {
  if (!search.trim() || !text) return text;
  const q = search.trim();
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

function getDocBadgeClass(docType: string): string {
  const type = (docType || '').toLowerCase();
  if (type.includes('nghị định') || type.includes('nghi dinh')) return styles.docBadgeNghiDinh;
  if (type.includes('thông tư') || type.includes('thong tu')) return styles.docBadgeThongTu;
  if (type.includes('quyết định') || type.includes('quyet dinh')) return styles.docBadgeQuyetDinh;
  if (type.includes('luật') || type.includes('luat')) return styles.docBadgeLuat;
  return styles.docBadgeDefault;
}

// ── Main Component ──────────────────────────────────────────

export default function ProceduresPage() {
  const [activeTab, setActiveTab] = useState<'procedures' | 'documents'>('procedures');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState(''); // debounced value

  // Procedures State
  const [activeCategory, setActiveCategory] = useState('');
  const [allProcedures, setAllProcedures] = useState<Procedure[]>(MOCK_PROCEDURES);
  const [isLoading, setIsLoading] = useState(true);
  const [backendError, setBackendError] = useState(false);

  // Legal Documents State
  const [allDocuments, setAllDocuments] = useState<LegalDocument[]>([]);
  const [docFilterType, setDocFilterType] = useState<string>('');
  const [isDocsLoading, setIsDocsLoading] = useState(false);
  const [readingDoc, setReadingDoc] = useState<LegalDocument | null>(null);
  const [isDocReadingLoading, setIsDocReadingLoading] = useState(false);
  const [docFontSize, setDocFontSize] = useState<number>(15);
  const [copiedText, setCopiedText] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce search input 300ms
  const handleSearchChange = useCallback((value: string) => {
    setSearchInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearch(value);
    }, 300);
  }, []);

  // Fetch dữ liệu thủ tục và văn bản pháp luật từ backend khi mount
  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      setBackendError(false);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

      // 1. Fetch Procedures
      try {
        const res = await fetch(`${apiUrl}/procedures?limit=1000`);
        if (res.ok) {
          const data = await res.json();
          if (data.items && Array.isArray(data.items) && data.items.length > 0) {
            const existingSlugs = new Set(MOCK_PROCEDURES.map((p) => p.slug));
            const merged: Procedure[] = [...MOCK_PROCEDURES];

            for (const item of data.items) {
              if (!item.slug) continue;
              if (existingSlugs.has(item.slug)) continue;

              merged.push({
                id: `api-${item.slug || item.id}`,
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
        } else {
          setBackendError(true);
        }
      } catch {
        setBackendError(true);
      } finally {
        setIsLoading(false);
      }

      // 2. Fetch Legal Documents (Thông tư, Nghị định, Quyết định...)
      try {
        setIsDocsLoading(true);
        const docsRes = await fetch(`${apiUrl}/legal-documents?limit=1000`);
        if (docsRes.ok) {
          const docsData = await docsRes.json();
          if (docsData.items && Array.isArray(docsData.items)) {
            setAllDocuments(docsData.items);
          }
        }
      } catch (err) {
        console.error('Lỗi khi tải văn bản pháp luật:', err);
      } finally {
        setIsDocsLoading(false);
      }
    }

    loadData();

    // Đọc query param ?cat=, ?search=, ?tab=
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const catParam = params.get('cat');
      if (catParam) setActiveCategory(catParam);

      const tabParam = params.get('tab');
      if (tabParam === 'documents' || tabParam === 'van-ban') {
        setActiveTab('documents');
      }

      const searchParam = params.get('search') || params.get('q');
      if (searchParam) {
        setSearchInput(searchParam);
        setSearch(searchParam);
      }
    }

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Fetch excerpts động từ backend khi người dùng tìm kiếm từ khóa
  useEffect(() => {
    if (!search.trim()) return;

    let isCancelled = false;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

    async function searchLegalDocs() {
      try {
        const res = await fetch(`${apiUrl}/legal-documents?search=${encodeURIComponent(search.trim())}&limit=500`);
        if (res.ok && !isCancelled) {
          const data = await res.json();
          if (data.items && Array.isArray(data.items)) {
            setAllDocuments(data.items);
          }
        }
      } catch {
        // Fallback: giữ allDocuments hiện tại để lọc client
      }
    }

    searchLegalDocs();

    return () => {
      isCancelled = true;
    };
  }, [search]);

  // Lọc thủ tục hành chính
  const filteredProcedures = useMemo(() => {
    const isSearching = Boolean(search.trim());

    return allProcedures
      .map((p) => ({
        procedure: p,
        score: isSearching ? calculateRelevanceScore(p, search) : 1,
      }))
      .filter(({ procedure: p, score }) => {
        const matchCat = matchCategory(p, activeCategory);
        if (!matchCat) return false;
        if (isSearching && score <= 0) return false;
        return true;
      })
      .sort((a, b) => {
        if (isSearching) {
          if (b.score !== a.score) return b.score - a.score;
        }
        return b.procedure.viewCount - a.procedure.viewCount;
      })
      .map(({ procedure }) => procedure);
  }, [allProcedures, search, activeCategory]);

  // Đếm số lượng thủ tục thực tế theo từng danh mục
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const cat of CATEGORIES) {
      counts[cat.slug] = allProcedures.filter((p) => matchCategory(p, cat.slug)).length;
    }
    return counts;
  }, [allProcedures]);

  // Lọc thông tư, nghị định
  const filteredDocuments = useMemo(() => {
    const isSearching = Boolean(search.trim());

    return allDocuments
      .map((doc) => ({
        doc,
        score: isSearching ? calculateDocRelevanceScore(doc, search) : 1,
      }))
      .filter(({ doc, score }) => {
        // Lọc loại văn bản
        if (docFilterType) {
          const dt = (doc.doc_type || '').toLowerCase();
          if (docFilterType === 'Khác') {
            if (dt.includes('nghị định') || dt.includes('thông tư') || dt.includes('quyết định')) {
              return false;
            }
          } else {
            if (!dt.includes(docFilterType.toLowerCase())) return false;
          }
        }

        if (isSearching && score <= 0) return false;
        return true;
      })
      .sort((a, b) => {
        if (isSearching) {
          if (b.score !== a.score) return b.score - a.score;
        }
        return (b.doc.issue_date || '').localeCompare(a.doc.issue_date || '');
      })
      .map(({ doc }) => doc);
  }, [allDocuments, search, docFilterType]);

  const clearSearch = () => {
    setSearchInput('');
    setSearch('');
    if (debounceRef.current) clearTimeout(debounceRef.current);
  };

  // Mở modal đọc toàn văn văn bản
  const handleOpenReader = async (doc: LegalDocument) => {
    setReadingDoc(doc);
    if (!doc.content_text) {
      setIsDocReadingLoading(true);
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        const res = await fetch(`${apiUrl}/legal-documents/${doc.slug}`);
        if (res.ok) {
          const fullDoc = await res.json();
          setReadingDoc((prev) =>
            prev && prev.slug === doc.slug
              ? { ...prev, content_text: fullDoc.content_text }
              : prev
          );
        }
      } catch (err) {
        console.error('Lỗi tải toàn văn văn bản:', err);
      } finally {
        setIsDocReadingLoading(false);
      }
    }
  };

  const handleCopyDocText = () => {
    if (!readingDoc?.content_text) return;
    navigator.clipboard.writeText(readingDoc.content_text);
    setCopiedText(true);
    setTimeout(() => setCopiedText(false), 2000);
  };

  return (
    <div className={styles.page}>
      {/* Page Header */}
      <div className={styles.pageHeader}>
        <div className={styles.container}>
          <div className={styles.breadcrumb}>
            <Link href="/">Trang chủ</Link>
            <span>/</span>
            <span>Tra cứu & Văn bản</span>
          </div>
          <h1 className={styles.pageTitle}>
            Tra cứu{' '}
            <span className="text-gradient">Pháp lý & Thủ tục</span>
          </h1>
          <p className={styles.pageSubtitle}>
            Hệ thống tra cứu kép: Thủ tục hành chính công và Văn bản quy phạm pháp luật (Thông tư, Nghị định, Quyết định).
          </p>

          {/* Search Input */}
          <div className={styles.searchWrapper}>
            {isLoading || isDocsLoading ? (
              <Loader2 size={18} className={`${styles.searchIcon} ${styles.spinning}`} />
            ) : (
              <Search size={18} className={styles.searchIcon} />
            )}
            <input
              id="procedure-search-input"
              type="text"
              value={searchInput}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Nhập từ khóa, tên thủ tục, số hiệu văn bản... (VD: khai sinh, căn cước, sổ đỏ, 6093)"
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
              <span className={styles.hintLabel}>Gợi ý từ khóa:</span>
              {['Khai sinh', 'Căn cước', 'Sổ đỏ', 'Kết hôn', 'Bằng lái xe', 'Tạm trú', 'Doanh nghiệp'].map((hint) => (
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

          {/* ── 2-Section Tab Switcher ── */}
          <div className={styles.tabSwitcher}>
            <button
              type="button"
              className={`${styles.tabBtn} ${activeTab === 'procedures' ? styles.tabBtnActive : ''}`}
              onClick={() => setActiveTab('procedures')}
            >
              <FileText size={18} />
              Thủ tục hành chính
              <span className={styles.tabBadge}>{filteredProcedures.length}</span>
            </button>

            <button
              type="button"
              className={`${styles.tabBtn} ${activeTab === 'documents' ? styles.tabBtnActive : ''}`}
              onClick={() => setActiveTab('documents')}
            >
              <BookOpen size={18} />
              Thông tư, Nghị định
              <span className={styles.tabBadge}>{filteredDocuments.length}</span>
            </button>
          </div>
        </div>
      </div>

      <div className={styles.container}>
        {/* ========================================================
            TAB 1: THỦ TỤC HÀNH CHÍNH (GIỮ NGUYÊN TÍNH NĂNG)
            ======================================================== */}
        {activeTab === 'procedures' && (
          <>
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
                  <span className={styles.catCount}>{categoryCounts[cat.slug] || cat.count}</span>
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
                    Tìm thấy <strong>{filteredProcedures.length}</strong> thủ tục
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

            {/* Procedures Grid */}
            {isLoading ? (
              <div className={styles.skeletonGrid}>
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className={styles.skeletonCard} />
                ))}
              </div>
            ) : filteredProcedures.length > 0 ? (
              <div className={styles.grid}>
                {filteredProcedures.map((proc) => (
                  <Link
                    key={proc.slug}
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
                <h3>Không tìm thấy thủ tục phù hợp</h3>
                <p>
                  {search
                    ? `Không có thủ tục nào khớp với từ khóa "${search}"${activeCategory ? ` trong danh mục "${CATEGORIES.find((c) => c.slug === activeCategory)?.label}"` : ''}.`
                    : 'Không có thủ tục nào trong danh mục đã chọn.'}
                </p>
                <div style={{ marginTop: '1rem', marginBottom: '1.5rem' }}>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                    Gợi ý các từ khóa thủ tục phổ biến:
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'center' }}>
                    {['Cấp sổ đỏ', 'Đăng ký khai sinh', 'Bằng lái xe', 'Căn cước công dân', 'Đăng ký kết hôn', 'Thành lập công ty', 'Tạm trú'].map((term) => (
                      <button
                        key={term}
                        type="button"
                        onClick={() => handleSearchChange(term)}
                        style={{
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          color: 'var(--text-secondary)',
                          padding: '0.35rem 0.75rem',
                          borderRadius: '9999px',
                          fontSize: '0.8rem',
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                        }}
                      >
                        🔍 {term}
                      </button>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
                  {search && (
                    <Link
                      href={`/chat?q=${encodeURIComponent(search)}`}
                      className={styles.resetBtn}
                      style={{ background: 'var(--primary-color, #2563eb)', color: '#fff', border: 'none' }}
                    >
                      💬 Hỏi Trợ lý AI về &quot;{search}&quot;
                    </Link>
                  )}
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
              </div>
            )}
          </>
        )}

        {/* ========================================================
            TAB 2: THÔNG TƯ, NGHỊ ĐỊNH (TRÍCH XUẤT VĂN BẢN ĐỂ ĐỌC)
            KHÔNG ĐỀ XUẤT THỦ TỤC HÀNH CHÍNH
            ======================================================== */}
        {activeTab === 'documents' && (
          <>
            {/* Filter by Document Type */}
            <div className={styles.docFilterRow}>
              {['Tất cả văn bản', 'Nghị định', 'Thông tư', 'Quyết định', 'Khác'].map((t) => {
                const val = t === 'Tất cả văn bản' ? '' : t;
                const isActive = docFilterType === val;
                return (
                  <button
                    key={t}
                    type="button"
                    className={`${styles.docFilterBtn} ${isActive ? styles.docFilterBtnActive : ''}`}
                    onClick={() => setDocFilterType(val)}
                  >
                    {t}
                  </button>
                );
              })}
            </div>

            {/* Results Summary */}
            <div className={styles.resultsSummary}>
              <span>
                {isDocsLoading ? (
                  <span className={styles.loadingText}>Đang tra cứu văn bản pháp luật...</span>
                ) : (
                  <>
                    Tìm thấy <strong>{filteredDocuments.length}</strong> văn bản
                    {docFilterType && ` loại "${docFilterType}"`}
                    {search && ` khớp với "${search}"`}
                  </>
                )}
              </span>
              <div className={styles.sortRow}>
                <SlidersHorizontal size={14} />
                <span>Ban hành mới nhất</span>
              </div>
            </div>

            {/* Documents Grid */}
            {isDocsLoading ? (
              <div className={styles.skeletonGrid}>
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className={styles.skeletonCard} />
                ))}
              </div>
            ) : filteredDocuments.length > 0 ? (
              <div className={styles.docGrid}>
                {filteredDocuments.map((doc) => (
                  <div key={doc.id || doc.slug} className={styles.docCard}>
                    <div className={styles.docTop}>
                      <span className={`${styles.docBadge} ${getDocBadgeClass(doc.doc_type)}`}>
                        {doc.doc_type || 'Văn bản'}
                      </span>
                      <span className={styles.docNumber}>{doc.doc_number}</span>
                    </div>

                    <h3 className={styles.docTitle}>
                      {highlightText(doc.title, search)}
                    </h3>

                    <div className={styles.docMetaLine}>
                      {doc.issuing_authority && (
                        <span className={styles.docMetaItem}>
                          <Building size={13} />
                          {doc.issuing_authority}
                        </span>
                      )}
                      {doc.issue_date && (
                        <span className={styles.docMetaItem}>
                          <Calendar size={13} />
                          Ban hành: {doc.issue_date}
                        </span>
                      )}
                    </div>

                    {(doc.excerpt || doc.summary) && (
                      <div className={styles.docExcerptBox}>
                        <div className={styles.docExcerptHeader}>
                          <BookOpen size={12} />
                          Trích yếu & Nội dung tra cứu
                        </div>
                        <p className={styles.docExcerptText}>
                          {highlightText(doc.excerpt || doc.summary || '', search)}
                        </p>
                      </div>
                    )}

                    <div className={styles.docActions}>
                      <button
                        type="button"
                        className={styles.btnReadDoc}
                        onClick={() => handleOpenReader(doc)}
                      >
                        <BookOpen size={14} />
                        Đọc toàn văn
                      </button>
                      {doc.original_url && (
                        <a
                          href={doc.original_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={styles.btnDocOriginal}
                        >
                          Văn bản gốc <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.empty}>
                <div className={styles.emptyIcon}>📜</div>
                <h3>Không tìm thấy văn bản phù hợp</h3>
                <p>
                  {search
                    ? `Không tìm thấy thông tư, nghị định nào khớp với từ khóa "${search}".`
                    : 'Chưa có văn bản pháp luật trong bộ lọc này.'}
                </p>
                <div style={{ marginTop: '1rem', display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
                  <button
                    className={styles.resetBtn}
                    onClick={() => {
                      clearSearch();
                      setDocFilterType('');
                    }}
                  >
                    Xóa bộ lọc
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Document Reader Modal ── */}
      {readingDoc && (
        <div className={styles.modalOverlay} onClick={() => setReadingDoc(null)}>
          <div className={styles.modalContainer} onClick={(e) => e.stopPropagation()}>
            {/* Modal Header */}
            <div className={styles.modalHeader}>
              <div className={styles.modalHeaderInfo}>
                <div className={styles.modalDocTypeRow}>
                  <span className={`${styles.docBadge} ${getDocBadgeClass(readingDoc.doc_type)}`}>
                    {readingDoc.doc_type}
                  </span>
                  <span className={styles.docNumber}>{readingDoc.doc_number}</span>
                </div>
                <h2 className={styles.modalTitle}>{readingDoc.title}</h2>
                <div className={styles.modalMetaRow}>
                  {readingDoc.issuing_authority && (
                    <span>🏛️ Cơ quan ban hành: {readingDoc.issuing_authority}</span>
                  )}
                  {readingDoc.issue_date && (
                    <span>📅 Ban hành: {readingDoc.issue_date}</span>
                  )}
                  {readingDoc.signer && <span>✍️ Người ký: {readingDoc.signer}</span>}
                </div>
              </div>
              <button
                type="button"
                className={styles.modalCloseBtn}
                onClick={() => setReadingDoc(null)}
                aria-label="Đóng"
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Toolbar */}
            <div className={styles.modalToolbar}>
              <div className={styles.modalToolGroup}>
                <span>Cỡ chữ:</span>
                <button
                  type="button"
                  className={styles.modalToolBtn}
                  onClick={() => setDocFontSize((s) => Math.max(12, s - 1))}
                  title="Thu nhỏ chữ"
                >
                  <ZoomOut size={13} /> A-
                </button>
                <span style={{ minWidth: '32px', textAlign: 'center' }}>{docFontSize}px</span>
                <button
                  type="button"
                  className={styles.modalToolBtn}
                  onClick={() => setDocFontSize((s) => Math.min(24, s + 1))}
                  title="Phóng to chữ"
                >
                  <ZoomIn size={13} /> A+
                </button>
              </div>

              <div className={styles.modalToolGroup}>
                <button
                  type="button"
                  className={styles.modalToolBtn}
                  onClick={handleCopyDocText}
                >
                  {copiedText ? <Check size={13} color="#10B981" /> : <Copy size={13} />}
                  {copiedText ? 'Đã sao chép' : 'Sao chép văn bản'}
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className={styles.modalBody}>
              {isDocReadingLoading ? (
                <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
                  <Loader2 size={28} className={styles.spinning} style={{ margin: '0 auto 1rem' }} />
                  <p>Đang tải toàn văn văn bản...</p>
                </div>
              ) : readingDoc.content_text ? (
                <div
                  className={styles.modalTextContent}
                  style={{ fontSize: `${docFontSize}px` }}
                >
                  {readingDoc.content_text}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
                  <p>Văn bản này hiện chưa có sẵn dữ liệu toàn văn nội bộ.</p>
                  {readingDoc.original_url && (
                    <a
                      href={readingDoc.original_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: 'var(--color-primary-light)',
                        textDecoration: 'underline',
                        marginTop: '0.5rem',
                        display: 'inline-block',
                      }}
                    >
                      Mở xem trực tiếp tại nguồn văn bản
                    </a>
                  )}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className={styles.modalFooter}>
              {readingDoc.original_url ? (
                <a
                  href={readingDoc.original_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.btnDocOriginal}
                >
                  Xem văn bản gốc tại Cơ sở dữ liệu Quốc gia <ExternalLink size={13} />
                </a>
              ) : (
                <span />
              )}
              <button
                type="button"
                className={styles.resetBtn}
                style={{ padding: '6px 18px', fontSize: '0.85rem' }}
                onClick={() => setReadingDoc(null)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
