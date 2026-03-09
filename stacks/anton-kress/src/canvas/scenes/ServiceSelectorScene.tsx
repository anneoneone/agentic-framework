import { useRef, useState, useCallback } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { useUIStore } from '@store/ui'
import type { ServiceType } from '@store/ui'
import orbVert from '../shaders/orb.vert?raw'
import orbFrag from '../shaders/orb.frag?raw'

interface OrbProps {
  position: [number, number, number]
  color: THREE.Color
  serviceId: ServiceType
  uTime: React.MutableRefObject<number>
  uProgress: React.MutableRefObject<number>
}

function Orb({ position, color, serviceId, uTime, uProgress }: OrbProps) {
  const matRef = useRef<THREE.ShaderMaterial>(null)
  const [hovered, setHovered] = useState(false)
  const currentService = useUIStore((s) => s.currentService)
  const setCurrentService = useUIStore((s) => s.setCurrentService)
  const isSelected = currentService === serviceId

  useFrame(() => {
    if (!matRef.current) return
    matRef.current.uniforms.uTime.value = uTime.current
    matRef.current.uniforms.uHover.value = THREE.MathUtils.lerp(
      matRef.current.uniforms.uHover.value, hovered ? 1 : 0, 0.08
    )
    matRef.current.uniforms.uSelected.value = THREE.MathUtils.lerp(
      matRef.current.uniforms.uSelected.value, isSelected ? 1 : 0, 0.06
    )
    matRef.current.uniforms.uProgress.value = uProgress.current
  })

  const handleClick = useCallback(() => {
    setCurrentService(isSelected ? null : serviceId)
  }, [isSelected, serviceId, setCurrentService])

  return (
    <mesh
      position={position}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
      onClick={handleClick}
      // Re-enable pointer events for this mesh only
      raycast={undefined}
    >
      <sphereGeometry args={[0.35, 64, 64]} />
      <shaderMaterial
        ref={matRef}
        vertexShader={orbVert}
        fragmentShader={orbFrag}
        uniforms={{
          uTime: { value: 0 },
          uHover: { value: 0 },
          uSelected: { value: 0 },
          uProgress: { value: 0 },
          uColor: { value: color },
        }}
        transparent
        depthWrite={false}
      />
    </mesh>
  )
}

interface ServiceSelectorSceneProps {
  uTime: React.MutableRefObject<number>
  uProgress: React.MutableRefObject<number>
}

const ORB_CONFIGS: Array<{ position: [number, number, number]; color: THREE.Color; id: ServiceType }> = [
  { position: [-1.2, 0, 0], color: new THREE.Color(0.47, 0.39, 0.86), id: 'web-dev' },   // purple
  { position: [0,   0, 0], color: new THREE.Color(0.2,  0.7,  0.9),  id: 'tool-dev' },  // cyan
  { position: [1.2, 0, 0], color: new THREE.Color(0.9,  0.4,  0.6),  id: 'ai-dev' },    // rose
]

export function ServiceSelectorScene({ uTime, uProgress }: ServiceSelectorSceneProps) {
  const { gl } = useThree()

  // Enable pointer events on this group's canvas region
  gl.domElement.style.pointerEvents = 'auto'

  return (
    <group>
      {ORB_CONFIGS.map((cfg) => (
        <Orb
          key={cfg.id}
          position={cfg.position}
          color={cfg.color}
          serviceId={cfg.id}
          uTime={uTime}
          uProgress={uProgress}
        />
      ))}
    </group>
  )
}
