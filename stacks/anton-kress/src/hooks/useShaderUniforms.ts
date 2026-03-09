import { useRef } from 'react'

export interface ShaderUniforms {
  uTime: React.MutableRefObject<number>
  uProgress: React.MutableRefObject<number>
}

/**
 * Returns refs for uTime and uProgress.
 * These refs are updated each frame by the animation layer (@animation-expert)
 * and consumed by R3F scene components via useFrame.
 * Using refs (not state) avoids React re-renders on every frame.
 */
export function useShaderUniforms(): ShaderUniforms {
  const uTime = useRef(0)
  const uProgress = useRef(0)
  return { uTime, uProgress }
}
