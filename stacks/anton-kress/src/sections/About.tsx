import { motion } from 'framer-motion'

const variants = {
  hidden: { opacity: 0, y: 40 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] as const } },
}

export function About() {
  return (
    <section
      id="about"
      className="relative min-h-screen flex items-center px-6 md:px-16 py-24"
    >
      <div className="max-w-5xl mx-auto w-full grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
        {/* Bio — left */}
        <motion.div
          data-reveal
          variants={variants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
        >
          <p className="font-mono text-xs tracking-[0.25em] uppercase text-secondary mb-6">
            About
          </p>
          <h2 className="font-sans text-4xl md:text-5xl font-light text-primary mb-8 leading-tight">
            Craft at the<br />intersection of<br />code and design.
          </h2>
          <p className="text-secondary leading-relaxed mb-4">
            I build things that feel alive — web applications with depth, tools that remove friction,
            and AI systems that extend human capability.
          </p>
          <p className="text-secondary leading-relaxed">
            Based in Europe. Available for select projects.
          </p>
        </motion.div>

        {/* Decorative element — right */}
        <motion.div
          data-reveal
          variants={variants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          className="flex items-center justify-center"
        >
          <div className="relative w-64 h-64">
            <div className="absolute inset-0 rounded-full border border-accent/20 animate-[spin_20s_linear_infinite]" />
            <div className="absolute inset-4 rounded-full border border-accent/30 animate-[spin_15s_linear_infinite_reverse]" />
            <div className="absolute inset-8 rounded-full border border-accent/40 animate-[spin_10s_linear_infinite]" />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="font-mono text-xs tracking-widest text-accent/60 uppercase">AK</span>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
