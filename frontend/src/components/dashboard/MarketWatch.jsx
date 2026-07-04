/**
 * components/dashboard/MarketWatch.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Dark-glass categorized view of all PSX sectors and tickers with bulk sync.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useState, useEffect, useRef } from 'react'
import styles from './MarketWatch.module.css'

export default function MarketWatch() {
  const [sectors, setSectors] = useState({})
  const [expandedSectors, setExpandedSectors] = useState({})
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [cooldownRemaining, setCooldownRemaining] = useState(0)
  const [lastSync, setLastSync] = useState('Never')
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const timerRef = useRef(null)

  // ── Cooldown Lock Sync ─────────────────────────────────────────────────────
  useEffect(() => {
    const savedTime = localStorage.getItem('psx_last_sync_time')
    if (savedTime) {
      const elapsed = Math.floor((Date.now() - parseInt(savedTime, 10)) / 1000)
      if (elapsed < 900) {
        setCooldownRemaining(900 - elapsed)
        setLastSync(new Date(parseInt(savedTime, 10)).toLocaleTimeString())
      }
    }
    fetchMarketWatch()
  }, [])

  useEffect(() => {
    if (cooldownRemaining > 0) {
      timerRef.current = setInterval(() => {
        setCooldownRemaining(prev => {
          if (prev <= 1) {
            clearInterval(timerRef.current)
            return 0
          }
          return prev - 1
        })
      }, 1000)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [cooldownRemaining])

  const fetchMarketWatch = async () => {
    try {
      setLoading(true)
      const res = await fetch('/api/v1/market-watch')
      if (!res.ok) throw new Error('Failed to load market data')
      const data = await res.json()
      setSectors(data.sectors)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSyncMarket = async () => {
    setSyncing(true)
    setError('')
    setWarning('')
    try {
      const res = await fetch('/api/v1/prices/sync-live', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sync_all: true })
      })

      if (res.status === 429) {
        const rateData = await res.json()
        const secs = rateData.cooldown_seconds ?? 900
        setCooldownRemaining(secs)
        const simulatedStart = Date.now() - (900 - secs) * 1000
        localStorage.setItem('psx_last_sync_time', simulatedStart.toString())
        throw new Error(`Rate limit active. Please wait ${formatTime(secs)}.`)
      }

      if (!res.ok) throw new Error('Bulk sync failed.')
      const syncData = await res.json()

      const now = Date.now()
      localStorage.setItem('psx_last_sync_time', now.toString())
      setCooldownRemaining(900)
      setLastSync(new Date(now).toLocaleTimeString())

      if (syncData.tickers_failed && syncData.tickers_failed.length > 0) {
        setWarning(`Synced partially. Failed to sync some symbols due to load.`)
      }

      await fetchMarketWatch()
    } catch (err) {
      setError(err.message)
    } finally {
      setSyncing(false)
    }
  }

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0')
    const s = (secs % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  const toggleSector = (sector) => {
    setExpandedSectors(prev => ({
      ...prev,
      [sector]: !prev[sector]
    }))
  }

  const toggleAll = (expand) => {
    const next = {}
    if (expand) {
      Object.keys(sectors).forEach(sec => {
        next[sec] = true
      })
    }
    setExpandedSectors(next)
  }

  if (loading) {
    return <div className={styles.loadingScreen}>Loading PSX Market Board...</div>
  }

  return (
    <div className={styles.container}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Market Board</h1>
          <p className={styles.subtitle}>Grouped by sectors • Latest PSX quotes</p>
        </div>

        <div className={styles.controls}>
          <button 
            className={styles.toggleBtn}
            onClick={() => toggleAll(true)}
          >
            Expand All
          </button>
          <button 
            className={styles.toggleBtn}
            onClick={() => toggleAll(false)}
          >
            Collapse All
          </button>
          <button
            className={`${styles.syncBtn} ${cooldownRemaining > 0 ? styles.locked : ''}`}
            onClick={handleSyncMarket}
            disabled={syncing || cooldownRemaining > 0}
          >
            {syncing ? 'Syncing...' : cooldownRemaining > 0 ? `Locked - ${formatTime(cooldownRemaining)}` : 'Sync Market'}
          </button>
        </div>
      </header>

      {error && <div className={styles.errorAlert}>✕ {error}</div>}
      {warning && <div className={styles.warningAlert}>⚠️ {warning}</div>}

      <div className={styles.lastSyncInfo}>
        Last updated: <span>{lastSync}</span>
      </div>

      {/* ── Accordion List ──────────────────────────────────────────────── */}
      <div className={styles.accordionContainer}>
        {Object.keys(sectors).length === 0 ? (
          <div className={styles.emptyState}>No market sectors found. Run seeder.</div>
        ) : (
          Object.entries(sectors).map(([sectorName, tickers]) => {
            const isExpanded = !!expandedSectors[sectorName]
            return (
              <div key={sectorName} className={styles.accordionItem}>
                <button
                  className={styles.accordionTrigger}
                  onClick={() => toggleSector(sectorName)}
                  aria-expanded={isExpanded}
                >
                  <span className={styles.accordionArrow}>{isExpanded ? '▼' : '▶'}</span>
                  <span className={styles.sectorTitle}>{sectorName}</span>
                  <span className={styles.tickerCount}>{tickers.length} Symbols</span>
                </button>

                {isExpanded && (
                  <div className={styles.accordionContent}>
                    <table className={styles.table}>
                      <thead>
                        <tr>
                          <th>Symbol</th>
                          <th>Company</th>
                          <th className={styles.numCol}>Price (PKR)</th>
                          <th className={styles.numCol}>Volume</th>
                          <th className={styles.dateCol}>Sync Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tickers.map(t => (
                          <tr key={t.ticker} className={styles.row}>
                            <td className={styles.tickerBadge}>{t.ticker}</td>
                            <td className={styles.companyName}>{t.company_name}</td>
                            <td className={styles.numCol}>{t.price ? t.price.toFixed(2) : '—'}</td>
                            <td className={styles.numCol}>{t.volume ? t.volume.toLocaleString() : '—'}</td>
                            <td className={styles.dateCol}>{t.date ? t.date : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
