import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import ProcedureDetailPage from './ProcedureDetailClient';

import { MOCK_PROCEDURES } from '@/lib/mockData';

interface StaticProcedure {
  slug?: string;
}

function loadStaticSlugs(): string[] {
  const candidates = [
    join(process.cwd(), '..', 'data', 'all_procedures.json'),
    join(process.cwd(), '..', 'data', 'dvc_procedures.json'),
    join(process.cwd(), '..', 'data', 'crawled_procedures.json'),
    join(process.cwd(), 'public', 'data', 'all_procedures.json'),
    join(process.cwd(), 'public', 'data', 'dvc_procedures.json'),
    join(process.cwd(), 'public', 'data', 'crawled_procedures.json'),
  ];

  const slugs = new Set<string>();

  // Thêm tất cả slug từ MOCK_PROCEDURES để đảm bảo không bao giờ 404
  MOCK_PROCEDURES.forEach((p) => {
    if (p.slug) slugs.add(p.slug);
  });
  slugs.add('cap-giay-chung-nhan-quyen-su-dung-dat');
  slugs.add('dang-ky-khai-sinh');

  for (const filePath of candidates) {
    if (!existsSync(filePath)) continue;
    try {
      const rows = JSON.parse(readFileSync(filePath, 'utf-8')) as StaticProcedure[];
      rows.forEach((row) => {
        if (row.slug) slugs.add(row.slug);
      });
    } catch {
      // Skip malformed optional data files during static export.
    }
  }

  return Array.from(slugs);
}

export function generateStaticParams() {
  return loadStaticSlugs().map((slug) => ({ slug }));
}

export default function Page() {
  return <ProcedureDetailPage />;
}
