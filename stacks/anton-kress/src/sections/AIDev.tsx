import { motion } from 'framer-motion'
import { aiProjects } from '@/data/projects'
import { ProjectCard } from '@/components/ProjectCard'

export function AIDev() {
  return (
    <section id="ai-dev" className="relative min-h-screen px-6 md:px-16 py-24">
      <div className="max-w-4xl mx-auto">
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="font-mono text-xs tracking-[0.25em] uppercase text-secondary mb-4"
        >
          AI Development
        </motion.p>
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="font-sans text-4xl md:text-5xl font-light text-primary mb-16"
        >
          Agents &amp; systems
        </motion.h2>

        <div className="flex flex-col gap-6">
          {aiProjects.map((project, i) => (
            <ProjectCard key={project.title} project={project} index={i} />
          ))}
        </div>
      </div>
    </section>
  )
}
