import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

/**
 * Registers a scroll-triggered reveal for a section element.
 * Children with [data-reveal] are staggered in after the section enters.
 * Returns a GSAP context for cleanup.
 */
export function registerSectionReveal(
  sectionEl: HTMLElement,
  options: {
    start?: string
    staggerChildren?: boolean
    yOffset?: number
  } = {}
): gsap.Context {
  const { start = 'top 80%', staggerChildren = true, yOffset = 60 } = options

  return gsap.context(() => {
    // Reveal the section itself
    gsap.fromTo(
      sectionEl,
      { opacity: 0, y: yOffset },
      {
        opacity: 1,
        y: 0,
        duration: 1,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: sectionEl,
          start,
          once: true,
        },
      }
    )

    // Stagger reveal child elements tagged with data-reveal
    if (staggerChildren) {
      const children = sectionEl.querySelectorAll('[data-reveal]')
      if (children.length > 0) {
        gsap.fromTo(
          children,
          { opacity: 0, y: 40 },
          {
            opacity: 1,
            y: 0,
            duration: 0.8,
            ease: 'power2.out',
            stagger: 0.12,
            scrollTrigger: {
              trigger: sectionEl,
              start,
              once: true,
            },
          }
        )
      }
    }
  }, sectionEl)
}

/** Register reveals for all sections at once, given a map of id → element. */
export function registerAllSectionReveals(
  sections: Partial<Record<string, HTMLElement>>
): gsap.Context[] {
  return Object.values(sections)
    .filter((el): el is HTMLElement => el != null)
    .map((el) => registerSectionReveal(el))
}
