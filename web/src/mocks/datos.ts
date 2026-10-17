import { ACTIVIDADES_BASE } from '../pedido'
import type { Aptitud, Avatar, Empleador, EstadoVisual, Labor, Resultado, Solicitud } from '../tipos'
import { LABORES_BD, SOLICITUDES_BD, TRABAJADORES_BD } from './bd'

export type Escenario = 'verde' | 'ambar' | 'rojo'

export const normalizar = (texto: string) =>
  texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()

// Mismas palabras clave y mismo orden que contracts/vocabulario.py: lo más específico primero
// ("carguío de taladros" es voladura, no perforación). En el backend real vivirán en la hoja de actividades.
const SINONIMOS: Record<string, string[]> = {
  voladura: ['voladura', 'disparo', 'explosivo', 'carguio de taladros'],
  perforacion: ['perfor', 'taladr', 'jumbo', 'jackleg'],
  desatado: ['desatado', 'desatar'],
  sostenimiento: ['sostenimiento', 'shotcrete', 'perno', 'malla', 'cimbra', 'enmaderado'],
  carguio: ['carguio', 'limpieza', 'scoop', 'pala'],
  acarreo: ['acarreo', 'transporte', 'volquete', 'camion'],
  izaje: ['izaje', 'winche', 'jaula'],
  trabajo_en_altura: ['altura', 'andamio'],
  espacio_confinado: ['confinado', 'tolva', 'tanque'],
  trabajo_en_caliente: ['soldadura', 'oxicorte', 'caliente'],
  mantenimiento: ['mantenimiento', 'reparacion'],
}

export const ACTIVIDADES = Object.keys(SINONIMOS).map((tipo) => ({
  ...ACTIVIDADES_BASE.find((a) => a.tipo_tarea === tipo)!,
  sinonimos: SINONIMOS[tipo],
}))

export function clasificarTarea(tarea: string): string {
  const texto = normalizar(tarea)
  return ACTIVIDADES.find((a) => a.sinonimos.some((s) => texto.includes(s)))?.tipo_tarea ?? 'otro'
}

const PREFIJOS: Record<string, string> = {
  TJ: 'tajeo', GA: 'galeria', GL: 'galeria', RP: 'rampa', CH: 'chimenea', XC: 'crucero', CX: 'crucero', BC: 'banco', TA: 'banco',
}

export function clasificarLabor(tarea: string, labor: string): string {
  if (normalizar(tarea).includes('frente')) return 'frente_avance'
  for (const [, prefijo] of labor.toUpperCase().matchAll(/\b([A-Z]{2})-/g)) if (PREFIJOS[prefijo]) return PREFIJOS[prefijo]
  return 'otro'
}

// Estado visual inventado y no clínico, coherente con lo que el gemelo responde en cada caso de la base de datos.
interface Gemelo {
  apto_para_tarea: Aptitud
  motivo_visible: string
  dia_rotacion: number
  exposicion_nivel: EstadoVisual['exposicion_nivel']
  historial: number[]
}

const SIN_OBSERVACIONES = 'Sin observaciones para la tarea'
const curva = (desde: number, hasta: number) => Array.from({ length: 14 }, (_, i) => Math.round(desde + ((hasta - desde) * i) / 13))
const apto = (dia_rotacion: number, exposicion_nivel: Gemelo['exposicion_nivel'], historial: number[]): Gemelo => ({
  apto_para_tarea: 'apto', motivo_visible: SIN_OBSERVACIONES, dia_rotacion, exposicion_nivel, historial,
})

export const GEMELOS: Record<string, Gemelo> = {
  'T-001': {
    apto_para_tarea: 'apto_con_observaciones',
    motivo_visible: 'Descanso por debajo del umbral recomendado; Tramo final de la rotación; Requiere protección respiratoria reforzada',
    dia_rotacion: 12,
    exposicion_nivel: 'alta',
    historial: [82, 80, 78, 75, 71, 68, 64, 60, 56, 52, 47, 43, 39, 35],
  },
  'T-001-D3': apto(3, 'baja', [70, 74, 77, 80, 82, 84, 86, 87, 86, 88, 86, 84, 86, 85]),
  'T-002': apto(5, 'baja', curva(78, 82)),
  'T-003': {
    apto_para_tarea: 'no_apto', motivo_visible: 'Descanso insuficiente para tareas de alto riesgo hoy',
    dia_rotacion: 13, exposicion_nivel: 'alta', historial: curva(70, 28),
  },
  'T-011': {
    apto_para_tarea: 'no_apto', motivo_visible: 'Restricción médica vigente para esta tarea: consultar a salud ocupacional',
    dia_rotacion: 6, exposicion_nivel: 'media', historial: curva(76, 74),
  },
  'T-101': apto(4, 'media', curva(80, 78)),
  'T-102': apto(7, 'baja', curva(75, 72)),
  'T-103': apto(9, 'media', curva(72, 66)),
  'T-104': apto(2, 'baja', curva(84, 86)),
  'T-105': {
    apto_para_tarea: 'apto_con_observaciones', motivo_visible: 'Tramo final de la rotación',
    dia_rotacion: 13, exposicion_nivel: 'media', historial: curva(74, 46),
  },
  'T-106': apto(8, 'media', curva(77, 70)),
}

// Juan descansado (T-001-D3) es la misma persona que Juan (T-001) en otro momento de su rotación.
export const gemeloDe = (trabajadorId: string, escenario: Escenario) =>
  GEMELOS[trabajadorId === 'T-001' && escenario !== 'ambar' ? 'T-001-D3' : trabajadorId] ?? apto(1, 'baja', curva(80, 80))

export const estadoVisual = (g: Gemelo): EstadoVisual => ({
  apto_para_tarea: g.apto_para_tarea,
  motivo_visible: g.motivo_visible,
  energia: g.historial[g.historial.length - 1],
  dia_rotacion: g.dia_rotacion,
  total_rotacion: 14,
  exposicion_nivel: g.exposicion_nivel,
  historial_energia: g.historial,
})

const CASCO: Record<Empleador, string> = { titular: '#EDEFEA', contratista: '#EE7D2B' }

export const TRABAJADORES: Record<string, Avatar> = Object.fromEntries(
  TRABAJADORES_BD.map((t) => [
    t.trabajador_id,
    {
      trabajador_id: t.trabajador_id,
      nombre: `${t.nombres} ${t.apellidos}`,
      cargo: t.cargo,
      empresa: t.empresa,
      empleador: t.empleador as Empleador,
      seed: normalizar(`${t.nombres}-${t.apellidos}`).replaceAll(' ', '-'),
      color_casco: CASCO[t.empleador as Empleador],
      estado_visual: estadoVisual(gemeloDe(t.trabajador_id, 'ambar')),
    },
  ]),
)

export const LABORES: Labor[] = LABORES_BD.map((l) => ({ labor: l.labor, tipo_labor: clasificarLabor('', l.labor) }))

// Tareas ya cerradas con su reporte, para la pestaña Reportes del supervisor.
const CIERRES: { trabajador_id: string; labor: string; resultado: Resultado }[] = [
  {
    trabajador_id: 'T-001-D3', labor: 'NV-3820 GA-07',
    resultado: { resultado: 'incidente', controles_cumplidos: true, observacion: 'Cayó roca menor del hastial; sin lesionados; se reforzó el desatado.' },
  },
  {
    trabajador_id: 'T-002', labor: 'TA-FASE4 BC-3400',
    resultado: { resultado: 'casi_incidente', controles_cumplidos: true, observacion: 'Un volquete invadió el carril en la rampa; se detuvo a tiempo.' },
  },
  {
    trabajador_id: 'T-104', labor: 'NV-4620 GA-24',
    resultado: { resultado: 'sin_novedad', controles_cumplidos: true, observacion: 'Sin observaciones.' },
  },
]

// El caso 1 (Juan, TJ-12, ámbar) es la demo en vivo; el resto llega ya resuelto al abrir la demo.
export const SEMILLAS: { ptw_id: string; solicitud: Solicitud; hace_min: number; resultado?: Resultado }[] = SOLICITUDES_BD.slice(1).map(
  (caso, i) => {
    const solicitud = caso.solicitud as Solicitud
    const cierre = CIERRES.find((c) => c.trabajador_id === solicitud.trabajador_id && c.labor === solicitud.labor)
    return {
      ptw_id: `PTW-SEED-${String(i + 2).padStart(2, '0')}`,
      solicitud,
      hace_min: cierre ? 240 + i * 15 : 6 + i * 7,
      resultado: cierre?.resultado,
    }
  },
)

const VENCE = '2026-11-16T00:00:00+00:00'

export const FICHAS_NANDA = [
  { id: 'vigia-incidentes', capabilities: ['incidentes.similares', 'incidentes.registrar'], firma: 'valida' as const,
    emisores: ['vigia-sso'], credencial_vence: VENCE, motivo: null },
  { id: 'vigia-area', capabilities: ['area.condiciones'], firma: 'valida' as const,
    emisores: ['vigia-sso'], credencial_vence: VENCE, motivo: null },
  { id: 'vigia-gemelo', capabilities: ['gemelo.aptitud'], firma: 'valida' as const,
    emisores: ['vigia-salud-ocupacional', 'vigia-sso'], credencial_vence: '2026-10-24T00:00:00+00:00', motivo: null },
]

// Simulada: en el backend real cada agente firma su respuesta con la clave que certificó la autoridad.
export const EVIDENCIA_SIMULADA = {
  nonce: 'demo',
  sha256: '9f2c4e1b7a6d3c8e5f0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5a6',
  firma: 'simulada',
  clave_publica: 'simulada',
}
