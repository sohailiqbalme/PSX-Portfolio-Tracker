/**
 * components/dashboard/TypeaheadSearch.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Beautiful glassmorphic autocomplete search dropdown with debouncing.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useState, useEffect, useRef } from 'react'
import styles from './TypeaheadSearch.module.css'

export default function TypeaheadSearch({ value, onChange, placeholder = 'Search Ticker or Company...' }) {
  const [query, setQuery] = useState(value)
  const [suggestions, setSuggestions] = useState([])
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const dropdownRef = useRef(null)

  // Sync state if parent value resets
  useEffect(() => {
    setQuery(value)
  }, [value])

  // Handle clicking outside to close suggestions
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [])

  // Debounced API query
  useEffect(() => {
    if (!query || query.trim().length < 2) {
      setSuggestions([])
      return
    }

    const delayDebounce = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await fetch(`/api/v1/tickers/search?q=${encodeURIComponent(query)}`)
        if (res.ok) {
          const data = await res.json()
          setSuggestions(data)
        }
      } catch (err) {
        console.error('Typeahead query failed:', err)
      } finally {
        setLoading(false)
      }
    }, 250) // 250ms debounce

    return () => clearTimeout(delayDebounce)
  }, [query])

  const handleSelect = (ticker) => {
    setQuery(ticker)
    onChange(ticker)
    setIsOpen(false)
  }

  return (
    <div className={styles.typeaheadContainer} ref={dropdownRef}>
      <input
        type="text"
        className={styles.typeaheadInput}
        placeholder={placeholder}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          onChange(e.target.value) // Notify parent on manual type
          setIsOpen(true)
        }}
        onFocus={() => setIsOpen(true)}
      />
      {isOpen && (query.trim().length >= 2) && (
        <ul className={styles.suggestionsList}>
          {loading && <li className={styles.statusMessage}>Searching...</li>}
          {!loading && suggestions.length === 0 && (
            <li className={styles.statusMessage}>No matches found</li>
          )}
          {!loading && suggestions.map((item) => (
            <li
              key={item.ticker}
              className={styles.suggestionItem}
              onClick={() => handleSelect(item.ticker)}
            >
              <span className={styles.tickerBadge}>{item.ticker}</span>
              <div className={styles.details}>
                <span className={styles.companyName}>{item.company_name}</span>
                <span className={styles.sector}>{item.sector}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
