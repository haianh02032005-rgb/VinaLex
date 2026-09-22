// VinaLex — Next.js API Route: Fallback thủ tục từ crawled_procedures.json
// Được gọi khi Backend FastAPI offline hoặc chưa khởi động.
// Phục vụ dữ liệu 122+ thủ tục thực tế đã cào từ thuvienphapluat.vn.

import { NextRequest, NextResponse } from 'next/server';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

function loadProcedures(): Record<string, unknown>[] {
  // Tìm file ở nhiều vị trí có thể (root hoặc relative)
  const candidates = [
    join(process.cwd(), '..', 'data', 'crawled_procedures.json'),
    join(process.cwd(), 'data', 'crawled_procedures.json'),
    join(process.cwd(), '..', '..', 'data', 'crawled_procedures.json'),
  ];

  for (const filePath of candidates) {
    if (existsSync(filePath)) {
      try {
        const raw = readFileSync(filePath, 'utf-8');
        return JSON.parse(raw) as Record<string, unknown>[];
      } catch {
        continue;
      }
    }
  }
  return [];
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const slug = searchParams.get('slug');

  if (!slug) {
    return NextResponse.json({ error: 'slug is required' }, { status: 400 });
  }

  const procedures = loadProcedures();

  if (procedures.length === 0) {
    return NextResponse.json(
      { error: 'Fallback data file not found' },
      { status: 503 }
    );
  }

  // Tìm thủ tục theo slug
  const found = procedures.find(
    (p) => (p as { slug?: string }).slug === slug
  );

  if (!found) {
    return NextResponse.json(
      { error: `Procedure "${slug}" not found in fallback data` },
      { status: 404 }
    );
  }

  // Normalise: thêm các field bắt buộc nếu thiếu
  const idx = procedures.indexOf(found) + 1;
  const normalised = {
    id: idx,
    updated_at: new Date().toISOString(),
    view_count: 0,
    is_published: true,
    ...found,
  };

  return NextResponse.json(normalised, {
    headers: {
      'Cache-Control': 'public, max-age=300, stale-while-revalidate=600',
    },
  });
}
