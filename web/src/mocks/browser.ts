import { setupWorker } from 'msw/browser'
import { handlers, reiniciarMocks } from './handlers'

export async function iniciarMocks() {
  if (new URLSearchParams(window.location.search).has('reiniciar')) reiniciarMocks()
  await setupWorker(...handlers).start({ onUnhandledRequest: 'bypass', quiet: true })
}
