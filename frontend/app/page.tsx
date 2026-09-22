import HeroSection from '@/components/home/HeroSection';
import FeatureCards from '@/components/home/FeatureCards';
import StatsSection from '@/components/home/StatsSection';
import ProcedureHighlights from '@/components/home/ProcedureHighlights';
import CtaBanner from '@/components/home/CtaBanner';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'VinaLex — Nền tảng Tư vấn Pháp lý & Thủ tục Hành chính',
  description:
    'Tra cứu thủ tục hành chính, tư vấn pháp lý bằng AI, kiểm tra hồ sơ tự động — bảo mật tuyệt đối theo Nghị định 13/2023.',
};

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <StatsSection />
      <FeatureCards />
      <ProcedureHighlights />
      <CtaBanner />
    </>
  );
}
