/**
 * components/dashboard/SectionHeader.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Reusable scroll-triggered section header component.
 *
 * Props:
 *   label    {string} — small all-caps eyebrow label (accent cyan)
 *   title    {string} — main heading
 *   subtitle {string} — optional sub-text
 * ─────────────────────────────────────────────────────────────────────────────
 */

import useGSAPScrollTrigger from '../../hooks/useGSAPScrollTrigger'
import styles               from './SectionHeader.module.css'

export default function SectionHeader({ label, title, subtitle }) {
  const headerRef = useGSAPScrollTrigger({
    start:    'top 88%',
    yOffset:  20,
    duration: 0.7,
    ease:     'power3.out',
  })

  return (
    <header ref={headerRef} className={styles.header}>
      {label && <span className={styles.label}>{label}</span>}
      <h2 className={styles.title}>{title}</h2>
      {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      <div className={styles.divider} />
    </header>
  )
}
