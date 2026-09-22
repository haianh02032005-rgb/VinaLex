import Link from 'next/link';
import { ArrowRight, Eye, Clock } from 'lucide-react';
import { MOCK_PROCEDURES, CATEGORIES } from '@/lib/mockData';
import styles from './ProcedureHighlights.module.css';

export default function ProcedureHighlights() {
  const featured = MOCK_PROCEDURES.slice(0, 4);

  return (
    <section className={styles.section}>
      <div className={styles.container}>
        {/* Header */}
        <div className={styles.header}>
          <div>
            <p className={styles.eyebrow}>Tra cứu thủ tục</p>
            <h2 className={styles.title}>Thủ tục được tra cứu nhiều nhất</h2>
          </div>
          <Link href="/thu-tuc" className={styles.viewAll}>
            Xem tất cả <ArrowRight size={16} />
          </Link>
        </div>

        {/* Categories */}
        <div className={styles.categories}>
          {CATEGORIES.map((cat) => (
            <Link
              key={cat.id}
              href={`/thu-tuc?cat=${cat.slug}`}
              className={styles.catChip}
              style={{ '--cat-color': cat.color } as React.CSSProperties}
            >
              <span>{cat.icon}</span>
              <span>{cat.label}</span>
              <span className={styles.catCount}>{cat.count}</span>
            </Link>
          ))}
        </div>

        {/* Procedure Cards */}
        <div className={styles.grid}>
          {featured.map((proc) => (
            <Link
              key={proc.id}
              href={`/thu-tuc/${proc.slug}`}
              className={styles.procCard}
            >
              <div className={styles.procTop}>
                <span className={styles.procCategory}>{proc.category}</span>
                <span className={styles.procLevel}>{proc.level}</span>
              </div>
              <h3 className={styles.procTitle}>{proc.title}</h3>
              <p className={styles.procDesc}>{proc.description}</p>
              <div className={styles.procMeta}>
                <div className={styles.procMetaItem}>
                  <Clock size={13} />
                  <span>{proc.processingTime}</span>
                </div>
                <div className={styles.procMetaItem}>
                  <Eye size={13} />
                  <span>{proc.viewCount.toLocaleString('vi-VN')}</span>
                </div>
                <span className={styles.procFee}>{proc.fee}</span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
