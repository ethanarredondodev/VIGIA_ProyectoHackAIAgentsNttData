import { cleanup } from '@testing-library/react'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { handlers, reiniciarMocks } from '../mocks/handlers'

export const servidor = setupServer(...handlers)

// jsdom no trae matchMedia: por defecto, pantalla angosta y con movimiento.
const sinMedios = (media: string) =>
  ({ matches: false, media, addEventListener: () => {}, removeEventListener: () => {} }) as unknown as MediaQueryList
Object.defineProperty(window, 'matchMedia', { writable: true, value: vi.fn(sinMedios) })

beforeAll(() => servidor.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  servidor.resetHandlers()
  reiniciarMocks()
})
afterAll(() => servidor.close())
