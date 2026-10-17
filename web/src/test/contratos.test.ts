import { describe, expect, it, vi } from 'vitest'
import { crearSolicitud, interpretarTarea, listarPtw, obtenerActividades, obtenerPtw } from '../api'
import { ACTIVIDADES_BASE } from '../pedido'
import type { Solicitud } from '../tipos'

const SOLICITUD_JUAN: Solicitud = {
  tarea: 'perforación de frente',
  labor: 'NV-3820 TJ-12',
  turno: 'noche',
  trabajador_id: 'T-001',
  altitud_msnm: 4210,
  tipo_mineria: 'subterranea',
  empleador: 'contratista',
}

describe('contratos nuevos (simulados con los datos de la base de datos)', () => {
  it('lista las 11 actividades de la tabla', async () => {
    expect((await obtenerActividades()).map((a) => a.id)).toEqual(ACTIVIDADES_BASE.map((a) => a.id))
  })

  it('interpreta una perforación con su labor', async () => {
    const r = await interpretarTarea('voy a perforar el frente del TJ-12')
    expect(r.actividad?.tipo_tarea).toBe('perforacion')
    expect(r.labor).toBe('NV-3820 TJ-12')
    expect(r.confianza).toBe('alta')
  })

  it('sin coincidencia devuelve confianza baja y todas las actividades como alternativas', async () => {
    const r = await interpretarTarea('trabajo en la zona norte')
    expect(r.actividad).toBeNull()
    expect(r.confianza).toBe('baja')
    expect(r.alternativas).toHaveLength(11)
  })

  it('no devuelve una labor que no existe', async () => {
    expect((await interpretarTarea('perforar en TJ-99')).labor).toBeNull()
  })

  it('los casos guionados de la base de datos llegan al nivel esperado', async () => {
    // nivel_esperado de data/synthetic/solicitudes.json del backend
    const esperado = { 'PTW-SEED-02': 'verde', 'PTW-SEED-03': 'rojo', 'PTW-SEED-04': 'verde', 'PTW-SEED-05': 'rojo' }
    for (const [id, nivel] of Object.entries(esperado)) expect((await obtenerPtw(id)).propuesta?.nivel).toBe(nivel)
  })

  it('perforar con la actividad de la lista en GA-07 respeta la galería y sale verde', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    const { ptw_id } = await crearSolicitud({
      ...SOLICITUD_JUAN,
      tarea: ACTIVIDADES_BASE[0].actividad,
      labor: 'NV-3820 GA-07',
      turno: 'dia',
      trabajador_id: 'T-001-D3',
    })
    vi.setSystemTime(Date.now() + 10_000)
    expect((await obtenerPtw(ptw_id)).propuesta?.nivel).toBe('verde')
    vi.useRealTimers()
  })

  it('GET /ptw trae los cerrados con su resultado y el gemelo sin diagnóstico', async () => {
    const lista = await listarPtw()
    expect(lista.filter((p) => p.estado === 'cerrado').map((p) => p.resultado?.resultado).sort()).toEqual([
      'casi_incidente',
      'incidente',
      'sin_novedad',
    ])
    expect(JSON.stringify(lista)).not.toMatch(/"diagnostico":"/)
  })

  it('una solicitud con actividad "otro" exige supervisor', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    const { ptw_id } = await crearSolicitud({
      ...SOLICITUD_JUAN,
      actividad_id: 'otro',
      interpretacion: { actividad_id: null, confianza: 'baja' },
    })
    vi.setSystemTime(Date.now() + 10_000)
    const ptw = await obtenerPtw(ptw_id)
    expect(ptw.tipo_tarea).toBe('otro')
    expect(ptw.propuesta?.requiere_supervisor).toBe(true)
    vi.useRealTimers()
  })
})
