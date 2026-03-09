import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import type { ServiceType } from '@store/ui'

gsap.registerPlugin(ScrollTrigger)

/**
 * Scroll-based reveal of the service selector section.
 * Returns a cleanup function.
 */
export function initServiceSelectorReveal(sectionEl: HTMLElement): () => void {
  const ctx = gsap.context(() => {
    gsap.fromTo(
      sectionEl,
      { opacity: 0, scale: 0.96 },
      {
        opacity: 1,
        scale: 1,
        duration: 1.1,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: sectionEl,
          start: 'top 75%',
          once: true,
        },
      }
    )
  }, sectionEl)

  return () => ctx.revert()
}

/**
 * Animate the orb expansion when a service is selected.
 * Drives uProgress 0→1 over 0.8s on the provided ref.
 */
export function animateOrbSelect(
  uProgressRef: React.MutableRefObject<number>,
  _service: ServiceType
): gsap.core.Tween {
  return gsap.to(uProgressRef, {
    current: 1,
    duration: 0.8,
    ease: 'power2.inOut',
  })
}

/**
 * Animate orb deselection — collapse uProgress back to 0.
 */
export function animateOrbDeselect(
  uProgressRef: React.MutableRefObject<number>
): gsap.core.Tween {
  return gsap.to(uProgressRef, {
    current: 0,
    duration: 0.5,
    ease: 'power2.out',
  })
}

/**
 * Section exit animation — fade out before navigating away.
 */
export function animateSectionExit(sectionEl: HTMLElement): gsap.core.Tween {
  return gsap.to(sectionEl, {
    opacity: 0,
    y: -30,
    duration: 0.4,
    ease: 'power2.in',
  })
}
