import { fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { USUARIOS } from '../sesion'
import { renderizar } from './render'

const [JUAN, ROSA, ADMIN] = USUARIOS

describe('ingreso por usuario', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    sessionStorage.clear()
  })

  it('sin usuario muestra "¿Quién eres?"', async () => {
    renderizar(<App />, '/supervisor', null)
    expect(await screen.findByRole('heading', { name: '¿Quién eres?' })).toBeTruthy()
  })

  it('el trabajador no puede abrir el supervisor', async () => {
    renderizar(<App />, '/supervisor', JUAN)
    expect(await screen.findByText('Tu gemelo hoy')).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Supervisor' })).toBeNull()
  })

  it('el supervisor no ve el admin', async () => {
    renderizar(<App />, '/admin', ROSA)
    expect(await screen.findByRole('heading', { name: 'Bandeja' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Admin' })).toBeNull()
  })

  it('el admin ve las tres vistas y /monitor lo lleva a /admin', async () => {
    renderizar(<App />, '/monitor', ADMIN)
    const admin = await screen.findByRole('link', { name: 'Admin' })
    expect(admin.getAttribute('aria-current')).toBe('page')
    expect(screen.getByRole('link', { name: 'Trabajador' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Supervisor' })).toBeTruthy()
  })

  it('elegir un usuario entra a su vista y "Cambiar de usuario" vuelve al inicio', async () => {
    renderizar(<App />, '/', null)
    fireEvent.click(await screen.findByRole('button', { name: /Juan Mamani/ }))
    expect(await screen.findByText('Tu gemelo hoy')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Cambiar de usuario' }))
    expect(await screen.findByRole('heading', { name: '¿Quién eres?' })).toBeTruthy()
  })

  it('al entrar conserva los parámetros de la demo', async () => {
    renderizar(<App />, '/?escenario=verde', null)
    fireEvent.click(await screen.findByRole('button', { name: /Ing\. Rosa Quispe/ }))
    expect(await screen.findByRole('heading', { name: 'Bandeja' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /Vigía/ }).getAttribute('href')).toBe('/supervisor?escenario=verde')
  })

  it('funciona si sessionStorage falla', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })
    renderizar(<App />, '/', null)
    fireEvent.click(await screen.findByRole('button', { name: /Juan Mamani/ }))
    expect(await screen.findByText('Tu gemelo hoy')).toBeTruthy()
  })
})
