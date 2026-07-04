/**
 * hooks/useAnimateEntrance.js
 * ─────────────────────────────────────────────────────────────────────────────
 * Lightweight per-element entrance animation helper using GSAP.
 *
 * Unlike useGSAPScrollTrigger (which is scroll-driven), this hook fires
 * an entrance animation immediately on mount — useful for the sidebar,
 * hero section, and any above-the-fold elements.
 *
 * Usage:
 *   const ref = useAnimateEntrance({ delay: 0.3, yOffset: 20 })
 *   return <div ref={ref}>...</div>
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useRef, useEffect } from 'react'
import gsap from 'gsap'

export default function useAnimateEntrance(options = {}) {
  const ref = useRef(null)

  const {
    yOffset     = 24,
    xOffset     = 0,
    scale       = 1,
    duration    = 0.7,
    ease        = 'power3.out',
    delay       = 0,
    stagger     = 0,
    childTarget = null,
  } = options

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const targets = childTarget ? el.querySelectorAll(childTarget) : el

    const animation = gsap.fromTo(
      targets,
      { opacity: 0, y: yOffset, x: xOffset, scale, willChange: 'opacity, transform' },
      {
        opacity:    1,
        y:          0,
        x:          0,
        scale:      1,
        duration,
        ease,
        delay,
        clearProps: 'willChange',
        ...(stagger > 0 ? { stagger } : {}),
      }
    )

    return () => animation.kill()
  }, [])

  return ref
}
