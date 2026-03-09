import React from 'react'
import { useLenis } from '@hooks/useLenis'
import { Hero } from '@sections/Hero'
import { About } from '@sections/About'
import { ServiceSelector } from '@sections/ServiceSelector'
import { WebDev } from '@sections/WebDev'
import { ToolDev } from '@sections/ToolDev'
import { AIDev } from '@sections/AIDev'
import { Contact } from '@sections/Contact'

// SceneRoot created in step 6 — lazy-loaded so R3F doesn't block initial render
const SceneRoot = React.lazy(() => import('@canvas/SceneRoot'))

export default function App() {
  useLenis()

  return (
    <>
      {/* Fixed fullscreen WebGL canvas — z-0, sits behind UI */}
      <React.Suspense fallback={null}>
        <SceneRoot />
      </React.Suspense>

      {/* Scrollable UI layer — z-10 above canvas */}
      <div className="relative z-10">
        <Hero />
        <About />
        <ServiceSelector />
        <WebDev />
        <ToolDev />
        <AIDev />
        <Contact />
      </div>
    </>
  )
}
