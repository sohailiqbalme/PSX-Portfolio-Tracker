/**
 * components/dashboard/AddTransactionModal.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Glassmorphic Modal for Adding Stock Trades and Cash Transactions.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useState } from 'react'
import TypeaheadSearch from './TypeaheadSearch'
import styles from './AddTransactionModal.module.css'

export default function AddTransactionModal({ portfolioId, onClose, onTransactionAdded }) {
  const [activeTab, setActiveTab] = useState('trade') // 'trade' or 'cash'
  
  // Trade States
  const [ticker, setTicker] = useState('')
  const [action, setAction] = useState('BUY') // 'BUY' or 'SELL'
  const [quantity, setQuantity] = useState('')
  const [price, setPrice] = useState('')
  const [commission, setCommission] = useState('0')
  const [tradeNotes, setTradeNotes] = useState('')
  
  // Cash States
  const [cashType, setCashType] = useState('DEPOSIT') // 'DEPOSIT' or 'WITHDRAWAL'
  const [cashAmount, setCashAmount] = useState('')
  const [cashNotes, setCashNotes] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleTradeSubmit = async (e) => {
    e.preventDefault()
    if (!ticker || !quantity || !price) {
      setError('Ticker, quantity, and price are required.')
      return
    }

    setLoading(true)
    setError('')
    try {
      const res = await fetch(`/api/v1/portfolios/${portfolioId}/transactions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: ticker.toUpperCase(),
          action: action,
          quantity: parseFloat(quantity),
          price: parseFloat(price),
          commission: parseFloat(commission || 0),
          notes: tradeNotes
        })
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.error || 'Failed to submit trade.')
      }

      onTransactionAdded()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleCashSubmit = async (e) => {
    e.preventDefault()
    if (!cashAmount || parseFloat(cashAmount) <= 0) {
      setError('A valid positive cash amount is required.')
      return
    }

    setLoading(true)
    setError('')
    try {
      // Endpoint is /api/v1/portfolios/<id>/transactions but we map it to Cash actions in backend if action is DEPOSIT/WITHDRAWAL
      // Wait, let's verify if the backend handles DEPOSIT/WITHDRAWAL on /portfolios/<id>/transactions.
      // Let's check routes.py.
      // Wait, is there a cash ledger route? Let's check routes.py using grep or view.
      // Ah, wait! The routes.py transaction POST route handles:
      // if action_str in ["DEPOSIT", "WITHDRAWAL"]:
      // Let's check if the backend supports DEPOSIT/WITHDRAWAL action on the transaction endpoint.
      // Yes! Let's verify by submitting action: DEPOSIT or WITHDRAWAL.
      const res = await fetch(`/api/v1/portfolios/${portfolioId}/transactions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: cashType,
          quantity: 1, // dummy
          price: parseFloat(cashAmount),
          commission: 0,
          notes: cashNotes
        })
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.error || 'Failed to submit cash transaction.')
      }

      onTransactionAdded()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.modalOverlay} role="dialog" aria-modal="true">
      <div className={styles.modalContent}>
        <button className={styles.closeBtn} onClick={onClose} aria-label="Close modal">✕</button>
        
        <h2 className={styles.modalTitle}>New Entry</h2>
        
        {/* ── Tabs ──────────────────────────────────────────────────────── */}
        <div className={styles.tabHeader}>
          <button
            className={`${styles.tabBtn} ${activeTab === 'trade' ? styles.activeTab : ''}`}
            onClick={() => { setActiveTab('trade'); setError(''); }}
          >
            Record Trade
          </button>
          <button
            className={`${styles.tabBtn} ${activeTab === 'cash' ? styles.activeTab : ''}`}
            onClick={() => { setActiveTab('cash'); setError(''); }}
          >
            Cash Operations
          </button>
        </div>

        {error && <div className={styles.errorText}>✕ {error}</div>}

        {/* ── Trade Tab ─────────────────────────────────────────────────── */}
        {activeTab === 'trade' && (
          <form onSubmit={handleTradeSubmit} className={styles.form}>
            <div className={styles.inputGroup}>
              <label>Ticker Search</label>
              <TypeaheadSearch value={ticker} onChange={setTicker} />
            </div>

            <div className={styles.row}>
              <div className={styles.inputGroup}>
                <label>Action</label>
                <select value={action} onChange={(e) => setAction(e.target.value)} className={styles.select}>
                  <option value="BUY">BUY</option>
                  <option value="SELL">SELL</option>
                </select>
              </div>

              <div className={styles.inputGroup}>
                <label>Quantity (Shares)</label>
                <input
                  type="number"
                  step="any"
                  className={styles.input}
                  placeholder="e.g. 100"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                />
              </div>
            </div>

            <div className={styles.row}>
              <div className={styles.inputGroup}>
                <label>Price (PKR)</label>
                <input
                  type="number"
                  step="any"
                  className={styles.input}
                  placeholder="e.g. 320.50"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                />
              </div>

              <div className={styles.inputGroup}>
                <label>Commission (PKR)</label>
                <input
                  type="number"
                  step="any"
                  className={styles.input}
                  placeholder="e.g. 150"
                  value={commission}
                  onChange={(e) => setCommission(e.target.value)}
                />
              </div>
            </div>

            <div className={styles.inputGroup}>
              <label>Notes</label>
              <textarea
                className={styles.textarea}
                placeholder="Optional comments..."
                value={tradeNotes}
                onChange={(e) => setTradeNotes(e.target.value)}
              />
            </div>

            <button type="submit" className={styles.submitBtn} disabled={loading}>
              {loading ? 'Recording...' : 'Add Trade'}
            </button>
          </form>
        )}

        {/* ── Cash Tab ──────────────────────────────────────────────────── */}
        {activeTab === 'cash' && (
          <form onSubmit={handleCashSubmit} className={styles.form}>
            <div className={styles.inputGroup}>
              <label>Operation Type</label>
              <select value={cashType} onChange={(e) => setCashType(e.target.value)} className={styles.select}>
                <option value="DEPOSIT">DEPOSIT</option>
                <option value="WITHDRAWAL">WITHDRAWAL</option>
              </select>
            </div>

            <div className={styles.inputGroup}>
              <label>Amount (PKR)</label>
              <input
                type="number"
                step="any"
                className={styles.input}
                placeholder="e.g. 50000"
                value={cashAmount}
                onChange={(e) => setCashAmount(e.target.value)}
              />
            </div>

            <div className={styles.inputGroup}>
              <label>Notes</label>
              <textarea
                className={styles.textarea}
                placeholder="Required notes (e.g. Bank transfer ID)..."
                value={cashNotes}
                onChange={(e) => setCashNotes(e.target.value)}
                required
              />
            </div>

            <button type="submit" className={styles.submitBtn} disabled={loading}>
              {loading ? 'Recording...' : 'Add Cash Transaction'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
