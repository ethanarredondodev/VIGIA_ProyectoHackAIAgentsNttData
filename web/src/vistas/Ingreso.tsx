import { useNavigate } from 'react-router-dom'
import { INICIO, USUARIOS, useSesion, type Rol } from '../sesion'

const QUE_HACE: Record<Rol, { rol: string; texto: string }> = {
  trabajador: { rol: 'Trabajador', texto: 'Pide su permiso de trabajo y recibe el resultado.' },
  supervisor: { rol: 'Supervisora', texto: 'Revisa los casos con duda, firma y lee los reportes.' },
  admin: { rol: 'Administración', texto: 'Ve en vivo cómo razona Vigía con cada solicitud.' },
}

export default function Ingreso() {
  const { entrar } = useSesion()
  const navigate = useNavigate()

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="font-cond text-4xl font-bold">¿Quién eres?</h1>
      <p className="mt-2 text-lg text-tinta-2">Elige con qué usuario entrar a la demo. No hace falta contraseña.</p>
      <ul className="mt-6 grid gap-3 sm:grid-cols-3">
        {USUARIOS.map((u) => (
          <li key={u.id}>
            <button
              type="button"
              onClick={() => {
                entrar(u.id)
                navigate(INICIO[u.rol])
              }}
              className="flex h-full min-h-32 w-full flex-col items-start gap-1 rounded-md border-2 border-linea bg-superficie p-4 text-left hover:border-azurita"
            >
              <span className="font-cond text-2xl font-bold leading-tight">{u.nombre}</span>
              <span className="font-semibold text-azurita">{QUE_HACE[u.rol].rol}</span>
              <span className="text-tinta-2">{QUE_HACE[u.rol].texto}</span>
            </button>
          </li>
        ))}
      </ul>
    </main>
  )
}
