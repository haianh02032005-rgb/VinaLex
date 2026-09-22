import Link from 'next/link';
import { Search, MessageSquare, FolderOpen, ArrowRight } from 'lucide-react';
import styles from './FeatureCards.module.css';

const FEATURES = [
  {
    icon: <Search size={28} />,
    color: '#4F7FFA',
    gradient: 'linear-gradient(135deg, rgba(79,127,250,0.15), rgba(79,127,250,0.05))',
    border: 'rgba(79,127,250,0.25)',
    title: 'Tra cứu Thủ tục',
    description:
      'Kho dữ liệu hơn 2.500 thủ tục hành chính được phân loại rõ ràng, cập nhật theo văn bản pháp luật mới nhất. Tìm thấy đúng thủ tục trong vài giây.',
    link: '/thu-tuc',
    linkLabel: 'Tra cứu ngay',
    highlights: ['2.500+ thủ tục', 'Cập nhật real-time', 'Tìm kiếm thông minh'],
  },
  {
    icon: <MessageSquare size={28} />,
    color: '#06B6D4',
    gradient: 'linear-gradient(135deg, rgba(6,182,212,0.15), rgba(6,182,212,0.05))',
    border: 'rgba(6,182,212,0.25)',
    title: 'Trợ lý AI Pháp lý',
    description:
      'Chatbot RAG được huấn luyện trên kho văn bản luật Việt Nam. Tải hồ sơ lên để AI bóc tách dữ liệu OCR và kiểm tra tính hợp lệ tức thì.',
    link: '/tro-ly-ai',
    linkLabel: 'Thử ngay',
    highlights: ['RAG + LLM local', 'OCR tài liệu', 'Bảo mật 100%'],
  },
  {
    icon: <FolderOpen size={28} />,
    color: '#8B5CF6',
    gradient: 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(139,92,246,0.05))',
    border: 'rgba(139,92,246,0.25)',
    title: 'Quản lý Hồ sơ',
    description:
      'Không gian làm việc cá nhân để theo dõi tiến độ hồ sơ, lưu trữ kết quả OCR và tải xuống biểu mẫu được điền tự động bởi AI.',
    link: '/ho-so',
    linkLabel: 'Xem hồ sơ',
    highlights: ['Theo dõi tiến độ', 'Tải biểu mẫu tự động', 'Lịch sử hồ sơ'],
  },
];

export default function FeatureCards() {
  return (
    <section className={styles.section}>
      <div className={styles.container}>
        <div className={styles.header}>
          <p className={styles.eyebrow}>Tính năng nổi bật</p>
          <h2 className={styles.title}>
            Mọi thứ bạn cần để{' '}
            <span className="text-gradient">xử lý thủ tục nhanh hơn</span>
          </h2>
          <p className={styles.subtitle}>
            Kết hợp tra cứu thông tin, tư vấn AI và quản lý hồ sơ trong một nền tảng duy nhất.
          </p>
        </div>

        <div className={styles.grid}>
          {FEATURES.map((feat, i) => (
            <div
              key={i}
              className={styles.card}
              style={{
                background: feat.gradient,
                borderColor: feat.border,
              }}
            >
              <div
                className={styles.iconBox}
                style={{ color: feat.color, background: `${feat.color}15` }}
              >
                {feat.icon}
              </div>
              <h3 className={styles.cardTitle}>{feat.title}</h3>
              <p className={styles.cardDesc}>{feat.description}</p>
              <ul className={styles.highlights}>
                {feat.highlights.map((h) => (
                  <li key={h} className={styles.highlight} style={{ color: feat.color }}>
                    <span className={styles.highlightDot} style={{ background: feat.color }} />
                    {h}
                  </li>
                ))}
              </ul>
              <Link href={feat.link} className={styles.cardLink} style={{ color: feat.color }}>
                {feat.linkLabel}
                <ArrowRight size={15} />
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
