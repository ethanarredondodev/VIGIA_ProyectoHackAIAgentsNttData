import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { SesionProvider, USUARIOS, type Usuario } from '../sesion'

export function renderizar(ui: ReactElement, ruta = '/', usuario: Usuario | null = USUARIOS[2]) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <SesionProvider inicial={usuario}>
        <MemoryRouter initialEntries={[ruta]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          {ui}
        </MemoryRouter>
      </SesionProvider>
    </QueryClientProvider>,
  )
}
