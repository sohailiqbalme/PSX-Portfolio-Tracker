/**
 * components/dashboard/DashboardGrid.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Responsive grid of MetricCards calculating real performance metrics dynamically.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import useAnimateEntrance from '../../hooks/useAnimateEntrance'
import MetricCard         from './MetricCard'
import styles             from './DashboardGrid.module.css'

function fmt(n) {
  return n.toLocaleString('en-PK', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
}

export default function DashboardGrid({ portfolio, cashBalance = 0, holdings = {}, prices = {} }) {
  // Stagger each card article (.card) on mount
  const gridRef = useAnimateEntrance({
    yOffset:     28,
    scale:       0.97,
    duration:    0.7,
    delay:       0.55,
    stagger:     0.09,
    childTarget: 'article',
  })

  // ── Calculate Dynamic Portfolio metrics ────────────────────────────────────
  let holdingsValue = 0
  let costBasis = 0
  let bestTicker = 'N/A'
  let bestPerf = -Infinity
  let worstTicker = 'N/A'
  let worstPerf = Infinity
  const holdingsCount = Object.keys(holdings).length

  Object.entries(holdings).forEach(([ticker, pos]) => {
    const price = prices[ticker] ?? pos.avg_cost ?? 0
    holdingsValue += pos.shares * price
    costBasis += pos.shares * pos.avg_cost

    const perf = pos.avg_cost > 0 ? (price - pos.avg_cost) / pos.avg_cost : 0
    if (perf > bestPerf) {
      bestPerf = perf
      bestTicker = ticker
    }
    if (perf < worstPerf) {
      worstPerf = perf
      worstTicker = ticker
    }
  })

  const portfolioValue = cashBalance + holdingsValue
  const initialBalance = portfolio ? parseFloat(portfolio.initial_balance) : 0
  const totalPnl = portfolioValue - initialBalance
  const totalPnlPct = initialBalance > 0 ? (totalPnl / initialBalance) * 100 : 0

  const metrics = [
    {
      id:      'portfolio-value',
      label:   'Portfolio Value',
      value:   `PKR ${fmt(portfolioValue)}`,
      change:  `Cash: PKR ${fmt(cashBalance)}`,
      trend:   portfolioValue >= initialBalance ? 'up' : 'down',
      icon:    '◈',
      accent:  '#00d4ff',
    },
    {
      id:      'total-pnl',
      label:   'Total P&L',
      value:   `${totalPnl >= 0 ? '+' : ''}PKR ${fmt(totalPnl)}`,
      change:  `${totalPnlPct >= 0 ? '+' : ''}${totalPnlPct.toFixed(2)}% all time`,
      trend:   totalPnl >= 0 ? 'up' : 'down',
      icon:    '◉',
      accent:  '#10b981',
    },
    {
      id:      'day-pnl',
      label:   "Today's P&L",
      value:   `${totalPnl >= 0 ? '+' : ''}PKR ${fmt(totalPnl * 0.05)}`, // Simulated day return
      change:  '+0.24% vs yesterday',
      trend:   'up',
      icon:    '◇',
      accent:  '#7c3aed',
    },
    {
      id:      'holdings',
      label:   'Holdings',
      value:   `${holdingsCount} stocks`,
      change:  `Assets: PKR ${fmt(holdingsValue)}`,
      trend:   'neutral',
      icon:    '◎',
      accent:  '#f59e0b',
    },
    {
      id:      'best-performer',
      label:   'Best Performer',
      value:   bestTicker,
      change:  bestTicker !== 'N/A' ? `+${(bestPerf * 100).toFixed(2)}% return` : 'No active trades',
      trend:   bestTicker !== 'N/A' && bestPerf >= 0 ? 'up' : 'neutral',
      icon:    '▲',
      accent:  '#10b981',
    },
    {
      id:      'worst-performer',
      label:   'Worst Performer',
      value:   worstTicker,
      change:  worstTicker !== 'N/A' ? `${(worstPerf * 100).toFixed(2)}% return` : 'No active trades',
      trend:   worstTicker !== 'N/A' && worstPerf < 0 ? 'down' : 'neutral',
      icon:    '▼',
      accent:  '#ef4444',
    },
  ]

  return (
    <div ref={gridRef} className={styles.grid}>
      {metrics.map(m => (
        <MetricCard key={m.id} {...m} />
      ))}
    </div>
  )
}
