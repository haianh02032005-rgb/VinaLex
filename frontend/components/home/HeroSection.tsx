'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Search, ArrowRight, Shield, Zap, FileCheck } from 'lucide-react';
import { useRouter } from 'next/navigation';
import styles from './HeroSection.module.css';

const QUICK_SEARCHES = [
  'Cấp sổ đỏ', 'Đăng ký khai sinh', 'Thành lập công ty', 'Bằng lái xe', 'Tạm trú',
];

export default function HeroSection() {
  const [query, setQuery] = useState('');
  const router = useRouter();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/thu-tuc?search=${encodeURIComponent(query)}`);
    }
  };

  return (
    <section className={styles.hero}>
      {/* Background effects */}
      <div className={styles.bgOrb1} />
      <div className={styles.bgOrb2} />
      <div className={styles.bgGrid} />

      <div className={styles.container}>
        {/* Badge */}
        <div className={styles.topBadge + ' animate-fade-in-up'}>
          <Zap size={13} fill="currentColor" />
          <span>Trợ lý AI Pháp lý — Chạy 100% nội bộ, không gửi dữ liệu ra ngoài</span>
        </div>

        {/* Heading */}
        <h1 className={styles.heading + ' animate-fade-in-up delay-100'}>
          Giải quyết thủ tục hành chính<br />
          <span className="text-gradient">nhanh hơn với AI</span>
        </h1>

        <p className={styles.subheading + ' animate-fade-in-up delay-200'}>
          Tra cứu hơn <strong>2.500+</strong> thủ tục hành chính, tư vấn pháp lý tức thì và
          kiểm tra hồ sơ tự động qua OCR — bảo mật tuyệt đối theo Nghị định 13/2023/NĐ-CP.
        </p>

        {/* Search Box */}
        <form
          onSubmit={handleSearch}
          className={styles.searchBox + ' animate-fade-in-up delay-300'}
        >
          <div className={styles.searchInner}>
            <Search size={20} className={styles.searchIcon} />
            <input
              id="hero-search-input"
              type="text"
              placeholder="Tìm thủ tục... ví dụ: đăng ký khai sinh, cấp sổ đỏ..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className={styles.searchInput}
            />
            <button
              id="hero-search-btn"
              type="submit"
              className={styles.searchBtn}
            >
              Tìm kiếm
              <ArrowRight size={16} />
            </button>
          </div>
        </form>

        {/* Quick searches */}
        <div className={styles.quickSearch + ' animate-fade-in-up delay-400'}>
          <span className={styles.quickLabel}>Tìm nhiều nhất:</span>
          {QUICK_SEARCHES.map((term) => (
            <button
              key={term}
              className={styles.quickBtn}
              onClick={() => router.push(`/thu-tuc?search=${encodeURIComponent(term)}`)}
            >
              {term}
            </button>
          ))}
        </div>

        {/* Trust Row */}
        <div className={styles.trustRow + ' animate-fade-in-up delay-500'}>
          <div className={styles.trustItem}>
            <Shield size={15} className={styles.trustIcon} />
            <span>Zero dữ liệu ra ngoài</span>
          </div>
          <div className={styles.trustDivider} />
          <div className={styles.trustItem}>
            <FileCheck size={15} className={styles.trustIcon} />
            <span>Cập nhật theo VBPL quốc gia</span>
          </div>
          <div className={styles.trustDivider} />
          <div className={styles.trustItem}>
            <Zap size={15} className={styles.trustIconAccent} />
            <span>Phản hồi trong vài giây</span>
          </div>
        </div>
      </div>
    </section>
  );
}
