import { motion } from 'framer-motion'
import {
  heroContainerVariants,
  heroItemVariants,
  heroScrollIndicatorVariants,
} from '@animations/heroEntrance'

export function Hero() {
  return (
    <section
      id="hero"
      className="relative flex min-h-screen items-center justify-center pointer-events-none"
    >
      <motion.div
        className="text-center px-6 select-none"
        variants={heroContainerVariants}
        initial="hidden"
        animate="visible"
      >
        <motion.p
          data-reveal
          variants={heroItemVariants}
          className="font-mono text-sm tracking-[0.3em] uppercase text-secondary mb-6"
        >
          Portfolio
        </motion.p>

        <motion.h1
          data-reveal
          variants={heroItemVariants}
          className="font-sans text-6xl md:text-8xl font-light tracking-tight text-primary mb-4"
        >
          Anton Kress
        </motion.h1>

        <motion.p
          data-reveal
          variants={heroItemVariants}
          className="font-sans text-lg md:text-xl text-secondary max-w-md mx-auto leading-relaxed"
        >
          Web development · Tool development · AI systems
        </motion.p>

        {/* Scroll indicator */}
        <motion.div
          variants={heroScrollIndicatorVariants}
          className="mt-20 flex flex-col items-center gap-2 text-muted"
        >
          <span className="font-mono text-xs tracking-widest uppercase">Scroll</span>
          <svg width="16" height="24" viewBox="0 0 16 24" fill="none" className="opacity-60">
            <rect x="6.5" y="0.5" width="3" height="3" rx="1.5" fill="currentColor" />
            <line x1="8" y1="6" x2="8" y2="23" stroke="currentColor" strokeWidth="1" />
            <polyline points="4,18 8,23 12,18" stroke="currentColor" strokeWidth="1" fill="none" />
          </svg>
        </motion.div>
      </motion.div>
    </section>
  )
}
