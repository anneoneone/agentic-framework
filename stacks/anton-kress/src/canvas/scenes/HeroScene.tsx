import { useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import heroVert from '../shaders/hero.vert?raw'
import heroFrag from '../shaders/hero.frag?raw'

interface HeroSceneProps {
  uTime: React.MutableRefObject<number>
  uProgress: React.MutableRefObject<number>
}

export function HeroScene({ uTime, uProgress }: HeroSceneProps) {
  const matRef = useRef<THREE.ShaderMaterial>(null)
  const { viewport } = useThree()

  useFrame(() => {
    if (!matRef.current) return
    matRef.current.uniforms.uTime.value = uTime.current
    matRef.current.uniforms.uProgress.value = uProgress.current
  })

  return (
    <mesh>
      <planeGeometry args={[viewport.width, viewport.height, 32, 32]} />
      <shaderMaterial
        ref={matRef}
        vertexShader={heroVert}
        fragmentShader={heroFrag}
        uniforms={{
          uTime: { value: 0 },
          uProgress: { value: 0 },
        }}
      />
    </mesh>
  )
}
