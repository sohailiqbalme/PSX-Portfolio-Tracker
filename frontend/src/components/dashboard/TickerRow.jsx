/**
 * components/dashboard/TickerRow.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * A single row in the Market Watch table.
 *
 * Props:
 *   ticker        {string}  — e.g. "ENGRO"
 *   name          {string}  — full company name
 *   price         {number}  — current price in PKR
 *   change        {number}  — absolute change
 *   changePercent {number}  — percentage change
 *   volume        {string}  — formatted volume string e.g. "2.1M"
 * ─────────────────────────────────────────────────────────────────────────────
 */

import styles from './TickerRow.module.css'

function fmt(n, decimals = 2) {
  return n.toLocaleString('en-PK', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

export default function TickerRow({ ticker, name, price, change, changePercent, volume }) {
  const isPositive = change >= 0
  const trendClass = isPositive ? styles.positive : styles.negative
  const arrow      = isPositive ? '▲' : '▼'

  return (
    <div className={styles.row} data-row="true" role="row" aria-label={`${ticker} price ${fmt(price)}`}>
      {/* Ticker + name */}
      <div className={styles.tickerCell}>
        <span className={styles.tickerSymbol}>{ticker}</span>
        <span className={styles.tickerName}>{name}</span>
      </div>

      {/* Price */}
      <span className={`${styles.price} mono`}>
        {fmt(price)}
      </span>

      {/* Change */}
      <span className={`${styles.changeVal} ${trendClass} mono`}>
        {isPositive ? '+' : ''}{fmt(change)}
      </span>

      {/* Change % */}
      <div className={`${styles.changePct} ${trendClass}`}>
        <span className={styles.arrow}>{arrow}</span>
        <span className="mono">{Math.abs(changePercent).toFixed(2)}%</span>
      </div>

      {/* Volume */}
      <span className={`${styles.volume} mono`}>{volume}</span>
    </div>
  )
}
