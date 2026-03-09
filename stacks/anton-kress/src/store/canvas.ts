import { create } from 'zustand'

export type SectionName = 'hero' | 'about' | 'service-selector' | 'web-dev' | 'tool-dev' | 'ai-dev' | 'contact'

interface CanvasState {
  activeSection: SectionName
  setActiveSection: (section: SectionName) => void
  canvasReady: boolean
  setCanvasReady: (ready: boolean) => void
}

export const useCanvasStore = create<CanvasState>()((set) => ({
  activeSection: 'hero',
  setActiveSection: (section) => set({ activeSection: section }),
  canvasReady: false,
  setCanvasReady: (ready) => set({ canvasReady: ready }),
}))
