import type { Metadata } from 'next';
import './globals.css';
import Navbar from '@/components/layout/Navbar';
import Footer from '@/components/layout/Footer';

export const metadata: Metadata = {
  title: {
    default: 'VinaLex — Nền tảng Tư vấn Pháp lý & Thủ tục Hành chính',
    template: '%s | VinaLex',
  },
  description:
    'VinaLex cung cấp thông tin thủ tục hành chính công, tư vấn pháp lý bằng AI và hỗ trợ bóc tách dữ liệu hồ sơ tự động, bảo mật tuyệt đối.',
  keywords: ['thủ tục hành chính', 'pháp lý', 'tư vấn luật', 'hồ sơ', 'CMND', 'đất đai'],
  authors: [{ name: 'VinaLex Team' }],
  openGraph: {
    title: 'VinaLex — Nền tảng Tư vấn Pháp lý',
    description: 'Tra cứu thủ tục, tư vấn pháp lý bằng AI — bảo mật tuyệt đối.',
    type: 'website',
    locale: 'vi_VN',
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
