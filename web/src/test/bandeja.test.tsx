import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { separarBandeja } from '../negocio'
import type { ItemBandeja } from '../tipos'
import Supervisor from '../vistas/Supervisor'
import { renderizar } from './render'
import { servidor } from './setup'

const item = (nombre: string, nivel: ItemBandeja['nivel'], requiere: boolean, tipo: ItemBandeja['tipo']): ItemBandeja => ({
  ptw_id: `PTW-${nombre}`,
  nivel,
  requiere_supervisor: requiere,
  trabajador_nombre: nombre,
  tarea: 'perforación de frente',
  labor: 'NV-3820 TJ-12',
  turno: 'noche',
  creado_en: '2026-10-17T05:00:00Z',
  tipo,
})

describe('los verdes no aparecen en la bandeja del supervisor', () => {
  it('descarta un verde sin alto riesgo aunque el backend lo envíe', () => {
    const { porRevisar, avisos } = separarBandeja([
      item('Verde', 'verde', false, 'revision'),
      item('VerdeAltoRiesgo', 'verde', true, 'revision'),
      item('Ambar', 'ambar', false, 'revision'),
      item('Rojo', 'rojo', false, 'aviso'),
    ])
    expect(porRevisar.map((i) => i.trabajador_nombre)).toEqual(['VerdeAltoRiesgo', 'Ambar'])
    expect(avisos.map((i) => i.trabajador_nombre)).toEqual(['Rojo'])
  })

  it('la vista del supervisor no lista los verdes emitidos de la demo', async () => {
    renderizar(<Supervisor />, '/supervisor')
    const panel = await screen.findByRole('tabpanel')
    await within(panel).findByText('Carlos Huanca')
    for (const nombre of ['Rosa Huanca', 'Wilber Ramos', 'Nely Apaza']) {
      expect(within(panel).getByText(nombre)).toBeTruthy()
    }
    expect(screen.queryByText('María Condori')).toBeNull()
    expect(screen.queryByText('Yeni Torres')).toBeNull()
    expect(screen.getByText('Los casos verdes se emiten solos y no llegan aquí.')).toBeTruthy()
    expect(screen.getByRole('tab', { name: /Por revisar\s*4/ })).toBeTruthy()
    expect(screen.getByRole('tab', { name: /Avisos\s*4/ })).toBeTruthy()
  })

  it('la vista filtra un verde que el backend mande por error', async () => {
    servidor.use(
      http.get('*/ptw/bandeja', () =>
        HttpResponse.json([item('Colado Verde', 'verde', false, 'revision'), item('Caso Ambar', 'ambar', false, 'revision')]),
      ),
      http.get('*/ptw/:id', () => HttpResponse.json({}, { status: 404 })),
    )
    renderizar(<Supervisor />, '/supervisor')
    await screen.findByText('Caso Ambar')
    expect(screen.queryByText('Colado Verde')).toBeNull()
  })
})
