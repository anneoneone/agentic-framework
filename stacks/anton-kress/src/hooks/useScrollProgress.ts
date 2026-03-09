import { useRef, useEffect } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

export interface SectionProgress {
  /** Normalised scroll progress through the section: 0 (top enters viewport) → 1 (bottom leaves) */
  progress: number
}

/**
 * Returns a ref holding the current scroll progress (0–1) for a given section element.
 * Uses ScrollTrigger so it integrates correctly with the Lenis+GSAP ticker.
 */
export function useScrollProgress(
  sectionRef: React.RefObject<HTMLElement>,
  options: { start?: string; end?: string } = {}
): React.MutableRefObject<number> {
  const progressRef = useRef(0)

  useEffect(() => {
    const el = sectionRef.current
    if (!el) return

    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: el,
        start: options.start ?? 'top bottom',
        end: options.end ?? 'bottom top',
        onUpdate: (self) => {
          progressRef.current = self.progress
        },
      })
    }, el)

    return () => ctx.revert()
  }, [sectionRef, options.start, options.end])

  return progressRef
}
