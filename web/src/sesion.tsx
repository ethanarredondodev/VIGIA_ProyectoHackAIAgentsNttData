import { createContext, useContext, useState, type ReactNode } from 'react'

export type Rol = 'trabajador' | 'supervisor' | 'admin'

export interface Usuario {
  id: string
  nombre: string
  rol: Rol
  trabajadorId?: string
}

// Usuarios de demo, sin contraseña: así lo decidió el usuario para el pitch.
export const USUARIOS: Usuario[] = [
  { id: 'juan', nombre: 'Juan Mamani', rol: 'trabajador', trabajadorId: 'T-001' },
  { id: 'rosa', nombre: 'Ing. Rosa Quispe', rol: 'supervisor' },
  { id: 'admin', nombre: 'Administración', rol: 'admin' },
]

export const INICIO: Record<Rol, string> = { trabajador: '/trabajador', supervisor: '/supervisor', admin: '/admin' }

export const puedeVer = (rol: Rol, ruta: string) => rol === 'admin' || ruta === INICIO[rol]

// Por pestaña: en la demo cada pestaña puede ser una persona distinta.
const CLAVE = 'vigia:usuario'

function leer(): Usuario | null {
  try {
    return USUARIOS.find((u) => u.id === sessionStorage.getItem(CLAVE)) ?? null
  } catch {
    return null
  }
}

interface Sesion {
  usuario: Usuario | null
  entrar: (id: string) => void
  salir: () => void
}

const Contexto = createContext<Sesion | null>(null)

export function SesionProvider({ children, inicial }: { children: ReactNode; inicial?: Usuario | null }) {
  const [usuario, setUsuario] = useState(() => (inicial !== undefined ? inicial : leer()))
  const entrar = (id: string) => {
    try {
      sessionStorage.setItem(CLAVE, id)
    } catch {
      /* sin almacenamiento la sesión vive solo en memoria */
    }
    setUsuario(USUARIOS.find((u) => u.id === id) ?? null)
  }
  const salir = () => {
    try {
      sessionStorage.removeItem(CLAVE)
    } catch {
      /* idem */
    }
    setUsuario(null)
  }
  return <Contexto.Provider value={{ usuario, entrar, salir }}>{children}</Contexto.Provider>
}

export const useSesion = () => useContext(Contexto)!
