/**
 * App.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Root application shell.
 *
 * Layer stack (bottom → top) — dashboard view:
 *   [0] AmbientCanvas   — fixed WebGL background, z-index: 0
 *   [1] Sidebar         — fixed left navigation panel, z-index: 20
 *   [2] MainContent     — scrollable right panel, z-index: 10
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { Suspense, useState } from 'react'
import AmbientCanvas from './components/three/AmbientCanvas'
import Sidebar       from './components/layout/Sidebar'
import MainContent   from './components/layout/MainContent'

export default function App() {
  const [activeView, setActiveView] = useState('dashboard')

  return (
    <>
      {/* ── Layer 0: Ambient 3D background ─────────────────────────────── */}
      <Suspense fallback={null}>
        <AmbientCanvas />
      </Suspense>

      {/* ── Layer 1: Fixed sidebar navigation ──────────────────────────── */}
      <Sidebar activeView={activeView} setActiveView={setActiveView} />

      {/* ── Layer 2: Main scrollable dashboard content ──────────────────── */}
      <MainContent activeView={activeView} />
    </>
  )
}
