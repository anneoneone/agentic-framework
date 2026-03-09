import { create } from 'zustand'

export type ServiceType = 'web-dev' | 'tool-dev' | 'ai-dev' | null

interface UIState {
  menuOpen: boolean
  setMenuOpen: (open: boolean) => void
  currentService: ServiceType
  setCurrentService: (service: ServiceType) => void
}

export const useUIStore = create<UIState>()((set) => ({
  menuOpen: false,
  setMenuOpen: (open) => set({ menuOpen: open }),
  currentService: null,
  setCurrentService: (service) => set({ currentService: service }),
}))
