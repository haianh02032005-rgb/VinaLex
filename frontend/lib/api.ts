// VinaLex — API Client (kết nối FastAPI Backend)

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options?: RequestInit
  ): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!res.ok) {
      throw new Error(`API Error ${res.status}: ${res.statusText}`);
    }

    return res.json();
  }

  // ── Procedures ──
  async getProcedures(params?: {
    category?: string;
    search?: string;
    page?: number;
    limit?: number;
  }) {
    const query = new URLSearchParams();
    if (params?.category) query.set('category', params.category);
    if (params?.search)   query.set('search', params.search);
    if (params?.page)     query.set('page', String(params.page));
    if (params?.limit)    query.set('limit', String(params.limit));

    return this.request<{ items: unknown[]; total: number }>(
      `/procedures?${query.toString()}`
    );
  }

  async getProcedureBySlug(slug: string) {
    return this.request<unknown>(`/procedures/${slug}`);
  }

  // ── AI Chat ──
  async sendChatMessage(message: string, sessionId: string) {
    return this.request<{ answer: string; sources: string[] }>('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId }),
    });
  }

  // ── OCR Upload ──
  // session_id bắt buộc truyền vào để Backend xác định session trên Redis
  // và thực thi xóa tự động sau khi trả kết quả (tuân thủ ARCHITECTURE.md Data Flow)
  async uploadDocumentForOcr(file: File, sessionId: string) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId); // Backend dùng để cleanup Redis

    const res = await fetch(`${this.baseUrl}/ai/ocr`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      throw new Error(`OCR Error ${res.status}: ${res.statusText}`);
    }

    return res.json();
  }

  // ── Document Templates (PDF) ──
  async downloadDocumentTemplate(
    docName: string,
    procedureTitle = '',
    slug = '',
    preview = false
  ): Promise<Blob> {
    const params = new URLSearchParams({
      doc_name: docName,
      title: procedureTitle,
      slug: slug,
      preview: String(preview),
    });

    const primaryUrl = `${this.baseUrl}/procedures/download-template?${params.toString()}`;
    const fallbackUrl = `/api/v1/procedures/download-template?${params.toString()}`;

    try {
      const res = await fetch(primaryUrl);
      if (res.ok) {
        return await res.blob();
      }
      throw new Error(`Download Error ${res.status}: ${res.statusText}`);
    } catch (primaryErr) {
      if (typeof window !== 'undefined') {
        try {
          const fallbackRes = await fetch(fallbackUrl);
          if (fallbackRes.ok) {
            return await fallbackRes.blob();
          }
        } catch {
          // Fallback also failed
        }
      }
      throw primaryErr;
    }
  }

  // ── Document Verification (OCR + Match) ──
  async verifyDocument(
    file: File,
    expectedDoc: string,
    procedureSlug: string,
    procedureTitle: string,
    sessionId: string
  ): Promise<{
    is_valid: boolean;
    status: 'passed' | 'rejected';
    document_type: string;
    expected_document: string;
    extracted_fields: Record<string, string>;
    validation_checks: Array<{ check: string; status: 'passed' | 'failed' | 'warning'; note: string }>;
    errors: string[];
    suggestions: string;
    processing_time_ms: number;
    session_id: string;
  }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('procedure_slug', procedureSlug);
    formData.append('procedure_title', procedureTitle);
    formData.append('expected_document', expectedDoc);
    formData.append('session_id', sessionId);

    const res = await fetch(`${this.baseUrl}/ai/verify-document`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => '');
      throw new Error(`Verification Error ${res.status}: ${errText || res.statusText}`);
    }

    return res.json();
  }

  // ── Auth ──
  async login(email: string, password: string) {
    return this.request<{ access_token: string; token_type: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async register(name: string, email: string, password: string) {
    return this.request<{ id: string; email: string }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    });
  }

  async getMe(token: string) {
    return this.request<{ id: number; name: string; email: string; is_active: boolean }>(
      '/auth/me',
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );
  }

  async getUserProcedures(token: string) {
    return this.request<
      Array<{
        id: number;
        procedure_id: number;
        procedure_title: string;
        progress: number;
        status: string;
        due_date?: string | null;
        created_at: string;
      }>
    >('/auth/me/procedures', {
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  async saveUserProcedure(token: string, procedureId: number, notes?: string) {
    return this.request<{
      id: number;
      procedure_id: number;
      procedure_title: string;
      progress: number;
      status: string;
      due_date?: string | null;
      created_at: string;
    }>('/auth/me/procedures', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ procedure_id: procedureId, notes }),
    });
  }

  async deleteUserProcedure(token: string, userProcId: number) {
    return this.request<{ message: string; id: number }>(`/auth/me/procedures/${userProcId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
  }


  // ── Admin CMS ──
  // Tất cả admin request đều cần X-Admin-Key header

  private getAdminHeaders(adminKey: string): HeadersInit {
    return { 'X-Admin-Key': adminKey };
  }

  async adminGetAllProcedures(adminKey: string, page = 1, limit = 50) {
    return this.request<{ items: unknown[]; total: number; page: number; limit: number }>(
      `/admin/procedures?page=${page}&limit=${limit}`,
      { headers: this.getAdminHeaders(adminKey) }
    );
  }

  async adminCreateProcedure(adminKey: string, data: unknown) {
    return this.request<unknown>('/procedures', {
      method: 'POST',
      headers: this.getAdminHeaders(adminKey),
      body: JSON.stringify(data),
    });
  }

  async adminUpdateProcedure(adminKey: string, slug: string, data: unknown) {
    return this.request<unknown>(`/procedures/${slug}`, {
      method: 'PUT',
      headers: this.getAdminHeaders(adminKey),
      body: JSON.stringify(data),
    });
  }

  async adminDeleteProcedure(adminKey: string, slug: string) {
    const res = await fetch(`${this.baseUrl}/procedures/${slug}`, {
      method: 'DELETE',
      headers: { 'X-Admin-Key': adminKey },
    });
    if (!res.ok) throw new Error(`Delete Error ${res.status}`);
  }

  async adminSyncLegalDoc(
    adminKey: string,
    content: string,
    source: string,
    documentType = 'Văn bản pháp luật'
  ) {
    return this.request<{ success: boolean; message: string; chunks_synced: number }>(
      '/admin/sync-legal-doc',
      {
        method: 'POST',
        headers: this.getAdminHeaders(adminKey),
        body: JSON.stringify({ content, source, document_type: documentType }),
      }
    );
  }

  async adminGetSyncStatus(adminKey: string) {
    return this.request<{ qdrant_host: string; collection: string; status: string }>(
      '/admin/sync-status',
      { headers: this.getAdminHeaders(adminKey) }
    );
  }

  async adminGetStats(adminKey: string) {
    return this.request<{
      procedures: { total: number; published: number; draft: number };
      total_views: number;
      vector_db: { status: string };
    }>('/admin/stats', { headers: this.getAdminHeaders(adminKey) });
  }
}

export const api = new ApiClient(API_BASE_URL);
export default api;

