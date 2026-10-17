import { fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { USUARIOS } from '../sesion'
import type { Ptw } from '../tipos'
import Supervisor, { DetalleCaso } from '../vistas/Supervisor'
import { renderizar } from './render'
import { servidor } from './setup'

const ROSA = USUARIOS[1]

const cerrada = (ptw_id: string, trabajador_id: string, cerrado_en: string): Ptw => ({
  ptw_id,
  estado: 'cerrado',
  solicitud: {
    tarea: 'desatado de rocas',
    labor: 'NV-3900 GA-05',
    turno: 'dia',
    trabajador_id,
    altitud_msnm: 4210,
    tipo_mineria: 'subterranea',
    empleador: 'contratista',
  },
  consultas: { incidentes: { estado: 'ok' }, area: { estado: 'ok' }, gemelo: { estado: 'ok' } },
  nanda: [],
  cerrado_en,
  resultado: { resultado: 'sin_novedad', controles_cumplidos: true, observacion: `Cerrada ${cerrado_en}.` },
})

describe('pestaña Reportes del supervisor', () => {
  it('Reportes lista las tareas cerradas con su resultado', async () => {
    renderizar(<Supervisor />, '/supervisor', ROSA)
    fireEvent.click(await screen.findByRole('tab', { name: /Reportes\s*2/ }, { timeout: 3000 }))
    expect(await screen.findByText('María Condori', {}, { timeout: 3000 })).toBeTruthy()
    expect(await screen.findByText('Yeni Torres', {}, { timeout: 3000 })).toBeTruthy()
    expect(screen.getByText('Casi incidente')).toBeTruthy()
    expect(screen.getByText('Un volquete invadió el carril en la rampa; se detuvo a tiempo.')).toBeTruthy()
    expect(screen.getByText('Incidente')).toBeTruthy()
    expect(screen.getByText('Sin novedad')).toBeTruthy()
  })

  it('Reportes pone primero la tarea cerrada más reciente', async () => {
    servidor.use(
      http.get('*/ptw', () =>
        HttpResponse.json([
          cerrada('PTW-A', 'T-002', '2026-10-17T08:00:00.000Z'),
          cerrada('PTW-B', 'T-104', '2026-10-17T10:00:00.000Z'),
          cerrada('PTW-C', 'T-102', '2026-10-17T09:00:00.000Z'),
        ]),
      ),
    )
    renderizar(<Supervisor />, '/supervisor', ROSA)
    fireEvent.click(await screen.findByRole('tab', { name: /Reportes/ }))
    const observaciones = await screen.findAllByText(/^Cerrada /, {}, { timeout: 3000 })
    expect(observaciones.map((o) => o.textContent)).toEqual([
      'Cerrada 2026-10-17T10:00:00.000Z.',
      'Cerrada 2026-10-17T09:00:00.000Z.',
      'Cerrada 2026-10-17T08:00:00.000Z.',
    ])
  })

  it('Reportes muestra la tarea cerrada aunque el backend no mande el resultado', async () => {
    const { resultado: _, ...sinResultado } = cerrada('PTW-D', 'T-002', '2026-10-17T08:00:00.000Z')
    servidor.use(http.get('*/ptw', () => HttpResponse.json([sinResultado])))
    renderizar(<Supervisor />, '/supervisor', ROSA)
    fireEvent.click(await screen.findByRole('tab', { name: /Reportes\s*0/ }))
    expect(await screen.findByText('Desatado de rocas', {}, { timeout: 3000 })).toBeTruthy()
    expect(screen.getByText('Sin reporte del trabajador.')).toBeTruthy()
  })

  it('Reportes avisa si todavía no hay tareas cerradas', async () => {
    servidor.use(http.get('*/ptw', () => HttpResponse.json([])))
    renderizar(<Supervisor />, '/supervisor', ROSA)
    fireEvent.click(await screen.findByRole('tab', { name: /Reportes/ }))
    expect(await screen.findByText('Todavía no hay reportes de tareas cerradas.', {}, { timeout: 3000 })).toBeTruthy()
  })

  it('la bandeja no cambia', async () => {
    renderizar(<Supervisor />, '/supervisor', ROSA)
    expect(await screen.findByRole('tab', { name: /Por revisar\s*4/ }, { timeout: 3000 })).toBeTruthy()
    expect(screen.getByRole('tab', { name: /Avisos\s*4/ })).toBeTruthy()
  })
})

describe('firma del supervisor', () => {
  it('antes de firmar se ve el checklist base', async () => {
    renderizar(<DetalleCaso ptwId="PTW-SEED-07" />, '/', ROSA)
    expect(await screen.findByText('Checklist base IPERC (va siempre)', {}, { timeout: 3000 })).toBeTruthy()
    expect(screen.getByText('Llenar el IPERC continuo al inicio de la tarea y realizar la charla de 5 minutos')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Aceptar y firmar' })).toBeTruthy()
  })

  it('firma con el nombre del usuario', async () => {
    const cuerpos: unknown[] = []
    servidor.use(
      http.post('*/ptw/:id/firma', async ({ request }) => {
        cuerpos.push(await request.json())
        return HttpResponse.json({})
      }),
    )
    renderizar(<DetalleCaso ptwId="PTW-SEED-07" />, '/', ROSA)
    fireEvent.click(await screen.findByRole('button', { name: 'Aceptar y firmar' }, { timeout: 3000 }))
    await waitFor(() => expect(cuerpos).toHaveLength(1))
    expect(cuerpos[0]).toMatchObject({ supervisor: 'Ing. Rosa Quispe', accion: 'aceptar' })
  })
})
