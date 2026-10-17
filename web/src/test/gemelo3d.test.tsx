import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import AvatarGemelo3D from '../componentes/AvatarGemelo3D'
import { TRABAJADORES } from '../mocks/datos'
import type { Avatar } from '../tipos'
import { parametrosMinero } from '../tres/parametros'
import { renderizar } from './render'
import { servidor } from './setup'

const banderas = vi.hoisted(() => ({ soporte: false }))
vi.mock('../tres/soporte', () => ({ soporta3D: () => banderas.soporte }))
vi.mock('../tres/escena', () => ({
  crearEscena: () => {
    throw new Error('sin contexto WebGL')
  },
}))

const juan = TRABAJADORES['T-001']
const CLINICO = 'Hipoxemia crónica leve'

describe('parámetros del minero 3D', () => {
  it('son deterministas para el mismo trabajador', () => {
    expect(parametrosMinero(juan)).toEqual(parametrosMinero(juan))
  })

  it('cambian entre trabajadores distintos', () => {
    const distintos = new Set(Object.values(TRABAJADORES).map((a) => JSON.stringify(parametrosMinero(a))))
    expect(distintos.size).toBe(Object.keys(TRABAJADORES).length)
  })

  it('con energía 35 la lámpara baja y los párpados caen', () => {
    expect(parametrosMinero({ ...juan, estado_visual: { ...juan.estado_visual, energia: 35 } })).toMatchObject({ energia: 0.35, parpados: true })
    expect(parametrosMinero({ ...juan, estado_visual: { ...juan.estado_visual, energia: 85 } })).toMatchObject({ energia: 0.85, parpados: false })
  })

  it('solo salen del estado visual, aunque el avatar traiga datos clínicos', () => {
    expect(Object.keys(parametrosMinero({ ...juan, diagnostico: 'X' } as Avatar)).sort()).toEqual([
      'casco', 'colorAnillo', 'energia', 'parpados', 'peinado', 'pelo', 'piel', 'pielSombra', 'ropa',
    ])
  })

  it('jsdom no tiene WebGL', async () => {
    const real = await vi.importActual<typeof import('../tres/soporte')>('../tres/soporte')
    expect(real.soporta3D()).toBe(false)
  })
})

describe('gemelo 3D en la vista del trabajador', () => {
  it('sin WebGL muestra el gemelo 2D sin datos clínicos', async () => {
    banderas.soporte = false
    servidor.use(
      http.get('*/trabajadores/:id/avatar', () =>
        HttpResponse.json({ ...juan, diagnostico: CLINICO, estado_visual: { ...juan.estado_visual, diagnostico: CLINICO } }),
      ),
    )
    const { container } = renderizar(<AvatarGemelo3D trabajadorId="T-001" />)
    expect(await screen.findByRole('img', { name: /Juan Mamani: Apto con observaciones/ })).toBeTruthy()
    expect(container.innerHTML).not.toContain(CLINICO)
  })

  it('si WebGL falla al crear la escena, muestra el 2D', async () => {
    banderas.soporte = true
    renderizar(<AvatarGemelo3D trabajadorId="T-001" />)
    expect(await screen.findByRole('img', { name: /Juan Mamani: Apto con observaciones/ })).toBeTruthy()
    expect(document.querySelector('canvas')).toBeNull()
  })

  it('si el archivo del 3D no descarga, la vista del trabajador sigue en pie con el 2D', async () => {
    vi.resetModules()
    vi.doMock('../componentes/AvatarGemelo3D', () => {
      throw new Error('Failed to fetch dynamically imported module')
    })
    const { default: Trabajador } = await import('../vistas/Trabajador')
    const { renderizar: renderizarDeNuevo } = await import('./render')
    const { USUARIOS } = await import('../sesion')
    renderizarDeNuevo(<Trabajador />, '/trabajador', USUARIOS[0])
    expect(await screen.findByRole('heading', { name: '¿Qué actividad vas a realizar?' })).toBeTruthy()
    await new Promise((r) => setTimeout(r, 300))
    expect(screen.getByRole('heading', { name: '¿Qué actividad vas a realizar?' })).toBeTruthy()
    expect(screen.getByRole('img', { name: /Juan Mamani/ })).toBeTruthy()
    vi.doUnmock('../componentes/AvatarGemelo3D')
  })
})
