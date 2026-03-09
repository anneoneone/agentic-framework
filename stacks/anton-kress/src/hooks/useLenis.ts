import { useEffect, useRef } from 'react'
import type Lenis from 'lenis'
import { createLenis, getLenis, destroyLenis } from '@lib/lenis'

export function useLenis(): Lenis | null {
  const lenisRef = useRef<Lenis | null>(null)

  useEffect(() => {
    lenisRef.current = createLenis()

    return () => {
      destroyLenis()
    }
  }, [])

  return lenisRef.current ?? getLenis()
}
