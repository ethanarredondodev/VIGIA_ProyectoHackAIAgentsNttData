import { fireEvent, screen, waitFor } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import PedidoActividad from '../componentes/PedidoActividad'
import { ACTIVIDADES_BASE, actividadConfirmada, armarSolicitud, laborValida, OTRA, turnoSegunHora, type PerfilTrabajador } from '../pedido'
import type { Interpretacion } from '../tipos'
import { renderizar } from './render'
import { servidor } from './setup'

const perfil: PerfilTrabajador = { trabajador_id: 'T-001', altitud_msnm: 4210, tipo_mineria: 'subterranea', empleador: 'contratista' }
const interpAlta: Interpretacion = {
  actividad: ACTIVIDADES_BASE[0],
  labor: 'NV-3820 TJ-12',
  tipo_labor: 'frente_avance',
  confianza: 'alta',
  alternativas: ACTIVIDADES_BASE.slice(1),
}
const interpBaja: Interpretacion = { actividad: null, labor: null, tipo_labor: null, confianza: 'baja', alternativas: ACTIVIDADES_BASE }

describe('reglas del pedido', () => {
  it('confirma sola la actividad solo con confianza alta', () => {
    expect(actividadConfirmada({ ...interpAlta }, null)?.id).toBe('ACT-01')
    expect(actividadConfirmada({ ...interpAlta, confianza: 'media' }, null)).toBeNull()
    expect(actividadConfirmada({ ...interpAlta, confianza: 'baja' }, ACTIVIDADES_BASE[2])?.id).toBe('ACT-03')
  })

  it('la solicitud lleva la actividad de la tabla y no el texto libre', () => {
    expect(armarSolicitud({ actividad: ACTIVIDADES_BASE[0], texto: 'voy a perforar', labor: 'NV-3820 TJ-12', turno: 'noche', interp: interpAlta, perfil })).toEqual({
      ...perfil,
      tarea: 'Perforación de frente',
      labor: 'NV-3820 TJ-12',
      turno: 'noche',
      actividad_id: 'ACT-01',
      interpretacion: { actividad_id: 'ACT-01', confianza: 'alta' },
    })
    expect(armarSolicitud({ actividad: ACTIVIDADES_BASE[0], texto: 'x', labor: 'L', turno: 'dia', perfil })).not.toHaveProperty('actividad_id')
    expect(armarSolicitud({ actividad: OTRA, texto: ' limpiar cunetas ', labor: 'L', turno: 'dia', interp: interpBaja, perfil })).toMatchObject({
      tarea: 'limpiar cunetas',
      actividad_id: 'otro',
    })
  })

  it('valida la labor contra la lista, o acepta cualquier texto si no hay lista', () => {
    const labores = [{ labor: 'NV-3820 TJ-12', tipo_labor: 'tajeo' }]
    expect(laborValida('NV-3820 TJ-12', labores)).toBe(true)
    expect(laborValida('TJ-99', labores)).toBe(false)
    expect(laborValida('NV-9999 GA-01', undefined)).toBe(true)
  })

  it('elige el turno según la hora', () => {
    expect(turnoSegunHora(new Date('2026-10-17T23:00:00'))).toBe('noche')
    expect(turnoSegunHora(new Date('2026-10-17T10:00:00'))).toBe('dia')
  })
})

function capturarSolicitud() {
  const cuerpos: Record<string, unknown>[] = []
  servidor.use(
    http.post('*/ptw/solicitud', async ({ request }) => {
      cuerpos.push((await request.json()) as Record<string, unknown>)
      return HttpResponse.json({ ptw_id: 'PTW-TEST', estado: 'procesando' }, { status: 201 })
    }),
  )
  return cuerpos
}

const escribir = (texto: string) => fireEvent.change(screen.getByRole('textbox', { name: '¿Qué actividad vas a realizar?' }), { target: { value: texto } })
const boton = () => screen.getByRole('button', { name: 'Pedir permiso' }) as HTMLButtonElement

describe('pedido de actividad en texto libre', () => {
  it('entiende la actividad y la solicitud no lleva el texto libre', async () => {
    const cuerpos = capturarSolicitud()
    const onCreado = vi.fn()
    renderizar(<PedidoActividad perfil={perfil} onCreado={onCreado} />)
    escribir('voy a perforar el frente del TJ-12')
    expect(await screen.findByText('Vigía entendió', {}, { timeout: 3000 })).toBeTruthy()
    expect(screen.getByText('Perforación de frente')).toBeTruthy()
    expect(screen.getByText('NV-3820 TJ-12')).toBeTruthy()
    fireEvent.click(boton())
    await waitFor(() => expect(onCreado).toHaveBeenCalledWith('PTW-TEST'))
    expect(cuerpos[0]).toMatchObject({ actividad_id: 'ACT-01', tarea: 'Perforación de frente', labor: 'NV-3820 TJ-12' })
    expect(cuerpos[0]).not.toHaveProperty('tipo_tarea')
    expect(JSON.stringify(cuerpos[0])).not.toContain('voy a perforar')
  })

  it('con confianza baja hay que tocar una actividad', async () => {
    renderizar(<PedidoActividad perfil={perfil} onCreado={vi.fn()} />)
    escribir('trabajo en la zona norte')
    expect(await screen.findByText('Elige la actividad', {}, { timeout: 3000 })).toBeTruthy()
    expect(boton().disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Desatado de rocas' }))
    fireEvent.change(screen.getByRole('combobox', { name: '¿En qué labor?' }), { target: { value: 'NV-3820 TJ-12' } })
    await waitFor(() => expect(boton().disabled).toBe(false))
  })

  it('si la interpretación falla, elige de la lista y no envía campos nuevos', async () => {
    servidor.use(http.post('*/tareas/interpretar', () => HttpResponse.json({ detail: 'caído' }, { status: 500 })))
    const cuerpos = capturarSolicitud()
    renderizar(<PedidoActividad perfil={perfil} onCreado={vi.fn()} />)
    escribir('voy a perforar el frente del TJ-12')
    expect(await screen.findByText('Elige la actividad', {}, { timeout: 3000 })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Perforación de frente' }))
    fireEvent.change(screen.getByRole('combobox', { name: '¿En qué labor?' }), { target: { value: 'NV-3820 TJ-12' } })
    await waitFor(() => expect(boton().disabled).toBe(false))
    fireEvent.click(boton())
    await waitFor(() => expect(cuerpos).toHaveLength(1))
    expect(cuerpos[0]).not.toHaveProperty('actividad_id')
    expect(cuerpos[0]).not.toHaveProperty('interpretacion')
  })

  it('backend antiguo: sin /actividades, /labores ni /tareas/interpretar', async () => {
    servidor.use(
      http.get('*/actividades', () => HttpResponse.json({ detail: 'Not Found' }, { status: 404 })),
      http.get('*/labores', () => HttpResponse.json({ detail: 'Not Found' }, { status: 404 })),
      http.post('*/tareas/interpretar', () => HttpResponse.json({ detail: 'Not Found' }, { status: 404 })),
    )
    const cuerpos = capturarSolicitud()
    renderizar(<PedidoActividad perfil={perfil} onCreado={vi.fn()} />)
    escribir('voy a perforar el frente del TJ-12')
    expect(await screen.findByText('Elige la actividad', {}, { timeout: 3000 })).toBeTruthy()
    for (const a of ACTIVIDADES_BASE) expect(screen.getByRole('button', { name: a.actividad })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Perforación de frente' }))
    fireEvent.change(screen.getByRole('combobox', { name: '¿En qué labor?' }), { target: { value: 'NV-3820 TJ-12' } })
    await waitFor(() => expect(boton().disabled).toBe(false))
    fireEvent.click(boton())
    await waitFor(() => expect(cuerpos).toHaveLength(1))
    expect(Object.keys(cuerpos[0]).sort()).toEqual(['altitud_msnm', 'empleador', 'labor', 'tarea', 'tipo_mineria', 'trabajador_id', 'turno'])
  })

  it('una respuesta vieja que llega tarde no pisa a la nueva', async () => {
    servidor.use(
      http.post('*/tareas/interpretar', async ({ request }) => {
        const { texto } = (await request.json()) as { texto: string }
        const desatar = texto.includes('desatar')
        await delay(desatar ? 50 : 1500)
        const actividad = desatar ? ACTIVIDADES_BASE[2] : ACTIVIDADES_BASE[0]
        return HttpResponse.json({ ...interpAlta, actividad, alternativas: ACTIVIDADES_BASE.filter((a) => a !== actividad) })
      }),
    )
    renderizar(<PedidoActividad perfil={perfil} onCreado={vi.fn()} />)
    escribir('voy a perforar')
    await new Promise((r) => setTimeout(r, 800))
    escribir('voy a desatar la corona')
    expect(await screen.findByText('Vigía entendió', {}, { timeout: 3000 })).toBeTruthy()
    await new Promise((r) => setTimeout(r, 1200))
    expect(screen.getAllByText('Desatado de rocas').length).toBeGreaterThan(0)
    expect(screen.queryByText('Perforación de frente', { selector: 'dd' })).toBeNull()
  })

  it('una labor que no existe no habilita el pedido', async () => {
    renderizar(<PedidoActividad perfil={perfil} onCreado={vi.fn()} />)
    escribir('voy a perforar el frente del TJ-99')
    expect(await screen.findByText('Vigía entendió', {}, { timeout: 3000 })).toBeTruthy()
    fireEvent.change(screen.getByRole('combobox', { name: '¿En qué labor?' }), { target: { value: 'TJ-99' } })
    await new Promise((r) => setTimeout(r, 100))
    expect(boton().disabled).toBe(true)
  })
})
