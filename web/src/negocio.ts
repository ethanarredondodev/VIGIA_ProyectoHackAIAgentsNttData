import type { Aptitud, EstadoPtw, ItemBandeja, Nivel, Propuesta, ResultadoTarea, Turno } from './tipos'

// El supervisor solo recibe el documento cuando hay duda.
export function destinoSupervisor(p: Pick<Propuesta, 'nivel' | 'requiere_supervisor'>): 'revision' | 'aviso' | null {
  if (p.nivel === 'rojo') return 'aviso'
  if (p.nivel === 'ambar' || p.requiere_supervisor) return 'revision'
  return null
}

export function separarBandeja(items: ItemBandeja[]) {
  const visibles = items.filter((i) => destinoSupervisor(i) !== null)
  return {
    porRevisar: visibles.filter((i) => i.tipo === 'revision'),
    avisos: visibles.filter((i) => i.tipo === 'aviso'),
  }
}

export function textoDestino(p: Propuesta): string {
  if (p.nivel === 'rojo') return 'Tarea bloqueada. El supervisor solo recibe un aviso.'
  if (p.nivel === 'ambar') return 'Va a la bandeja del supervisor para firmar con controles.'
  if (p.requiere_supervisor) return 'Trabajo de alto riesgo: va a la bandeja del supervisor.'
  return 'PETAR emitido directo al trabajador.'
}

// Lo que ve el trabajador en su pantalla según el estado del PETAR.
export const TEXTO_TRABAJADOR: Record<EstadoPtw, string> = {
  procesando: 'Vigía revisa tu pedido',
  emitido: 'Tu permiso está listo',
  en_revision: 'Tu supervisor está revisando',
  bloqueado: 'Esta tarea está bloqueada',
  autorizado_con_controles: 'Tu permiso está listo',
  rechazado: 'Tu supervisor no la autorizó',
  en_ejecucion: 'Trabajo en curso',
  cerrado: 'Tarea cerrada con reporte',
}

export const TEXTO_NIVEL: Record<Nivel, string> = { verde: 'Verde', ambar: 'Ámbar', rojo: 'Rojo' }

export const CLASES_NIVEL: Record<Nivel, { relleno: string; texto: string; borde: string }> = {
  verde: { relleno: 'bg-verde text-sobre-verde', texto: 'text-verde-texto', borde: 'border-verde' },
  ambar: { relleno: 'bg-ambar text-sobre-ambar', texto: 'text-ambar-texto', borde: 'border-ambar' },
  rojo: { relleno: 'bg-rojo text-sobre-rojo', texto: 'text-rojo-texto', borde: 'border-rojo' },
}

export const NIVEL_DE_APTITUD: Record<Aptitud, Nivel> = {
  apto: 'verde',
  apto_con_observaciones: 'ambar',
  no_apto: 'rojo',
}

export const TEXTO_APTITUD: Record<Aptitud, string> = {
  apto: 'Apto',
  apto_con_observaciones: 'Apto con observaciones',
  no_apto: 'No apto',
}

export const TEXTO_DECISION: Record<Propuesta['decision'], string> = {
  autorizar: 'Autorizar',
  autorizar_con_controles: 'Autorizar con controles',
  reasignar: 'Reasignar',
}

export const TEXTO_ESTADO: Record<EstadoPtw, string> = {
  procesando: 'Procesando',
  emitido: 'PETAR emitido',
  en_revision: 'En revisión del supervisor',
  bloqueado: 'Tarea bloqueada',
  autorizado_con_controles: 'Autorizado con controles',
  rechazado: 'Rechazado por el supervisor',
  en_ejecucion: 'En ejecución',
  cerrado: 'Cerrado con reporte',
}

export const TEXTO_TURNO: Record<Turno, string> = { dia: 'Día', noche: 'Noche' }

export const NIVEL_DE_RESULTADO: Record<ResultadoTarea, Nivel> = {
  sin_novedad: 'verde',
  casi_incidente: 'ambar',
  incidente: 'rojo',
}

export const TEXTO_RESULTADO: Record<ResultadoTarea, string> = {
  sin_novedad: 'Sin novedad',
  casi_incidente: 'Casi incidente',
  incidente: 'Incidente',
}

const VENTILACION: Record<string, string> = {
  operativa: 'Operativa',
  deficiente: 'Deficiente',
  inoperativa: 'Detenida',
  natural: 'Natural',
}

export const textoVentilacion = (v: string) => VENTILACION[v] ?? v

export const capitalizar = (t: string) => t.charAt(0).toUpperCase() + t.slice(1)

export const textoClave = (clave: string) => capitalizar(clave.replaceAll('_', ' '))

const relativo = new Intl.RelativeTimeFormat('es-PE', { numeric: 'auto' })

export function haceCuanto(iso: string, ahora = Date.now()): string {
  const min = Math.round((new Date(iso).getTime() - ahora) / 60000)
  if (Math.abs(min) < 60) return relativo.format(min, 'minute')
  return relativo.format(Math.round(min / 60), 'hour')
}
