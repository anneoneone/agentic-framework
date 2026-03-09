import { Canvas } from '@react-three/fiber'
import { OrthographicCamera } from '@react-three/drei'
import { useCanvasStore } from '@store/canvas'
import { useShaderUniforms } from '@hooks/useShaderUniforms'
import { HeroScene } from './scenes/HeroScene'
import { ServiceSelectorScene } from './scenes/ServiceSelectorScene'
import { TransitionScene } from './scenes/TransitionScene'

export default function SceneRoot() {
  const setCanvasReady = useCanvasStore((s) => s.setCanvasReady)
  const uniforms = useShaderUniforms()

  return (
    <Canvas
      frameloop="demand"
      dpr={[1, 2]}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 0,
        pointerEvents: 'none',
      }}
      onCreated={() => setCanvasReady(true)}
    >
      <OrthographicCamera makeDefault position={[0, 0, 1]} zoom={1} />

      <HeroScene uTime={uniforms.uTime} uProgress={uniforms.uProgress} />
      <ServiceSelectorScene uTime={uniforms.uTime} uProgress={uniforms.uProgress} />
      <TransitionScene uProgress={uniforms.uProgress} />
    </Canvas>
  )
}
