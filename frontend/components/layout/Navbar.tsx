'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Scale, Menu, X, ChevronDown, Shield, User, LogOut } from 'lucide-react';
import styles from './Navbar.module.css';

const NAV_LINKS = [
  { href: '/thu-tuc', label: 'Thủ tục', hasDropdown: true },
  { href: '/tro-ly-ai', label: 'Trợ lý AI' },
  { href: '/ho-so', label: 'Hồ sơ của tôi' },
];

export default function Navbar() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const pathname = usePathname();
  const router = useRouter();

  // Kiểm tra trạng thái đăng nhập
  const checkAuth = () => {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('vinalex_access_token');
    const email = localStorage.getItem('vinalex_user_email') || '';
    if (token) {
      setIsLoggedIn(true);
      setUserEmail(email);
    } else {
      setIsLoggedIn(false);
      setUserEmail('');
    }
  };

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Lắng nghe sự kiện đăng nhập / đăng xuất
  useEffect(() => {
    checkAuth();
    const handleAuthChange = () => checkAuth();
    window.addEventListener('vinalex_auth_change', handleAuthChange);
    window.addEventListener('storage', handleAuthChange);
    return () => {
      window.removeEventListener('vinalex_auth_change', handleAuthChange);
      window.removeEventListener('storage', handleAuthChange);
    };
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('vinalex_access_token');
    localStorage.removeItem('vinalex_user_email');
    localStorage.removeItem('vinalex_user_name');
    window.dispatchEvent(new Event('vinalex_auth_change'));
    setIsLoggedIn(false);
    setUserEmail('');
    router.push('/dang-nhap');
  };

  const displayName = userEmail ? userEmail.split('@')[0] : 'Tài khoản';

  return (
    <nav className={`${styles.navbar} ${isScrolled ? styles.scrolled : ''}`}>
      <div className={styles.container}>
        {/* Logo */}
        <Link href="/" className={styles.logo}>
          <div className={styles.logoIcon}>
            <Scale size={20} />
          </div>
          <span className={styles.logoText}>
            Vina<span className={styles.logoAccent}>Lex</span>
          </span>
        </Link>

        {/* Desktop Links */}
        <div className={styles.desktopLinks}>
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`${styles.navLink} ${pathname.startsWith(link.href) ? styles.active : ''}`}
            >
              {link.label}
              {link.hasDropdown && <ChevronDown size={14} />}
            </Link>
          ))}
        </div>

        {/* Right Section */}
        <div className={styles.rightSection}>
          <div className={styles.securityBadge}>
            <Shield size={12} />
            <span>Bảo mật NĐ 13</span>
          </div>

          {isLoggedIn ? (
            <div className={styles.userSection}>
              <Link href="/ho-so" className={styles.userProfileBtn} title={`Đăng nhập với: ${userEmail}`}>
                <div className={styles.userAvatar}>
                  <User size={14} />
                </div>
                <span className={styles.userNameText}>{displayName}</span>
              </Link>
              <button
                onClick={handleLogout}
                className={styles.logoutBtn}
                title="Đăng xuất khỏi hệ thống"
              >
                <LogOut size={14} />
                <span>Thoát</span>
              </button>
            </div>
          ) : (
            <>
              <Link href="/dang-nhap" className={styles.loginBtn}>
                Đăng nhập
              </Link>
              <Link href="/dang-nhap?mode=register" className={styles.ctaBtn}>
                Dùng thử miễn phí
              </Link>
            </>
          )}
        </div>

        {/* Mobile Menu Button */}
        <button
          id="navbar-mobile-toggle"
          className={styles.mobileToggle}
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div className={styles.mobileMenu}>
          {NAV_LINKS.map((link) => (
            <Link key={link.href} href={link.href} className={styles.mobileLink}>
              {link.label}
            </Link>
          ))}
          <div className={styles.mobileDivider} />
          {isLoggedIn ? (
            <>
              <Link href="/ho-so" className={styles.mobileLink}>
                👤 {displayName} ({userEmail})
              </Link>
              <button
                onClick={handleLogout}
                className={styles.mobileLink}
                style={{ textAlign: 'left', color: '#EF4444', background: 'transparent', border: 'none', cursor: 'pointer' }}
              >
                🚪 Đăng xuất
              </button>
            </>
          ) : (
            <>
              <Link href="/dang-nhap" className={styles.mobileLink}>
                Đăng nhập
              </Link>
              <Link href="/dang-nhap?mode=register" className={styles.mobileCta}>
                Dùng thử miễn phí
              </Link>
            </>
          )}
        </div>
      )}
    </nav>
  );
}

