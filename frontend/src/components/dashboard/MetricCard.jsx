/**
 * components/dashboard/MetricCard.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Glassmorphic KPI card with:
 *   - Gradient accent icon background
 *   - Large mono-spaced value display
 *   - Positive/negative change badge
 *   - Hover: subtle scale + border glow transition
 *
 * Props:
 *   label   {string}  — Card label e.g. "Portfolio Value"
 *   value   {string}  — Formatted display value e.g. "PKR 2,345,680"
 *   change  {string}  — Change label e.g. "+12,450" or "−2,200"
 *   trend   {"up"|"down"|"neutral"}
 *   icon    {string}  — Unicode symbol or emoji
 *   accent  {string}  — CSS color override for the icon bg (optional)
 * ─────────────────────────────────────────────────────────────────────────────
 */

import styles from './MetricCard.module.css'

export default function MetricCard({ label, value, change, trend = 'neutral', icon = '◈', accent }) {
  const trendClass = {
    up:      styles.trendUp,
    down:    styles.trendDown,
    neutral: styles.trendNeutral,
  }[trend]

  const trendArrow = { up: '▲', down: '▼', neutral: '—' }[trend]

  return (
    <article className={styles.card} aria-label={`${label}: ${value}`}>
      {/* Subtle top-edge glow bar */}
      <div
        className={styles.glowBar}
        style={{ background: accent || 'var(--accent-cyan)' }}
      />

      {/* Icon */}
      <div
        className={styles.iconWrap}
        style={{
          background: accent
            ? `${accent}22`
            : 'rgba(0, 212, 255, 0.12)',
          color: accent || 'var(--accent-cyan)',
          borderColor: accent
            ? `${accent}44`
            : 'rgba(0, 212, 255, 0.25)',
        }}
      >
        <span className={styles.icon}>{icon}</span>
      </div>

      {/* Content */}
      <div className={styles.content}>
        <span className={styles.label}>{label}</span>
        <span className={`${styles.value} mono`}>{value}</span>

        {/* Change badge */}
        {change && (
          <div className={`${styles.change} ${trendClass}`}>
            <span className={styles.arrow}>{trendArrow}</span>
            <span className={`${styles.changeText} mono`}>{change}</span>
          </div>
        )}
      </div>
    </article>
  )
}
