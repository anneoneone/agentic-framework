/**
 * Plausible Analytics helpers.
 * The Plausible script is injected into index.html in production only.
 * trackEvent() is a no-op if Plausible isn't loaded (dev, preview, or ad-blocked).
 */

declare global {
  interface Window {
    plausible?: (event: string, options?: { props?: Record<string, string> }) => void
  }
}

export function trackEvent(name: string, props?: Record<string, string>): void {
  if (typeof window !== 'undefined' && typeof window.plausible === 'function') {
    window.plausible(name, { props })
  }
}

/** Common events */
export const analytics = {
  contactFormSubmit: () => trackEvent('Contact Form Submit'),
  serviceSelected: (service: string) => trackEvent('Service Selected', { service }),
  sectionViewed: (section: string) => trackEvent('Section Viewed', { section }),
}
