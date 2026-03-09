import emailjs from '@emailjs/browser'

export interface ContactFormData {
  name: string
  email: string
  message: string
}

/**
 * Send a contact form message via EmailJS.
 * Reads service/template/key from Vite env vars — all must be set in .env.
 */
export async function sendContactForm(data: ContactFormData): Promise<void> {
  const serviceId = import.meta.env.VITE_EMAILJS_SERVICE_ID
  const templateId = import.meta.env.VITE_EMAILJS_TEMPLATE_ID
  const publicKey = import.meta.env.VITE_EMAILJS_PUBLIC_KEY

  if (!serviceId || !templateId || !publicKey) {
    throw new Error('EmailJS environment variables are not configured. See .env.example.')
  }

  await emailjs.send(serviceId, templateId, { ...data }, publicKey)
}
