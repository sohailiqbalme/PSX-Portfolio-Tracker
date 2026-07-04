/**
 * components/layout/MainContent.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Scrollable main content area with dynamic API fetching and rate-limited sync.
 * Handles:
 *   - 15-minute sync cooldown lock with active countdown UI (MM:SS).
 *   - Cooldown persistence across page refreshes via localStorage.
 *   - Database-driven portfolio metric calculation and sync.
 *   - Partial-failure reporting for network/scraping timeouts.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useEffect, useState, useRef } from 'react'
import DashboardGrid                  from '../dashboard/DashboardGrid'
import SectionHeader                  from '../dashboard/SectionHeader'
import TickerRow                      from '../dashboard/TickerRow'
import useAnimateEntrance             from '../../hooks/useAnimateEntrance'
import useGSAPScrollTrigger           from '../../hooks/useGSAPScrollTrigger'
import styles                         from './MainContent.module.css'
import MarketWatch                    from '../dashboard/MarketWatch'
import AddTransactionModal            from '../dashboard/AddTransactionModal'

const WATCHLIST_TICKERS = [
  { ticker: 'ENGRO', name: 'Engro Corporation' },
  { ticker: 'HUBC',  name: 'Hub Power Company' },
  { ticker: 'OGDC',  name: 'Oil & Gas Dev. Corp.' },
  { ticker: 'PPL',   name: 'Pakistan Petroleum Ltd.' },
  { ticker: 'UBL',   name: 'United Bank Limited' },
  { ticker: 'LUCK',  name: 'Lucky Cement' },
]

export default function MainContent({ activeView }) {
  const timerRef = useRef(null)
  
  // ── State ──────────────────────────────────────────────────────────────────
  const [portfolio,         setPortfolio]         = useState(null)
  const [cashBalance,       setCashBalance]       = useState(0)
  const [holdings,          setHoldings]          = useState({})
  const [prices,            setPrices]            = useState({})
  const [transactions,      setTransactions]      = useState([])
  
  const [loading,           setLoading]           = useState(true)
  const [syncing,           setSyncing]           = useState(false)
  const [cooldownRemaining, setCooldownRemaining] = useState(0) // seconds
  const [lastSync,          setLastSync]          = useState('Never')
  const [error,             setError]             = useState('')
  const [warning,           setWarning]           = useState('')
  const [isModalOpen,       setIsModalOpen]       = useState(false)

  // ── Animations ─────────────────────────────────────────────────────────────
  const heroRef = useAnimateEntrance({ yOffset: 32, duration: 1.0, delay: 0.4 })
  const holdingsRef = useGSAPScrollTrigger({
    start:         'top 85%',
    yOffset:       30,
    duration:      0.7,
    staggerTarget: '[data-row]',
    staggerAmount: 0.06,
  })
  const analyticsRef = useGSAPScrollTrigger({
    start:    'top 80%',
    yOffset:  40,
    scale:    0.97,
    duration: 0.9,
    ease:     'power2.out',
  })

  // ── Cooldown Timer Logic ───────────────────────────────────────────────────
  useEffect(() => {
    // Rehydrate cooldown from localStorage on mount
    const key = `psx_last_sync_time`
    const savedTime = localStorage.getItem(key)
    if (savedTime) {
      const elapsed = Math.floor((Date.now() - parseInt(savedTime, 10)) / 1000)
      if (elapsed < 900) {
        setCooldownRemaining(900 - elapsed)
        const dateObj = new Date(parseInt(savedTime, 10))
        setLastSync(dateObj.toLocaleTimeString())
      }
    }
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

  // ── API Fetchers ───────────────────────────────────────────────────────────
  const fetchPortfolioData = async () => {
    try {
      // 1. Fetch user portfolios (auto-seeds Default Portfolio if empty)
      const portfoliosRes = await fetch('/api/v1/portfolios')
      if (!portfoliosRes.ok) throw new Error('Failed to fetch portfolios')
      const portfoliosData = await portfoliosRes.json()
      
      let targetPortfolio = portfoliosData.portfolios?.[0]
      if (!targetPortfolio) throw new Error('No portfolios found')
      
      // 2. Fetch portfolio details
      const detailRes = await fetch(`/api/v1/portfolios/${targetPortfolio.id}`)
      if (!detailRes.ok) throw new Error('Failed to fetch portfolio details')
      const detailData = await detailRes.json()
      
      setPortfolio(detailData.portfolio)
      setCashBalance(detailData.cash_balance)
      setHoldings(detailData.holdings)
      setTransactions(detailData.transactions)
      
      // 4. Resolve prices for holdings & watchlist
      const holdingsTickers = Object.keys(detailData.holdings)
      const watchlistTickers = WATCHLIST_TICKERS.map(t => t.ticker)
      const uniqueTickers = Array.from(new Set([...holdingsTickers, ...watchlistTickers]))
      
      const priceMap = {}
      await Promise.all(
        uniqueTickers.map(async (ticker) => {
          try {
            const pRes = await fetch(`/api/v1/prices/${ticker}`)
            if (pRes.ok) {
              const pData = await pRes.json()
              priceMap[ticker] = parseFloat(pData.close_price)
            }
          } catch (err) {
            console.error(`Failed to load price for ${ticker}:`, err)
          }
        })
      )
      setPrices(priceMap)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPortfolioData()
  }, [])

  // ── Sync Live Market handler ───────────────────────────────────────────────
  const handleLiveSync = async () => {
    setSyncing(true)
    setError('')
    setWarning('')
    
    try {
      const syncRes = await fetch('/api/v1/prices/sync-live', {
        method: 'POST',
        headers: {
          'Content-Type':  'application/json'
        },
      })

      // Handle 429 rate limit
      if (syncRes.status === 429) {
        const rateData = await syncRes.json()
        const secs = rateData.cooldown_seconds ?? 900
        setCooldownRemaining(secs)
        
        // Sync timestamp to localStorage
        const simulatedStart = Date.now() - (900 - secs) * 1000
        localStorage.setItem(`psx_last_sync_time`, simulatedStart.toString())
        throw new Error(`Rate limit active. Please wait ${formatTime(secs)}.`)
      }

      if (!syncRes.ok) throw new Error('Sync failed due to server error.')
      
      const syncData = await syncRes.json()
      
      // Save sync timestamp
      const now = Date.now()
      localStorage.setItem(`psx_last_sync_time`, now.toString())
      setCooldownRemaining(900)
      setLastSync(new Date(now).toLocaleTimeString())

      // Report partial failures if some tickers timed out or failed to sync
      if (syncData.tickers_failed && syncData.tickers_failed.length > 0) {
        setWarning(
          `Sync completed partially. Loaded: ${syncData.tickers_succeeded.join(', ')}. ` +
          `Failed: ${syncData.tickers_failed.join(', ')} (Heavy PSX load / Timeouts).`
        )
      }

      // Reload database-driven states
      await fetchPortfolioData()
    } catch (err) {
      setError(err.message)
    } finally {
      setSyncing(false)
    }
  }

  // Helper to format countdown timer (MM:SS)
  const formatTime = (secs) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0')
    const s = (secs % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  
  // Combine watchlist metadata with latest prices for table rendering
  const tableRows = WATCHLIST_TICKERS.map(item => {
    const currentPrice = prices[item.ticker] ?? 0
    const owned = holdings[item.ticker]?.shares ?? 0
    return {
      ticker:        item.ticker,
      name:          owned > 0 ? `${item.name} (Held: ${owned.toFixed(0)})` : item.name,
      price:         currentPrice,
      change:        owned > 0 ? (currentPrice - (holdings[item.ticker]?.avg_cost ?? 0)) : 0,
      changePercent: owned > 0 && holdings[item.ticker]?.avg_cost > 0
        ? ((currentPrice - holdings[item.ticker].avg_cost) / holdings[item.ticker].avg_cost) * 100
        : 0,
      volume:        'Synced',
    }
  })

  if (loading) {
    return (
      <main className={styles.main}>
        <div className={styles.loadingContainer}>
          <div className="shimmer" style={{ width: '200px', height: '24px', borderRadius: '4px', marginBottom: '1rem' }} />
          <div className="shimmer" style={{ width: '400px', height: '48px', borderRadius: '8px' }} />
        </div>
      </main>
    )
  }

  // Dynamic view routing
  if (activeView === 'market') {
    return (
      <main className={styles.main}>
        <MarketWatch />
      </main>
    )
  }

  if (activeView === 'settings') {
    return (
      <main className={styles.main}>
        <div className={styles.settingsContainer}>
          <h1 className={styles.heroTitle}>Settings</h1>
          <p className={styles.subtitle}>Single-tenant local environment configurations</p>
          <div className={styles.analyticsPlaceholder} style={{ marginTop: '24px' }}>
            <p className={styles.placeholderText}>
              System is running in SQLite / PostgreSQL developer mode. No further configurations needed.
            </p>
          </div>
        </div>
      </main>
    )
  }

  if (activeView === 'portfolio') {
    return (
      <main className={styles.main}>
        <header className={styles.heroHeader} style={{ marginBottom: '24px' }}>
          <div>
            <p className={styles.heroLabel}>Operations Ledger</p>
            <h1 className={styles.heroTitle}>Transaction History</h1>
          </div>
          <button 
            className={styles.addBtn}
            onClick={() => setIsModalOpen(true)}
          >
            + Add Entry
          </button>
        </header>

        {/* Transaction History List */}
        <div className={styles.tickerTable}>
          <div className={styles.tickerHead} style={{ gridTemplateColumns: '1fr 1.2fr 1fr 1fr 1fr' }}>
            <span>Date</span>
            <span>Ticker / Operation</span>
            <span>Action</span>
            <span>Quantity</span>
            <span className={styles.numCol}>Price (PKR)</span>
          </div>
          {transactions.length === 0 ? (
            <div className={styles.emptyState} style={{ padding: '40px', color: 'rgba(255,255,255,0.3)', fontStyle: 'italic', textAlign: 'center' }}>
              No transactions recorded yet.
            </div>
          ) : (
            transactions.map(txn => (
              <div key={txn.id} className={styles.transactionRow} style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 1fr 1fr 1fr', padding: '14px 12px', borderBottom: '1px solid rgba(255,255,255,0.03)', fontSize: '0.9rem' }}>
                <span style={{ color: 'rgba(255,255,255,0.4)' }}>{new Date(txn.transacted_at).toLocaleDateString()}</span>
                <span style={{ fontWeight: 600, color: '#f1f5f9' }}>{txn.ticker || 'CASH ACTION'}</span>
                <span style={{ 
                  color: txn.action === 'BUY' || txn.action === 'WITHDRAWAL' ? '#fca5a5' : '#00f2fe',
                  fontWeight: 700 
                }}>{txn.action}</span>
                <span>{txn.quantity}</span>
                <span className={styles.numCol} style={{ fontWeight: 600, color: '#f1f5f9' }}>{float(txn.price).toLocaleString()}</span>
              </div>
            ))
          )}
        </div>

        {isModalOpen && portfolio && (
          <AddTransactionModal
            portfolioId={portfolio.id}
            onClose={() => setIsModalOpen(false)}
            onTransactionAdded={fetchPortfolioData}
          />
        )}
      </main>
    )
  }

  // Helper float parser
  function float(val) {
    const parsed = parseFloat(val)
    return isNaN(parsed) ? 0 : parsed
  }

  // Default: Dashboard View
  return (
    <main className={styles.main}>
      {/* Error Banner */}
      {error && (
        <div className={styles.errorBanner} role="alert">
          <span>⚠️ {error}</span>
          <button onClick={() => setError('')} className={styles.closeError}>&times;</button>
        </div>
      )}

      {/* Warning Banner */}
      {warning && (
        <div className={styles.warningBanner} role="alert">
          <span>⚡ {warning}</span>
          <button onClick={() => setWarning('')} className={styles.closeError}>&times;</button>
        </div>
      )}

      {/* ── 1. Hero: Portfolio Overview ─────────────────────────────────── */}
      <section ref={heroRef} className={styles.heroSection}>
        <header className={styles.heroHeader}>
          <div>
            <p className={styles.heroLabel}>Portfolio Overview</p>
            <h1 className={styles.heroTitle}>
              My <span className="gradient-text">Dashboard</span>
            </h1>
          </div>
          <div className={styles.heroMeta}>
            <button
              onClick={() => setIsModalOpen(true)}
              className={styles.addBtn}
              style={{ marginRight: '12px' }}
            >
              + Add Entry
            </button>
            <button
              onClick={handleLiveSync}
              className={`${styles.syncBtn} ${syncing ? styles.syncBtnActive : ''}`}
              disabled={syncing || cooldownRemaining > 0}
            >
              {syncing
                ? 'Syncing Live...'
                : cooldownRemaining > 0
                  ? `Locked - ${formatTime(cooldownRemaining)}`
                  : 'Sync Live Market'
              }
            </button>
            <span className={styles.lastUpdated}>Last Sync: {lastSync}</span>
          </div>
        </header>

        {/* Key metric cards */}
        <DashboardGrid
          portfolio={portfolio}
          cashBalance={cashBalance}
          holdings={holdings}
          prices={prices}
        />
      </section>

      {/* ── 2. Market Watch: Live Tickers ───────────────────────────────── */}
      <section className={styles.section}>
        <SectionHeader
          label="Watchlist"
          title="Tracked Tickers"
          subtitle="Real-time pricing synced directly into the database on click"
        />
        <div ref={holdingsRef} className={styles.tickerTable}>
          {/* Table head */}
          <div className={styles.tickerHead}>
            <span>Ticker</span>
            <span>Price (PKR)</span>
            <span>Unrealised P&L</span>
            <span>P&L %</span>
            <span>Volume</span>
          </div>
          {/* Rows */}
          {tableRows.map(t => (
            <TickerRow key={t.ticker} {...t} />
          ))}
        </div>
      </section>

      {/* ── 3. Analytics ────────────────────────────────────────────────── */}
      <section ref={analyticsRef} className={styles.section}>
        <SectionHeader
          label="Analytics"
          title="Portfolio Performance"
          subtitle="Sector allocation, drawdown analysis, and return benchmarking"
        />
        <div className={styles.analyticsPlaceholder}>
          <div className={styles.placeholderInner}>
            <span className={styles.placeholderIcon}>◇</span>
            <p className={styles.placeholderText}>
              Advanced charts — drawdown curves, sector rings, and benchmark overlays — coming in Phase 3.
            </p>
            <p className={styles.placeholderSub}>
              Live sync commits data directly to Supabase daily_prices.
            </p>
          </div>
        </div>
      </section>

      {/* ── Footer padding ──────────────────────────────────────────────── */}
      <div className={styles.footerPad} />

      {isModalOpen && portfolio && (
        <AddTransactionModal
          portfolioId={portfolio.id}
          onClose={() => setIsModalOpen(false)}
          onTransactionAdded={fetchPortfolioData}
        />
      )}
    </main>
  )
}
