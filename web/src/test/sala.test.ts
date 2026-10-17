import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { avanzar, INICIAL, ORDEN, salaReal, useSala, type EstadoSala } from '../sala'
import type { Ptw } from '../tipos'

const base: Ptw = {
  ptw_id: 'PTW-A',
  estado: 'procesando',
  solicitud: {
    tarea: 'Perforación de frente', labor: 'NV-3820 TJ-12', turno: 'noche', trabajador_id: 'T-001',
    altitud_msnm: 4210, tipo_mineria: 'subterranea', empleador: 'contratista',
  },
  consultas: { incidentes: { estado: 'pendiente' }, area: { estado: 'pendiente' }, gemelo: { estado: 'pendiente' } },
  nanda: [],
}
const ficha = { id: 'vigia-area', capabilities: ['area.condiciones'], firma: 'valida' as const }
const terminado: Ptw = {
  ...base,
  estado: 'en_revision',
  consultas: { incidentes: { estado: 'ok' }, area: { estado: 'ok' }, gemelo: { estado: 'ok' } },
  nanda: [ficha],
  propuesta: { decision: 'autorizar_con_controles', nivel: 'ambar', requiere_supervisor: false, porque: [], controles_extra: [], alternativa: '' },
}
const todoListo = Object.fromEntries(ORDEN.map((e) => [e, 'listo'])) as EstadoSala

describe('repetición fiel de la sala de control', () => {
  it('un PETAR terminado está todo listo en la realidad', () => {
    expect(salaReal(terminado)).toEqual(todoListo)
  })

  it('un PETAR terminado se muestra etapa por etapa, en orden', () => {
    let mostrado = INICIAL
    const completadas: string[] = []
    for (let i = 0; i < 8; i++) {
      const siguiente = avanzar(mostrado, todoListo)
      completadas.push(ORDEN.find((e) => mostrado[e] !== 'listo' && siguiente[e] === 'listo')!)
      mostrado = siguiente
    }
    expect(completadas).toEqual(ORDEN.slice(1))
    expect(mostrado).toEqual(todoListo)
  })

  it('nunca se adelanta al dato real', () => {
    const real = salaReal(base)
    expect(real.nanda).toBe('proceso')
    const tras = avanzar(INICIAL, real)
    expect(tras.ptw).toBe('listo')
    expect(avanzar(tras, real)).toBe(tras)
  })

  it('una consulta con error deja seguir a reglas', () => {
    const real = salaReal({ ...terminado, consultas: { ...terminado.consultas, area: { estado: 'error' } } })
    let mostrado = INICIAL
    for (let i = 0; i < 8; i++) mostrado = avanzar(mostrado, real)
    expect(mostrado.area).toBe('error')
    expect(mostrado.reglas).toBe('listo')
  })

  it('cambiar de PETAR reinicia la repetición', async () => {
    const { result, rerender } = renderHook(({ ptw }) => useSala(ptw, 10), { initialProps: { ptw: terminado } })
    await waitFor(() => expect(result.current).toEqual(todoListo))
    rerender({ ptw: { ...base, ptw_id: 'PTW-B' } })
    expect(result.current.nanda).not.toBe('listo')
  })
})
