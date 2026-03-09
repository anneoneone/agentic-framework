import { motion } from 'framer-motion'
import type { Project } from '@/data/projects'

interface ProjectCardProps {
  project: Project
  index: number
}

export function ProjectCard({ project, index }: ProjectCardProps) {
  return (
    <motion.div
      data-reveal
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.6, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] }}
      className={[
        'group border p-6 transition-colors duration-300',
        project.highlight
          ? 'border-accent/40 bg-accent/5'
          : 'border-muted/30 hover:border-muted/60',
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-4 mb-3">
        <h3 className="font-sans text-lg font-light text-primary">{project.title}</h3>
        {project.url && (
          <a
            href={project.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-xs text-secondary hover:text-accent transition-colors shrink-0 pointer-events-auto"
          >
            ↗
          </a>
        )}
      </div>

      <p className="text-sm text-secondary leading-relaxed mb-4">{project.description}</p>

      <div className="flex flex-wrap gap-2">
        {project.tags.map((tag) => (
          <span
            key={tag}
            className="font-mono text-xs text-muted/80 border border-muted/30 px-2 py-0.5"
          >
            {tag}
          </span>
        ))}
      </div>
    </motion.div>
  )
}
