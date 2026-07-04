/**
 * hooks/useGSAPScrollTrigger.js
 * ─────────────────────────────────────────────────────────────────────────────
 * Core GSAP ScrollTrigger hook.
 *
 * Usage:
 *   const ref = useGSAPScrollTrigger({ yOffset: 40, duration: 0.8 })
 *   return <section ref={ref}>...</section>
 *
 * Options:
 *   start          — ScrollTrigger start (default: "top 82%")
 *   end            — ScrollTrigger end   (default: "bottom 20%")
 *   yOffset        — Initial Y translate  (default: 40px)
 *   xOffset        — Initial X translate  (default: 0px)
 *   scale          — Initial scale        (default: 0.96)
 *   duration       — Animation duration   (default: 0.85s)
 *   ease           — GSAP ease string     (default: "power3.out")
 *   delay          — Animation delay      (default: 0)
 *   staggerTarget  — If set, staggers children matching this selector
 *   staggerAmount  — Stagger delay between children (default: 0.08s)
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useRef, useEffect } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

// Register once at module level
gsap.registerPlugin(ScrollTrigger)

export default function useGSAPScrollTrigger(options = {}) {
  const ref = useRef(null)

  const {
    start          = 'top 82%',
    end            = 'bottom 20%',
    yOffset        = 40,
    xOffset        = 0,
    scale          = 0.96,
    duration       = 0.85,
    ease           = 'power3.out',
    delay          = 0,
    staggerTarget  = null,
    staggerAmount  = 0.08,
    toggleActions  = 'play none none reverse',
  } = options

  useEffect(() => {
    const el = ref.current
    if (!el) return

    // Determine what to animate — the whole element or its staggered children
    const targets = staggerTarget
      ? el.querySelectorAll(staggerTarget)
      : el

    const fromVars = {
      opacity:    0,
      y:          yOffset,
      x:          xOffset,
      scale:      scale,
      willChange: 'opacity, transform',
    }

    const toVars = {
      opacity:    1,
      y:          0,
      x:          0,
      scale:      1,
      duration,
      ease,
      delay,
      clearProps:  'willChange',
      ...(staggerTarget ? { stagger: staggerAmount } : {}),
    }

    const animation = gsap.fromTo(targets, fromVars, {
      ...toVars,
      scrollTrigger: {
        trigger:      el,
        start,
        end,
        toggleActions,
        // Uncomment for debugging:
        // markers: true,
      },
    })

    return () => {
      // Clean up this specific animation + its ScrollTrigger on unmount
      animation.scrollTrigger?.kill()
      animation.kill()
    }
  }, []) // intentionally empty — options are read once on mount

  return ref
}
