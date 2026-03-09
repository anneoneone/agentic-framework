import { useState } from 'react'
import { motion } from 'framer-motion'

interface FormState {
  name: string
  email: string
  message: string
}

type SubmitStatus = 'idle' | 'loading' | 'success' | 'error'

export function Contact() {
  const [form, setForm] = useState<FormState>({ name: '', email: '', message: '' })
  const [status, setStatus] = useState<SubmitStatus>('idle')

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setStatus('loading')
    try {
      // sendContactForm wired in step 17 (EmailJS integration)
      const { sendContactForm } = await import('@lib/emailjs')
      await sendContactForm(form)
      setStatus('success')
      setForm({ name: '', email: '', message: '' })
    } catch {
      setStatus('error')
    }
  }

  return (
    <section
      id="contact"
      className="relative min-h-screen flex items-center justify-center px-6 py-24"
    >
      <div className="w-full max-w-lg">
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="font-mono text-xs tracking-[0.25em] uppercase text-secondary mb-4 text-center"
        >
          Contact
        </motion.p>
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="font-sans text-4xl md:text-5xl font-light text-primary mb-12 text-center"
        >
          Get in touch
        </motion.h2>

        <motion.form
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, delay: 0.1 }}
          onSubmit={handleSubmit}
          className="flex flex-col gap-5 pointer-events-auto"
        >
          {(['name', 'email'] as const).map((field) => (
            <div key={field} className="flex flex-col gap-1">
              <label className="font-mono text-xs tracking-widest uppercase text-secondary capitalize">
                {field}
              </label>
              <input
                type={field === 'email' ? 'email' : 'text'}
                name={field}
                value={form[field]}
                onChange={handleChange}
                required
                className="bg-transparent border border-muted/40 text-primary px-4 py-3 font-sans text-sm focus:outline-none focus:border-accent/60 transition-colors"
              />
            </div>
          ))}

          <div className="flex flex-col gap-1">
            <label className="font-mono text-xs tracking-widest uppercase text-secondary">Message</label>
            <textarea
              name="message"
              value={form.message}
              onChange={handleChange}
              required
              rows={5}
              className="bg-transparent border border-muted/40 text-primary px-4 py-3 font-sans text-sm focus:outline-none focus:border-accent/60 transition-colors resize-none"
            />
          </div>

          <button
            type="submit"
            disabled={status === 'loading'}
            className="mt-2 border border-accent/60 text-primary font-mono text-xs tracking-widest uppercase px-8 py-4 hover:bg-accent/10 transition-colors disabled:opacity-50"
          >
            {status === 'loading' ? 'Sending…' : 'Send message'}
          </button>

          {status === 'success' && (
            <p className="font-mono text-xs text-accent text-center">Message sent. I'll be in touch.</p>
          )}
          {status === 'error' && (
            <p className="font-mono text-xs text-red-400 text-center">Something went wrong. Please try again.</p>
          )}
        </motion.form>
      </div>
    </section>
  )
}
