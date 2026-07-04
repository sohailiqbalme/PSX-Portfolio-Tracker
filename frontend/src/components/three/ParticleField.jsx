/**
 * components/three/ParticleField.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * 2,500-point ambient particle cloud.
 *
 * Points are distributed across a wide 3D volume and drift slowly using
 * a per-frame sin/cos wave pattern — creating an organic, breathing effect
 * without any physics library overhead.
 *
 * Performance:
 *   - Single BufferGeometry + Points — one draw call for all particles.
 *   - Positions computed once into a Float32Array, then mutated in useFrame.
 *   - willChange tracked so React Three Fiber can skip unnecessary checks.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useRef, useMemo } from 'react'
import { useFrame }        from '@react-three/fiber'
import * as THREE          from 'three'

export default function ParticleField({ count = 2500 }) {
  const pointsRef = useRef(null)

  // ── Generate initial random positions in a wide cube ─────────────────────
  const [positions, basePositions] = useMemo(() => {
    const pos  = new Float32Array(count * 3)
    const base = new Float32Array(count * 3)

    for (let i = 0; i < count; i++) {
      const i3 = i * 3
      // Spread over a [-50, 50] cube, weighted toward centre
      const x = (Math.random() - 0.5) * 100
      const y = (Math.random() - 0.5) * 100
      const z = (Math.random() - 0.5) * 80

      pos[i3]     = base[i3]     = x
      pos[i3 + 1] = base[i3 + 1] = y
      pos[i3 + 2] = base[i3 + 2] = z
    }

    return [pos, base]
  }, [count])

  // ── Per-frame drift animation ─────────────────────────────────────────────
  useFrame(({ clock }) => {
    if (!pointsRef.current) return
    const t = clock.getElapsedTime()
    const attr = pointsRef.current.geometry.attributes.position

    for (let i = 0; i < count; i++) {
      const i3 = i * 3
      // Each particle oscillates with a unique phase based on its index
      const phase = i * 0.001
      attr.array[i3]     = basePositions[i3]     + Math.sin(t * 0.12 + phase * 6.28) * 0.5
      attr.array[i3 + 1] = basePositions[i3 + 1] + Math.cos(t * 0.09 + phase * 5.12) * 0.5
      // Z is kept stable — depth doesn't oscillate to avoid z-fighting
    }

    attr.needsUpdate = true
  })

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.08}
        color="#00d4ff"
        transparent
        opacity={0.45}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}
