import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { SesionProvider } from './sesion'
import './index.css'

async function arrancar() {
  if (import.meta.env.VITE_USE_MOCKS === 'true') {
    const { iniciarMocks } = await import('./mocks/browser')
    await iniciarMocks()
  }
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={cliente}>
        <SesionProvider>
          <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <App />
          </BrowserRouter>
        </SesionProvider>
      </QueryClientProvider>
    </React.StrictMode>,
  )
}

arrancar()
