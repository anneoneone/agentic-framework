import { useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import transitionVert from '../shaders/transition.vert?raw'
import transitionFrag from '../shaders/transition.frag?raw'

interface TransitionSceneProps {
  uProgress: React.MutableRefObject<number>
}

export function TransitionScene({ uProgress }: TransitionSceneProps) {
  const matRef = useRef<THREE.ShaderMaterial>(null)
  const clockRef = useRef(0)
  const { viewport } = useThree()

  useFrame((_, delta) => {
    if (!matRef.current) return
    clockRef.current += delta
    matRef.current.uniforms.uTime.value = clockRef.current
    matRef.current.uniforms.uProgress.value = uProgress.current
  })

  return (
    <mesh position={[0, 0, 0.5]}>
      <planeGeometry args={[viewport.width, viewport.height]} />
      <shaderMaterial
        ref={matRef}
        vertexShader={transitionVert}
        fragmentShader={transitionFrag}
        uniforms={{
          uProgress: { value: 0 },
          uTime: { value: 0 },
        }}
        transparent
        depthWrite={false}
      />
    </mesh>
  )
}
