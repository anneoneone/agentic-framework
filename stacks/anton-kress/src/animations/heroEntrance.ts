import { Variants } from 'framer-motion'

/** Framer Motion variants for the Hero section entrance. */
export const heroContainerVariants: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.18,
      delayChildren: 0.3,
    },
  },
}

export const heroItemVariants: Variants = {
  hidden: { opacity: 0, y: 32 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, ease: [0.22, 1, 0.36, 1] },
  },
}

export const heroScrollIndicatorVariants: Variants = {
  hidden: { opacity: 0, y: -8 },
  visible: {
    opacity: [0, 1, 0.6, 1],
    y: [0, 8, 0],
    transition: {
      delay: 1.4,
      duration: 1.8,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
}
