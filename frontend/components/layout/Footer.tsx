import Link from 'next/link';
import { Scale, Shield, Github, Facebook, Mail, Phone } from 'lucide-react';
import styles from './Footer.module.css';

const FOOTER_LINKS = {
  'Thủ tục': [
    { label: 'Đất đai & Nhà ở', href: '/thu-tuc?cat=dat-dai' },
    { label: 'Hộ tịch', href: '/thu-tuc?cat=ho-tich' },
    { label: 'Doanh nghiệp', href: '/thu-tuc?cat=doanh-nghiep' },
    { label: 'Giao thông', href: '/thu-tuc?cat=giao-thong' },
    { label: 'Thuế & Tài chính', href: '/thu-tuc?cat=thue' },
  ],
  'Tính năng': [
    { label: 'Trợ lý AI Pháp lý', href: '/tro-ly-ai' },
    { label: 'Kiểm tra Hồ sơ OCR', href: '/tro-ly-ai#ocr' },
    { label: 'Quản lý Hồ sơ', href: '/ho-so' },
    { label: 'Tải biểu mẫu', href: '/ho-so#forms' },
  ],
  'Hỗ trợ': [
    { label: 'Hướng dẫn sử dụng', href: '/huong-dan' },
    { label: 'Câu hỏi thường gặp', href: '/faq' },
    { label: 'Chính sách bảo mật', href: '/bao-mat' },
    { label: 'Điều khoản dịch vụ', href: '/dieu-khoan' },
  ],
};

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.container}>
        {/* Top section */}
        <div className={styles.top}>
          {/* Brand */}
          <div className={styles.brand}>
            <Link href="/" className={styles.logo}>
              <div className={styles.logoIcon}>
                <Scale size={18} />
              </div>
              <span>Vina<span className={styles.logoAccent}>Lex</span></span>
            </Link>
            <p className={styles.tagline}>
              Nền tảng tư vấn pháp lý & thủ tục hành chính dành cho người dân Việt Nam.
              Bảo mật tuyệt đối, hoạt động hoàn toàn nội bộ (Local AI).
            </p>
            <div className={styles.badge}>
              <Shield size={13} />
              <span>Tuân thủ Nghị định 13/2023/NĐ-CP</span>
            </div>
            <div className={styles.socials}>
              <a href="https://facebook.com" target="_blank" rel="noopener noreferrer" className={styles.socialBtn}>
                <Facebook size={16} />
              </a>
              <a href="mailto:support@vinalex.vn" className={styles.socialBtn}>
                <Mail size={16} />
              </a>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer" className={styles.socialBtn}>
                <Github size={16} />
              </a>
            </div>
          </div>

          {/* Links */}
          {Object.entries(FOOTER_LINKS).map(([section, links]) => (
            <div key={section} className={styles.linkGroup}>
              <h3 className={styles.linkGroupTitle}>{section}</h3>
              <ul className={styles.linkList}>
                {links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className={styles.link}>
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {/* Contact */}
          <div className={styles.linkGroup}>
            <h3 className={styles.linkGroupTitle}>Liên hệ</h3>
            <div className={styles.contactList}>
              <div className={styles.contactItem}>
                <Phone size={14} />
                <span>1900 1800</span>
              </div>
              <div className={styles.contactItem}>
                <Mail size={14} />
                <span>support@vinalex.vn</span>
              </div>
            </div>
            <div className={styles.techStack}>
              <span className={styles.techBadge}>FastAPI</span>
              <span className={styles.techBadge}>Next.js</span>
              <span className={styles.techBadge}>Ollama</span>
              <span className={styles.techBadge}>VietOCR</span>
            </div>
          </div>
        </div>

        {/* Bottom */}
        <div className={styles.bottom}>
          <p>© {new Date().getFullYear()} VinaLex. Được phát triển với mục đích phi thương mại.</p>
          <p className={styles.bottomRight}>
            Dữ liệu pháp luật theo Cơ sở dữ liệu quốc gia về pháp luật (vbpl.vn)
          </p>
        </div>
      </div>
    </footer>
  );
}
