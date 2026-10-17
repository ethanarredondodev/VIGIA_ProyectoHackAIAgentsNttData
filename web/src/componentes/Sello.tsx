import type { ReactNode } from 'react'
import { CLASES_NIVEL, TEXTO_NIVEL } from '../negocio'
import type { Nivel } from '../tipos'

type Icono = 'check' | 'alerta' | 'equis'

const TRAZOS: Record<Icono, ReactNode> = {
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  alerta: (
    <>
      <path d="M12 5.5v8.5" />
      <circle cx="12" cy="18.5" r="1.4" fill="currentColor" stroke="none" />
    </>
  ),
  equis: <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />,
}

export const ICONO_NIVEL: Record<Nivel, Icono> = { verde: 'check', ambar: 'alerta', rojo: 'equis' }

export function IconoEstado({ icono, className = 'size-4' }: { icono: Icono; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`shrink-0 ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="2.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {TRAZOS[icono]}
    </svg>
  )
}

export function SelloNivel({ nivel, altoRiesgo = false }: { nivel: Nivel; altoRiesgo?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-sm px-2 py-0.5 font-cond text-sm font-semibold ${CLASES_NIVEL[nivel].relleno}`}
    >
      <IconoEstado icono={ICONO_NIVEL[nivel]} className="size-3.5" />
      {TEXTO_NIVEL[nivel]}
      {altoRiesgo && nivel !== 'rojo' && ', alto riesgo'}
    </span>
  )
}
