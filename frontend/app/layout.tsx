import type { Metadata, Viewport } from 'next';
import './globals.css';
import Navbar from '@/components/layout/Navbar';
import Footer from '@/components/layout/Footer';

export const viewport: Viewport = {
  themeColor: '#2563eb',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
};

export const metadata: Metadata = {
  title: {
    default: 'VinaLex — Cổng Tư vấn Pháp lý & Thủ tục Hành chính Số Quốc gia',
    template: '%s | VinaLex',
  },
  description:
    'VinaLex cung cấp giải pháp tra cứu 615+ thủ tục hành chính, 260+ văn bản pháp luật, trợ lý AI tư vấn và sinh biểu mẫu PDF chuẩn Nghị định 30/2020/NĐ-CP.',
  keywords: ['thủ tục hành chính', 'pháp lý', 'tư vấn luật', 'hồ sơ dịch vụ công', 'sổ đỏ', 'CCCD', 'biểu mẫu PDF', 'VinaLex'],
  authors: [{ name: 'VinaLex Engineering Team' }],
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title: 'VinaLex — Cổng Tư vấn Pháp lý & Thủ tục Hành chính Số',
    description: 'Tra cứu thủ tục, tải biểu mẫu PDF chuẩn quốc gia và tư vấn pháp lý AI tức thì.',
    type: 'website',
    locale: 'vi_VN',
    siteName: 'VinaLex',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body>
        <Navbar />
        <main style={{ paddingTop: 'var(--navbar-height)' }}>
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
