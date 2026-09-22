'use client';

import { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Scale, Eye, EyeOff, ArrowRight, Shield, Mail, Lock, User, ArrowLeft, AlertCircle, CheckCircle } from 'lucide-react';
import styles from './page.module.css';
import { api } from '@/lib/api';

type Mode = 'login' | 'register';

function DangNhapContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<Mode>('login');
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get('mode') === 'register') {
      setMode('register');
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      if (mode === 'login') {
        // ── Đăng nhập ──
        const result = await api.login(email, password);

        // Lưu access token vào localStorage
        localStorage.setItem('vinalex_access_token', result.access_token);
        localStorage.setItem('vinalex_user_email', email);
        window.dispatchEvent(new Event('vinalex_auth_change'));

        setSuccess('Đăng nhập thành công! Đang chuyển hướng...');
        setTimeout(() => router.push('/ho-so'), 800);


      } else {
        // ── Đăng ký ──
        if (!name.trim()) {
          setError('Vui lòng nhập họ và tên.');
          return;
        }
        if (password.length < 8) {
          setError('Mật khẩu phải có ít nhất 8 ký tự.');
          return;
        }

        await api.register(name, email, password);
        setSuccess('Tạo tài khoản thành công! Vui lòng đăng nhập.');
        setMode('login');
        setPassword('');
        setName('');
      }
    } catch (err: unknown) {
      // Phân tích lỗi từ API
      let msg = 'Đã có lỗi xảy ra. Vui lòng thử lại.';
      if (err instanceof Error) {
        const text = err.message.toLowerCase();
        if (text.includes('401') || text.includes('unauthorized')) {
          msg = 'Email hoặc mật khẩu không đúng.';
        } else if (text.includes('409') || text.includes('conflict')) {
          msg = 'Email này đã được đăng ký. Vui lòng đăng nhập.';
        } else if (text.includes('422')) {
          msg = 'Thông tin không hợp lệ. Kiểm tra lại email và mật khẩu.';
        } else if (text.includes('fetch') || text.includes('network')) {
          msg = 'Không thể kết nối máy chủ. Kiểm tra Backend đang chạy chưa.';
        }
      }
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      {/* Background */}
      <div className={styles.bgOrb1} />
      <div className={styles.bgOrb2} />

      <div className={styles.container}>
        {/* Back to home */}
        <Link href="/" className={styles.backLink}>
          <ArrowLeft size={16} />
          Về trang chủ
        </Link>

        {/* Card */}
        <div className={styles.card}>
          {/* Logo */}
          <div className={styles.cardHeader}>
            <div className={styles.logoIcon}>
              <Scale size={22} />
            </div>
            <h1 className={styles.cardTitle}>
              {mode === 'login' ? 'Đăng nhập vào VinaLex' : 'Tạo tài khoản VinaLex'}
            </h1>
            <p className={styles.cardSubtitle}>
              {mode === 'login'
                ? 'Chào mừng trở lại! Đăng nhập để tiếp tục.'
                : 'Miễn phí, không giới hạn tính năng cơ bản.'}
            </p>
          </div>

          {/* Mode Toggle */}
          <div className={styles.modeToggle}>
            <button
              id="mode-login"
              className={`${styles.modeBtn} ${mode === 'login' ? styles.modeBtnActive : ''}`}
              onClick={() => { setMode('login'); setError(null); setSuccess(null); }}
            >
              Đăng nhập
            </button>
            <button
              id="mode-register"
              className={`${styles.modeBtn} ${mode === 'register' ? styles.modeBtnActive : ''}`}
              onClick={() => { setMode('register'); setError(null); setSuccess(null); }}
            >
              Đăng ký
            </button>
          </div>

          {/* Thông báo lỗi */}
          {error && (
            <div className={styles.alertError} role="alert">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Thông báo thành công */}
          {success && (
            <div className={styles.alertSuccess} role="alert">
              <CheckCircle size={16} />
              <span>{success}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className={styles.form}>
            {mode === 'register' && (
              <div className={styles.field}>
                <label htmlFor="auth-name" className={styles.label}>
                  Họ và tên
                </label>
                <div className={styles.inputWrapper}>
                  <User size={16} className={styles.inputIcon} />
                  <input
                    id="auth-name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Nguyễn Văn A"
                    className={styles.input}
                    required
                  />
                </div>
              </div>
            )}

            <div className={styles.field}>
              <label htmlFor="auth-email" className={styles.label}>
                Email
              </label>
              <div className={styles.inputWrapper}>
                <Mail size={16} className={styles.inputIcon} />
                <input
                  id="auth-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ten@email.com"
                  className={styles.input}
                  required
                />
              </div>
            </div>

            <div className={styles.field}>
              <div className={styles.labelRow}>
                <label htmlFor="auth-password" className={styles.label}>
                  Mật khẩu
                </label>
                {mode === 'login' && (
                  <button type="button" className={styles.forgotLink}>
                    Quên mật khẩu?
                  </button>
                )}
              </div>
              <div className={styles.inputWrapper}>
                <Lock size={16} className={styles.inputIcon} />
                <input
                  id="auth-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Tối thiểu 8 ký tự"
                  className={styles.input}
                  required
                />
                <button
                  type="button"
                  className={styles.togglePasswordBtn}
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label="Toggle password visibility"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              id="auth-submit-btn"
              type="submit"
              className={styles.submitBtn}
              disabled={isLoading}
            >
              {isLoading ? (
                <span className={styles.loadingSpinner} />
              ) : (
                <>
                  {mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>

          {/* Security note */}
          <div className={styles.secNote}>
            <Shield size={13} />
            <span>Dữ liệu tài khoản được mã hóa và bảo vệ theo chuẩn bảo mật.</span>
          </div>

          {/* Divider */}
          <div className={styles.divider}>
            <span>hoặc tiếp tục mà không cần tài khoản</span>
          </div>

          {/* Guest Option */}
          <Link href="/tro-ly-ai" className={styles.guestBtn} id="auth-guest-btn">
            Dùng thử Trợ lý AI không cần đăng ký
            <ArrowRight size={15} />
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function DangNhapPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94A3B8' }}>Đang tải...</div>}>
      <DangNhapContent />
    </Suspense>
  );
}

