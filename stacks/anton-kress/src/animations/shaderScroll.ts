import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import type { ShaderUniforms } from '@hooks/useShaderUniforms'

gsap.registerPlugin(ScrollTrigger)

/**
 * Drives uTime continuously via requestAnimationFrame (independent of scroll).
 * Drives uProgress per-section via ScrollTrigger (0→1 as section scrolls through viewport).
 *
 * Call once after Lenis is initialised and DOM sections are mounted.
 */
export function initShaderScroll(
  uniforms: ShaderUniforms,
  sectionEl: HTMLElement
): () => void {
  let rafId: number
  let startTime = performance.now()

  // Continuous time tick — drives uTime for all shaders
  function tick() {
    uniforms.uTime.current = (performance.now() - startTime) / 1000
    rafId = requestAnimationFrame(tick)
  }
  rafId = requestAnimationFrame(tick)

  // Scroll-driven uProgress for this section (0 when section top hits center, 1 at bottom)
  const ctx = gsap.context(() => {
    ScrollTrigger.create({
      trigger: sectionEl,
      start: 'top center',
      end: 'bottom center',
      onUpdate: (self) => {
        uniforms.uProgress.current = self.progress
      },
    })
  })

  return () => {
    cancelAnimationFrame(rafId)
    ctx.revert()
  }
}
