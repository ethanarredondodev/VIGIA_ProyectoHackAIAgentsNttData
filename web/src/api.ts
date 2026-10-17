import { useQuery } from '@tanstack/react-query'
import type {
  Actividad,
  Avatar,
  ConsultaGemelo,
  EstadoPtw,
  Firma,
  Interpretacion,
  ItemBandeja,
  Labor,
  Ptw,
  RespuestaSolicitud,
  Resultado,
  Solicitud,
} from './tipos'

export const API = import.meta.env.VITE_API_URL ?? ''

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API || window.location.origin}${ruta}`, {
    ...init,
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) throw new Error(`La API respondió ${res.status} en ${ruta}`)
  return res.json()
}

const enviar = (cuerpo: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(cuerpo) })

// Privacidad: aunque el backend enviara algo más, del gemelo solo pasan estos campos.
function limpiarGemelo(c: ConsultaGemelo): ConsultaGemelo {
  if (!c.data) return { estado: c.estado }
  const { trabajador_id, apto_para_tarea, motivo_visible, diagnostico } = c.data
  return {
    estado: c.estado,
    data: { trabajador_id, apto_para_tarea, motivo_visible, diagnostico: null },
    diagnostico_descartado: diagnostico != null,
    evidencia: c.evidencia ?? null,
  }
}

function limpiarAvatar(a: Avatar): Avatar {
  const e = a.estado_visual
  return {
    trabajador_id: a.trabajador_id,
    nombre: a.nombre,
    cargo: a.cargo,
    empresa: a.empresa,
    empleador: a.empleador,
    seed: a.seed,
    color_casco: a.color_casco,
    estado_visual: {
      apto_para_tarea: e.apto_para_tarea,
      motivo_visible: e.motivo_visible,
      energia: e.energia,
      dia_rotacion: e.dia_rotacion,
      total_rotacion: e.total_rotacion,
      exposicion_nivel: e.exposicion_nivel,
      historial_energia: e.historial_energia,
    },
  }
}

const limpiarPtw = (ptw: Ptw): Ptw => ({ ...ptw, consultas: { ...ptw.consultas, gemelo: limpiarGemelo(ptw.consultas.gemelo) } })

export const crearSolicitud = (s: Solicitud) => pedir<RespuestaSolicitud>('/ptw/solicitud', enviar(s))

export const obtenerPtw = async (id: string) => limpiarPtw(await pedir<Ptw>(`/ptw/${encodeURIComponent(id)}`))

export const listarPtw = async () => (await pedir<Ptw[]>('/ptw')).map(limpiarPtw)

export const obtenerActividades = () => pedir<Actividad[]>('/actividades')

export const obtenerLabores = () => pedir<Labor[]>('/labores')

export const interpretarTarea = (texto: string) => pedir<Interpretacion>('/tareas/interpretar', enviar({ texto }))

export const obtenerBandeja = () => pedir<ItemBandeja[]>('/ptw/bandeja')

export const firmar = (id: string, f: Firma) => pedir<unknown>(`/ptw/${encodeURIComponent(id)}/firma`, enviar(f))

export const iniciar = (id: string) => pedir<unknown>(`/ptw/${encodeURIComponent(id)}/inicio`, { method: 'POST' })

export const reportar = (id: string, r: Resultado) =>
  pedir<unknown>(`/ptw/${encodeURIComponent(id)}/resultado`, enviar(r))

export const obtenerAvatar = async (id: string) =>
  limpiarAvatar(await pedir<Avatar>(`/trabajadores/${encodeURIComponent(id)}/avatar`))

// El trabajador espera la firma del supervisor, así que también se sigue consultando en revisión.
const EN_CURSO: EstadoPtw[] = ['procesando', 'en_revision']

export const usePtw = (id: string | null | undefined, seguir = true) =>
  useQuery({
    queryKey: ['ptw', id],
    queryFn: () => obtenerPtw(id!),
    enabled: !!id,
    refetchInterval: (q) => (seguir && q.state.data && EN_CURSO.includes(q.state.data.estado) ? 2000 : false),
  })

export const useBandeja = () =>
  useQuery({ queryKey: ['bandeja'], queryFn: obtenerBandeja, refetchInterval: 4000 })

export const usePtwLista = () => useQuery({ queryKey: ['ptw-lista'], queryFn: listarPtw, refetchInterval: 4000 })

export const useActividades = () =>
  useQuery({ queryKey: ['actividades'], queryFn: obtenerActividades, staleTime: Infinity, retry: false })

export const useLabores = () => useQuery({ queryKey: ['labores'], queryFn: obtenerLabores, staleTime: Infinity, retry: false })

export const useAvatar = (id: string | undefined) =>
  useQuery({ queryKey: ['avatar', id], queryFn: () => obtenerAvatar(id!), enabled: !!id, staleTime: 30_000 })
