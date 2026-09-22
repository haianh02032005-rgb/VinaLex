import Link from 'next/link';
import { ArrowRight, Bot, Shield } from 'lucide-react';
import styles from './CtaBanner.module.css';

export default function CtaBanner() {
  return (
    <section className={styles.section}>
      <div className={styles.container}>
        <div className={styles.card}>
          <div className={styles.bgOrb} />

          <div className={styles.iconRow}>
            <div className={styles.iconCircle}>
              <Bot size={28} />
            </div>
          </div>

          <h2 className={styles.title}>
            Bắt đầu tư vấn pháp lý ngay{' '}
            <span className="text-gradient">cùng AI</span>
          </h2>
          <p className={styles.subtitle}>
            Đặt câu hỏi về thủ tục, tải hồ sơ lên để AI kiểm tra — miễn phí, không cần đăng ký, bảo mật tuyệt đối.
          </p>

          <div className={styles.actions}>
            <Link href="/tro-ly-ai" className={styles.primaryBtn} id="cta-ai-btn">
              <Bot size={18} />
              Thử Trợ lý AI ngay
              <ArrowRight size={16} />
            </Link>
            <Link href="/thu-tuc" className={styles.secondaryBtn} id="cta-procedures-btn">
              Xem tất cả thủ tục
            </Link>
          </div>

          <div className={styles.footnote}>
            <Shield size={13} />
            <span>Chạy 100% trên máy chủ nội bộ — Không gửi dữ liệu ra bên ngoài — Tuân thủ NĐ 13/2023</span>
          </div>
        </div>
      </div>
    </section>
  );
}
