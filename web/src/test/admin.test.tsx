import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { crearSolicitud } from '../api'
import Admin from '../vistas/Admin'
import { renderizar } from './render'
import { servidor } from './setup'

// Como responde hoy el backend real: sin evaluacion ni checklist_base, y ya firmado.
const ptwBackendActual = {
  ptw_id: 'PTW-REAL01',
  estado: 'autorizado_con_controles',
  solicitud: {
    tarea: 'Perforación de frente',
    labor: 'NV-3820 TJ-12',
    turno: 'noche',
    trabajador_id: 'T-001',
    altitud_msnm: 4210,
    tipo_mineria: 'subterranea',
    empleador: 'contratista',
  },
  consultas: {
    incidentes: { estado: 'ok', data: { casos_similares: 3, patron: '3 casos similares.', riesgo_potencial_max: 'alto', casos: [] } },
    area: {
      estado: 'ok',
      data: { labor: 'NV-3820 TJ-12', co_ppm: 12, o2_pct: 20.1, ventilacion: 'operativa', ruido_dBA: 91, ultimo_desatado_h: 26 },
    },
    gemelo: {
      estado: 'ok',
      data: { trabajador_id: 'T-001', apto_para_tarea: 'apto_con_observaciones', motivo_visible: 'Descanso bajo.', diagnostico: null },
    },
  },
  nanda: [],
  propuesta: {
    decision: 'autorizar_con_controles',
    nivel: 'ambar',
    requiere_supervisor: false,
    porque: ['Ruido 91 dBA supera el máximo de 85 dBA.', 'Último desatado 26 h supera el máximo de 12 h.'],
    controles_extra: ['Doble protección auditiva', 'Desatado antes de iniciar'],
    alternativa: 'Reprogramar la tarea.',
  },
}

// Pantalla grande y movimiento reducido: el tablero muestra al instante lo que pasó.
beforeEach(() => {
  vi.mocked(window.matchMedia).mockImplementation(
    (media: string) => ({ matches: true, media, addEventListener: () => {}, removeEventListener: () => {} }) as unknown as MediaQueryList,
  )
})

describe('sala de control del admin', () => {
  it('el detalle de Reglas muestra la tabla de verificación', async () => {
    renderizar(<Admin />, '/admin?ptw=PTW-SEED-07')
    const reglas = await screen.findByRole('button', { name: 'Reglas: ver detalle' }, { timeout: 3000 })
    fireEvent.focus(reglas)
    const detalle = await screen.findByRole('tooltip')
    expect(within(detalle).getByText('Último desatado')).toBeTruthy()
    expect(within(detalle).getByText('15 h')).toBeTruthy()
    expect(within(detalle).getByText('máximo 12 h')).toBeTruthy()
    expect(within(detalle).getAllByText('! Ámbar').length).toBeGreaterThan(0)
  })

  it('el detalle del Gemelo prueba diagnostico: null', async () => {
    renderizar(<Admin />, '/admin?ptw=PTW-SEED-07')
    fireEvent.focus(await screen.findByRole('button', { name: 'Gemelo: ver detalle' }, { timeout: 3000 }))
    const detalle = await screen.findByRole('tooltip')
    expect(within(detalle).getByText('diagnostico: null')).toBeTruthy()
  })

  it('el detalle del Agente PTW muestra lo que propuso la IA y lo confirmado', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    const { ptw_id } = await crearSolicitud({
      tarea: 'Perforación de frente', labor: 'NV-3820 TJ-12', turno: 'noche', trabajador_id: 'T-001',
      altitud_msnm: 4210, tipo_mineria: 'subterranea', empleador: 'contratista',
      actividad_id: 'ACT-01', interpretacion: { actividad_id: 'ACT-01', confianza: 'alta' },
    })
    vi.setSystemTime(Date.now() + 10_000)
    renderizar(<Admin />, `/admin?ptw=${ptw_id}`)
    fireEvent.focus(await screen.findByRole('button', { name: 'Agente PTW: ver detalle' }, { timeout: 3000 }))
    const detalle = await screen.findByRole('tooltip')
    expect(within(detalle).getByText(/confianza alta/)).toBeTruthy()
    expect(within(detalle).getByText(/lo confirmó/)).toBeTruthy()
    vi.useRealTimers()
  })

  it('con el backend de hoy no inventa reglas en orden ni cero controles base', async () => {
    servidor.use(http.get('*/ptw/PTW-REAL01', () => HttpResponse.json(ptwBackendActual)))
    renderizar(<Admin />, '/admin?ptw=PTW-REAL01')
    const reglas = await screen.findByRole('button', { name: 'Reglas: ver detalle' }, { timeout: 3000 })
    await waitFor(() => expect(within(reglas).getByText('2 motivos')).toBeTruthy())
    fireEvent.focus(screen.getByRole('button', { name: 'Decisión: ver detalle' }))
    const detalle = await screen.findByRole('tooltip')
    expect(within(detalle).queryByText(/0 controles base/)).toBeNull()
    expect(within(detalle).getByText('PETAR con el checklist base IPERC y 2 controles extra.')).toBeTruthy()
  })

  it('la burbuja de Juan sigue el estado del PETAR después de la firma', async () => {
    servidor.use(http.get('*/ptw/PTW-REAL01', () => HttpResponse.json(ptwBackendActual)))
    renderizar(<Admin />, '/admin?ptw=PTW-REAL01')
    expect(await screen.findByText('Tu permiso está listo', {}, { timeout: 3000 })).toBeTruthy()
    fireEvent.focus(screen.getByRole('button', { name: /Bandeja: ver detalle|Destino: ver detalle/ }))
    expect(within(await screen.findByRole('tooltip')).getByText(/ve: "Tu permiso está listo"/)).toBeTruthy()
  })

  it('un PETAR cerrado muestra la tarea cerrada en la burbuja', async () => {
    renderizar(<Admin />, '/admin?ptw=PTW-SEED-04')
    expect(await screen.findByText('Tarea cerrada con reporte', {}, { timeout: 3000 })).toBeTruthy()
  })

  it('la lista de solicitudes permite cambiar de PETAR', async () => {
    renderizar(<Admin />, '/admin?ptw=PTW-SEED-07')
    expect(await screen.findByText(/PTW-SEED-07: carguío de taladros en NV-4010 GA-20/, {}, { timeout: 3000 })).toBeTruthy()
    const recientes = await screen.findByRole('navigation', { name: 'Solicitudes recientes' })
    fireEvent.click(within(recientes).getAllByRole('button').find((b) => b.textContent?.includes('NV-3700 CH-02'))!)
    await waitFor(() => expect(screen.getByText(/PTW-SEED-03: perforación de chimenea en NV-3700 CH-02/)).toBeTruthy())
  })
})
