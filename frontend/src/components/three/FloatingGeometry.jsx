/**
 * components/three/FloatingGeometry.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Three slow-rotating geometric meshes that provide visual depth and a
 * "high-end trading terminal" aesthetic.
 *
 * Meshes:
 *   1. Wireframe torus knot  — centre/left, cyan
 *   2. Icosahedron           — top right, violet
 *   3. Octahedron            — bottom right, emissive blue
 *
 * Each mesh:
 *   - Uses MeshStandardMaterial with emissive colour so it glows under bloom
 *   - Rotates at a unique rate on all 3 axes
 *   - Moves slightly on a slow sin/cos path for an organic floating feel
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'

function FloatingMesh({ position, geometry, color, emissive, rotationSpeeds, pathRadius = 1, pathSpeed = 0.15 }) {
  const meshRef = useRef(null)
  const basePos = [...position]

  useFrame(({ clock }) => {
    if (!meshRef.current) return
    const t = clock.getElapsedTime()

    // Orbital path drift
    meshRef.current.position.x = basePos[0] + Math.sin(t * pathSpeed)        * pathRadius
    meshRef.current.position.y = basePos[1] + Math.cos(t * pathSpeed * 0.7)  * pathRadius * 0.6
    meshRef.current.position.z = basePos[2] + Math.sin(t * pathSpeed * 0.4)  * pathRadius * 0.3

    // Rotation
    meshRef.current.rotation.x += rotationSpeeds[0]
    meshRef.current.rotation.y += rotationSpeeds[1]
    meshRef.current.rotation.z += rotationSpeeds[2]
  })

  return (
    <mesh ref={meshRef} position={position}>
      {geometry}
      <meshStandardMaterial
        color={color}
        emissive={emissive}
        emissiveIntensity={0.6}
        wireframe
        transparent
        opacity={0.35}
      />
    </mesh>
  )
}

export default function FloatingGeometry() {
  return (
    <group>
      {/* 1 — Torus knot: centre-left, cyan, primary focal geometry */}
      <FloatingMesh
        position={[-14, 2, -10]}
        geometry={<torusKnotGeometry args={[3, 0.9, 96, 12]} />}
        color="#00d4ff"
        emissive="#00aacc"
        rotationSpeeds={[0.0008, 0.0012, 0.0004]}
        pathRadius={1.2}
        pathSpeed={0.12}
      />

      {/* 2 — Icosahedron: top right, violet */}
      <FloatingMesh
        position={[16, 10, -18]}
        geometry={<icosahedronGeometry args={[4.5, 1]} />}
        color="#7c3aed"
        emissive="#5b21b6"
        rotationSpeeds={[0.0006, 0.0008, 0.0010]}
        pathRadius={0.9}
        pathSpeed={0.09}
      />

      {/* 3 — Octahedron: lower right, deep blue */}
      <FloatingMesh
        position={[20, -8, -14]}
        geometry={<octahedronGeometry args={[3.5]} />}
        color="#1e40af"
        emissive="#1e3a8a"
        rotationSpeeds={[0.0012, 0.0006, 0.0008]}
        pathRadius={1.5}
        pathSpeed={0.18}
      />
    </group>
  )
}
