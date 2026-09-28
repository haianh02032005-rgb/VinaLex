import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import ProcedureDetailPage from './ProcedureDetailClient';

interface StaticProcedure {
  slug?: string;
}

function loadStaticSlugs(): string[] {
  const candidates = [
    join(process.cwd(), '..', 'data', 'crawled_procedures.json'),
    join(process.cwd(), '..', 'data', 'dvc_procedures.json'),
  ];

  const slugs = new Set<string>();
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
