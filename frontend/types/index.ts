// VinaLex — TypeScript Type Definitions

export interface Procedure {
  id: string;
  slug: string;
  title: string;
  category: string;
  categorySlug: string;
  description: string;
  steps: ProcedureStep[];
  documents: string[];
  processingTime: string;
  fee: string;
  agency: string;
  level: 'Trung ương' | 'Tỉnh/TP' | 'Quận/Huyện' | 'Phường/Xã';
  tags: string[];
  updatedAt: string;
  viewCount: number;
}

export interface ProcedureStep {
  index: number;
  title: string;
  description: string;
  duration?: string;
}

export interface Category {
  id: string;
  slug: string;
  label: string;
  icon: string;
  count: number;
  color: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: string[];
  isStreaming?: boolean;
}

export interface OcrResult {
  success: boolean;
  documentType: string;
  extractedFields: Record<string, string>;
  rawText: string;
  confidence: number;
  processingTime: number;
}

export interface UserFile {
  id: string;
  name: string;
  type: string;
  size: number;
  status: 'pending' | 'processing' | 'done' | 'error';
  ocrResult?: OcrResult;
  uploadedAt: Date;
}

export interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

export interface ApiResponse<T> {
  data: T;
  message: string;
  success: boolean;
}
