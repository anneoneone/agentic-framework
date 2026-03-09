import Lenis from 'lenis'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

let lenisInstance: Lenis | null = null

export function createLenis(): Lenis {
  if (lenisInstance) return lenisInstance

  lenisInstance = new Lenis({
    duration: 1.2,
    easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    smoothWheel: true,
  })

  // Wire Lenis to GSAP ticker
  gsap.ticker.add((time) => {
    lenisInstance!.raf(time * 1000)
  })

  // Disable GSAP lag smoothing for accurate ScrollTrigger timing
  gsap.ticker.lagSmoothing(0)

  // Refresh ScrollTrigger on each Lenis scroll event
  lenisInstance.on('scroll', ScrollTrigger.update)

  return lenisInstance
}

export function getLenis(): Lenis | null {
  return lenisInstance
}

export function destroyLenis(): void {
  if (lenisInstance) {
    lenisInstance.destroy()
    lenisInstance = null
  }
}
