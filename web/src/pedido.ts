import type { Actividad, Interpretacion, Labor, Solicitud, Turno } from './tipos'

// Las filas con que arranca la tabla de actividades: una por cada tipo de tarea que Vigía conoce.
// Se usan cuando el backend todavía no ofrece GET /actividades.
export const ACTIVIDADES_BASE: Actividad[] = [
  { id: 'ACT-01', actividad: 'Perforación', tipo_tarea: 'perforacion' },
  { id: 'ACT-02', actividad: 'Voladura', tipo_tarea: 'voladura' },
  { id: 'ACT-03', actividad: 'Desatado de rocas', tipo_tarea: 'desatado' },
  { id: 'ACT-04', actividad: 'Sostenimiento con pernos y malla', tipo_tarea: 'sostenimiento' },
  { id: 'ACT-05', actividad: 'Carguío y limpieza', tipo_tarea: 'carguio' },
  { id: 'ACT-06', actividad: 'Acarreo de mineral', tipo_tarea: 'acarreo' },
  { id: 'ACT-07', actividad: 'Mantenimiento de equipos', tipo_tarea: 'mantenimiento' },
  { id: 'ACT-08', actividad: 'Izaje con winche', tipo_tarea: 'izaje' },
  { id: 'ACT-09', actividad: 'Trabajo en altura', tipo_tarea: 'trabajo_en_altura' },
  { id: 'ACT-10', actividad: 'Trabajo en espacio confinado', tipo_tarea: 'espacio_confinado' },
  { id: 'ACT-11', actividad: 'Soldadura y oxicorte', tipo_tarea: 'trabajo_en_caliente' },
]

// Una actividad que no está en la tabla: siempre va al supervisor.
export const OTRA: Actividad = { id: 'otro', actividad: 'Otra actividad', tipo_tarea: 'otro' }

export type PerfilTrabajador = Pick<Solicitud, 'trabajador_id' | 'altitud_msnm' | 'tipo_mineria' | 'empleador'>

// Con confianza alta, la tarjeta "Vigía entendió" a la vista cuenta como confirmación; si no, hay que tocar una actividad.
export const actividadConfirmada = (interp: Interpretacion | undefined, elegida: Actividad | null) =>
  elegida ?? (interp?.confianza === 'alta' ? interp.actividad : null)

export const laborValida = (labor: string, labores: Labor[] | undefined) => {
  const valor = labor.trim().toUpperCase()
  return labores ? labores.some((l) => l.labor.toUpperCase() === valor) : valor.length >= 2
}

export function turnoSegunHora(fecha = new Date()): Turno {
  const hora = fecha.getHours()
  return hora >= 7 && hora < 19 ? 'dia' : 'noche'
}

// El texto libre solo sirve para interpretar: viaja únicamente con "Otra actividad", donde es la única descripción.
// actividad_id e interpretacion van solo si el backend interpretó, así un backend sin ese contrato no responde 422.
export function armarSolicitud(p: {
  actividad: Actividad
  texto: string
  labor: string
  turno: Turno
  interp?: Interpretacion
  perfil: PerfilTrabajador
}): Solicitud {
  const solicitud: Solicitud = {
    ...p.perfil,
    tarea: p.actividad.id === OTRA.id ? p.texto.trim() : p.actividad.actividad,
    labor: p.labor.trim().toUpperCase(),
    turno: p.turno,
  }
  if (!p.interp) return solicitud
  return {
    ...solicitud,
    actividad_id: p.actividad.id,
    interpretacion: { actividad_id: p.interp.actividad?.id ?? null, confianza: p.interp.confianza },
  }
}
