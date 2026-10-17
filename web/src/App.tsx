import { useState, type ReactNode } from 'react'
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { INICIO, puedeVer, useSesion } from './sesion'
import Ingreso from './vistas/Ingreso'
import Admin from './vistas/Admin'
import Supervisor from './vistas/Supervisor'
import Trabajador from './vistas/Trabajador'

function Logo() {
  return (
    <svg viewBox="0 0 64 64" className="size-9" aria-hidden="true">
      <path d="M11 41c0-14 9.4-25 21-25s21 11 21 25z" fill="#1F4E9C" />
      <path d="M29.5 16.6h5v8.4h-5z" fill="#163A78" />
      <rect x="5" y="39" width="54" height="8" rx="4" fill="#1F4E9C" />
      <circle cx="32" cy="30" r="12" fill="#FFD45C" opacity=".35" />
      <circle cx="32" cy="30" r="6.5" fill="#FFF3C4" stroke="#163A78" strokeWidth="2.5" />
    </svg>
  )
}

function BotonTema() {
  const [oscuro, setOscuro] = useState(() => document.documentElement.classList.contains('dark'))
  const cambiar = () => {
    document.documentElement.classList.toggle('dark', !oscuro)
    try {
      localStorage.setItem('vigia:tema', oscuro ? 'claro' : 'oscuro')
    } catch {
      /* el tema vuelve a seguir al sistema en la próxima visita */
    }
    setOscuro(!oscuro)
  }
  return (
    <button
      type="button"
      onClick={cambiar}
      aria-pressed={oscuro}
      className="flex min-h-11 items-center gap-2 rounded-md px-2.5 text-tinta-2 hover:bg-superficie-2 hover:text-tinta"
    >
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z" />
      </svg>
      <span className="sr-only md:not-sr-only">Modo oscuro</span>
    </button>
  )
}

const VISTAS = [
  { ruta: '/trabajador', texto: 'Trabajador' },
  { ruta: '/supervisor', texto: 'Supervisor' },
  { ruta: '/admin', texto: 'Admin' },
]

export default function App() {
  const { search } = useLocation()
  const navigate = useNavigate()
  const { usuario, salir } = useSesion()
  const inicio = usuario ? INICIO[usuario.rol] : '/'
  const protegida = (ruta: string, vista: ReactNode) =>
    usuario && puedeVer(usuario.rol, ruta) ? vista : <Navigate to={{ pathname: inicio, search }} replace />

  return (
    <div className="min-h-dvh">
      <header className="border-b border-linea bg-superficie">
        <div className="mx-auto flex max-w-[110rem] flex-wrap items-center gap-x-2 px-4 py-1.5 sm:flex-nowrap sm:gap-4">
          <Link to={{ pathname: inicio, search }} className="flex items-center gap-2 rounded-md pr-1">
            <Logo />
            <span className="font-cond text-2xl font-bold tracking-tight">Vigía</span>
          </Link>
          {usuario?.rol === 'admin' && (
            <nav aria-label="Vistas" className="order-last flex basis-full gap-1 sm:order-none sm:flex-1 sm:basis-auto sm:gap-2">
              {VISTAS.map((v) => (
                <NavLink
                  key={v.ruta}
                  to={{ pathname: v.ruta, search }}
                  className={({ isActive }) =>
                    `flex min-h-11 flex-1 items-center justify-center rounded-md px-2 text-[15px] font-semibold sm:flex-none sm:px-3 ${
                      isActive ? 'bg-superficie-2 text-tinta shadow-[inset_0_-3px_0_var(--azurita)]' : 'text-tinta-2 hover:text-tinta'
                    }`
                  }
                >
                  {v.texto}
                </NavLink>
              ))}
            </nav>
          )}
          <div className="ml-auto flex items-center gap-1 sm:gap-2">
            {usuario && (
              <>
                <span className="hidden text-[15px] font-semibold md:inline">{usuario.nombre}</span>
                <button
                  type="button"
                  onClick={() => {
                    salir()
                    navigate({ pathname: '/', search })
                  }}
                  className="min-h-11 rounded-md px-2.5 text-[15px] text-tinta-2 hover:bg-superficie-2 hover:text-tinta"
                >
                  Cambiar de usuario
                </button>
              </>
            )}
            {import.meta.env.VITE_USE_MOCKS === 'true' && <span className="hidden text-sm text-tinta-2 lg:inline">Datos simulados</span>}
            <BotonTema />
          </div>
        </div>
      </header>
      {!usuario ? (
        <Ingreso />
      ) : (
        <Routes>
          <Route path="/" element={<Navigate to={{ pathname: inicio, search }} replace />} />
          <Route path="/trabajador" element={protegida('/trabajador', <Trabajador />)} />
          <Route path="/supervisor" element={protegida('/supervisor', <Supervisor />)} />
          <Route path="/admin" element={protegida('/admin', <Admin />)} />
          <Route path="/monitor" element={<Navigate to={{ pathname: '/admin', search }} replace />} />
          <Route path="*" element={<Navigate to={{ pathname: inicio, search }} replace />} />
        </Routes>
      )}
    </div>
  )
}
