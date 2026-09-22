import { STATS } from '@/lib/mockData';
import styles from './StatsSection.module.css';

export default function StatsSection() {
  return (
    <section className={styles.section}>
      <div className={styles.container}>
        {STATS.map((stat, i) => (
          <div key={i} className={styles.statCard}>
            <span className={styles.icon}>{stat.icon}</span>
            <span className={styles.value}>{stat.value}</span>
            <span className={styles.label}>{stat.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
