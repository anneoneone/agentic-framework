import { motion } from 'framer-motion'
import { useUIStore } from '@store/ui'
import type { ServiceType } from '@store/ui'

interface ServiceCardProps {
  id: ServiceType
  label: string
  description: string
  index: number
}

const SERVICES: ServiceCardProps[] = [
  {
    id: 'web-dev',
    label: 'Web Development',
    description: 'Full-stack web applications built with precision and care.',
    index: 0,
  },
  {
    id: 'tool-dev',
    label: 'Tool Development',
    description: 'CLI tools, scripts, and automation that remove friction.',
    index: 1,
  },
  {
    id: 'ai-dev',
    label: 'AI Development',
    description: 'Agentic systems, custom agents, and MCP integrations.',
    index: 2,
  },
]

function ServiceCard({ id, label, description, index }: ServiceCardProps) {
  const currentService = useUIStore((s) => s.currentService)
  const setCurrentService = useUIStore((s) => s.setCurrentService)
  const isSelected = currentService === id

  return (
    <motion.button
      onClick={() => setCurrentService(isSelected ? null : id)}
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.6, delay: index * 0.12, ease: [0.22, 1, 0.36, 1] }}
      className={[
        'group text-left px-8 py-6 border transition-all duration-300 rounded-sm pointer-events-auto',
        isSelected
          ? 'border-accent/60 bg-accent/10'
          : 'border-muted/40 hover:border-accent/40 hover:bg-accent/5',
      ].join(' ')}
    >
      <p className="font-mono text-xs tracking-[0.2em] uppercase text-secondary mb-3 group-hover:text-accent transition-colors">
        {String(index + 1).padStart(2, '0')}
      </p>
      <h3 className="font-sans text-xl font-light text-primary mb-2">{label}</h3>
      <p className="text-sm text-secondary leading-relaxed">{description}</p>
    </motion.button>
  )
}

export function ServiceSelector() {
  const currentService = useUIStore((s) => s.currentService)
  const setCurrentService = useUIStore((s) => s.setCurrentService)

  return (
    <section
      id="service-selector"
      className="relative min-h-screen flex flex-col items-center justify-center px-6 md:px-16 py-24"
    >
      <motion.p
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        className="font-mono text-xs tracking-[0.25em] uppercase text-secondary mb-4"
      >
        Services
      </motion.p>
      <motion.h2
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="font-sans text-4xl md:text-5xl font-light text-primary mb-16 text-center"
      >
        What I build
      </motion.h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full max-w-4xl">
        {SERVICES.map((s) => (
          <ServiceCard key={s.id} {...s} />
        ))}
      </div>

      {currentService && (
        <motion.button
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          onClick={() => setCurrentService(null)}
          className="mt-12 font-mono text-xs tracking-widest uppercase text-secondary hover:text-primary transition-colors pointer-events-auto"
        >
          ← Back
        </motion.button>
      )}
    </section>
  )
}
