/**
 * components/layout/Sidebar.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Fixed dark-glass navigation sidebar.
 *
 * Features:
 *   - Glassmorphic fill with cyan-accent active state
 *   - GSAP entrance animation on mount (slides in from left)
 *   - Active nav item: left cyan border + glow
 *   - PSX branding at top
 *   - User profile stub at bottom
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useState }        from 'react'
import useAnimateEntrance  from '../../hooks/useAnimateEntrance'
import styles              from './Sidebar.module.css'

// ── Nav item data ──────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { id: 'dashboard',  label: 'Dashboard',     icon: '◈' },
  { id: 'portfolio',  label: 'Portfolio',      icon: '◉' },
  { id: 'analytics',  label: 'Analytics',      icon: '◇' },
  { id: 'market',     label: 'Market Watch',   icon: '◎' },
  { id: 'settings',   label: 'Settings',       icon: '◌' },
]

export default function Sidebar({ activeView, setActiveView }) {
  // Derive display name for local single-tenant context
  const displayName  = 'Operator'
  const displayEmail = 'local@sandbox'

  // Slide in from left on mount
  const sidebarRef = useAnimateEntrance({ xOffset: -30, duration: 0.9, delay: 0.1 })
  // Stagger nav items from top
  const navRef = useAnimateEntrance({
    yOffset:     16,
    duration:    0.6,
    delay:       0.35,
    stagger:     0.07,
    childTarget: 'li',
  })

  return (
    <aside ref={sidebarRef} className={styles.sidebar}>
      {/* ── Brand ──────────────────────────────────────────────────────── */}
      <div className={styles.brand}>
        <div className={styles.brandIcon}>
          <span>P</span>
        </div>
        <div className={styles.brandText}>
          <span className={styles.brandName}>PSX</span>
          <span className={styles.brandSub}>Portfolio Tracker</span>
        </div>
      </div>

      {/* ── Divider ────────────────────────────────────────────────────── */}
      <div className={styles.divider} />

      {/* ── Navigation ─────────────────────────────────────────────────── */}
      <nav className={styles.nav}>
        <ul ref={navRef} className={styles.navList}>
          {NAV_ITEMS.map(item => (
            <li key={item.id}>
              <button
                className={`${styles.navItem} ${activeView === item.id ? styles.active : ''}`}
                onClick={() => setActiveView(item.id)}
                aria-label={`Navigate to ${item.label}`}
                aria-current={activeView === item.id ? 'page' : undefined}
              >
                <span className={styles.navIcon}>{item.icon}</span>
                <span className={styles.navLabel}>{item.label}</span>
                {activeView === item.id && <span className={styles.activeIndicator} />}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* ── Market status badge ────────────────────────────────────────── */}
      <div className={styles.marketStatus}>
        <span className={styles.statusDot} />
        <span className={styles.statusText}>PSX Open</span>
        <span className={styles.statusTime}>09:30 – 15:30 PKT</span>
      </div>

      {/* ── User profile & Sign out ──────────────────────────────────── */}
      <div className={styles.divider} />
      <div className={styles.userProfile}>
        <div className={styles.userAvatar}>
          O
        </div>
        <div className={styles.userInfo}>
          <span className={styles.userName}>{displayName}</span>
          <span className={styles.userRole}>{displayEmail}</span>
        </div>
      </div>
    </aside>
  )
}
