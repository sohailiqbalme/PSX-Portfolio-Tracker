/**
 * components/three/AmbientCanvas.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * The cinematic 3D background layer.
 *
 * Renders a full-screen, fixed React Three Fiber <Canvas> behind all UI.
 * Contains:
 *   - ParticleField    — 2,500 drifting points forming a depth field
 *   - FloatingGeometry — 3 slow-rotating geometric meshes with neon materials
 *   - Atmospheric lighting (3 coloured point lights + ambient)
 *   - Subtle bloom post-processing via @react-three/postprocessing
 *
 * Performance:
 *   - frameloop="demand" prevents needless renders when scene is static.
 *   - Geometry is instanced / shared where possible.
 *   - dpr capped at [1, 1.5] for balanced quality vs GPU cost.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { Suspense } from 'react'
import { Canvas }   from '@react-three/fiber'
import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing'
import ParticleField    from './ParticleField'
import FloatingGeometry from './FloatingGeometry'

/** Inline style: fixed, full-screen, behind all UI */
const canvasStyle = {
  position:   'fixed',
  inset:      0,
  width:      '100vw',
  height:     '100vh',
  zIndex:     'var(--z-canvas)',
  pointerEvents: 'none', // Let clicks pass through to UI
}

export default function AmbientCanvas() {
  return (
    <div style={canvasStyle} aria-hidden="true">
      <Canvas
        frameloop="always"
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 20], fov: 60, near: 0.1, far: 200 }}
        gl={{
          antialias:         true,
          alpha:             true, // Transparent canvas — body bg-color shows
          powerPreference:   'high-performance',
          preserveDrawingBuffer: false,
        }}
      >
        {/* ── Atmosphere ─────────────────────────────────────────────────── */}
        <color attach="background" args={['#020816']} />
        <fog attach="fog" args={['#020816', 30, 120]} />

        {/* ── Lighting ───────────────────────────────────────────────────── */}
        <ambientLight intensity={0.08} />
        {/* Cyan key light — top right */}
        <pointLight position={[15, 20, 10]}  color="#00d4ff" intensity={2.0} distance={80} />
        {/* Violet fill light — bottom left */}
        <pointLight position={[-20, -15, 5]} color="#7c3aed" intensity={1.5} distance={80} />
        {/* Deep blue rim — far back */}
        <pointLight position={[0, 0, -30]}   color="#1e40af" intensity={1.0} distance={100} />

        {/* ── Scene objects ──────────────────────────────────────────────── */}
        <Suspense fallback={null}>
          <ParticleField count={2500} />
          <FloatingGeometry />
        </Suspense>

        {/* ── Post-processing ────────────────────────────────────────────── */}
        <EffectComposer multisampling={0}>
          {/* Subtle bloom — glow on bright mesh surfaces */}
          <Bloom
            luminanceThreshold={0.4}
            luminanceSmoothing={0.6}
            intensity={0.8}
            mipmapBlur
          />
          {/* Vignette darkens edges for depth */}
          <Vignette eskil={false} offset={0.2} darkness={0.7} />
        </EffectComposer>
      </Canvas>
    </div>
  )
}
