// Contratos de la API del Agente PTW, escritos a mano. No cambiarlos sin acordarlo con el backend.

export type EstadoPtw =
  | 'procesando'
  | 'emitido'
  | 'en_revision'
  | 'bloqueado'
  | 'autorizado_con_controles'
  | 'rechazado'
  | 'en_ejecucion'
  | 'cerrado'
export type Nivel = 'verde' | 'ambar' | 'rojo'
export type Turno = 'dia' | 'noche'
export type TipoMineria = 'subterranea' | 'tajo_abierto'
export type Empleador = 'titular' | 'contratista'
export type Aptitud = 'apto' | 'apto_con_observaciones' | 'no_apto'
export type EstadoConsulta = 'pendiente' | 'ok' | 'error'
export type Decision = 'autorizar' | 'autorizar_con_controles' | 'reasignar'
export type AccionFirma = 'aceptar' | 'ajustar' | 'rechazar'
export type ResultadoTarea = 'sin_novedad' | 'casi_incidente' | 'incidente'
export type Confianza = 'alta' | 'media' | 'baja'

// Una fila de la tabla de actividades que la mina autoriza.
export interface Actividad {
  id: string
  actividad: string
  tipo_tarea: string
}

export interface Labor {
  labor: string
  tipo_labor: string
}

// Lo que entendió la IA de Vigía al comparar el texto del trabajador con la tabla de actividades.
export interface Interpretacion {
  actividad: Actividad | null
  labor: string | null
  tipo_labor: string | null
  confianza: Confianza
  alternativas: Actividad[]
}

export interface Solicitud {
  tarea: string
  labor: string
  turno: Turno
  trabajador_id: string
  altitud_msnm: number
  tipo_mineria: TipoMineria
  empleador: Empleador
  // El cliente nunca envía tipo_tarea: el servidor lo deriva de la tabla con actividad_id.
  actividad_id?: string | null
  interpretacion?: { actividad_id: string | null; confianza: Confianza }
}

export interface RespuestaSolicitud {
  ptw_id: string
  estado: 'procesando'
}

export interface CasoIncidente {
  id: string
  resumen_es: string
  riesgo_critico: string
  causa_probable: string
}

export interface DatosIncidentes {
  casos_similares: number
  patron: string
  riesgo_potencial_max: string
  casos: CasoIncidente[]
}

export interface DatosArea {
  labor: string
  co_ppm: number
  o2_pct: number
  ventilacion: string
  ruido_dBA: number
  ultimo_desatado_h: number
}

// Zona clínica: del gemelo solo sale la aptitud y su motivo visible.
export interface DatosGemelo {
  trabajador_id: string
  apto_para_tarea: Aptitud
  motivo_visible: string
  diagnostico: null
}

// El agente certificado firma con Ed25519 el nonce de vigia-ptw y el sha256 de su respuesta.
export interface EvidenciaFirma {
  nonce: string
  sha256: string
  firma: string
  clave_publica: string
}

export interface Consulta<T> {
  estado: EstadoConsulta
  data?: T
  evidencia?: EvidenciaFirma | null
}

export interface ConsultaGemelo extends Consulta<DatosGemelo> {
  // Solo front: true si la respuesta traía un diagnóstico y Vigía lo descartó antes de mostrarla.
  diagnostico_descartado?: boolean
}

// firma = valida solo si la credencial de las autoridades está vigente, no revocada y la ficha cuadra.
export interface FichaNanda {
  id: string
  capabilities: string[]
  firma: 'valida' | 'invalida'
  emisores?: string[]
  credencial_vence?: string | null
  motivo?: string | null
}

export interface Propuesta {
  decision: Decision
  nivel: Nivel
  requiere_supervisor: boolean
  porque: string[]
  controles_extra: string[]
  alternativa: string
}

// Solo existe una vez emitido: el checklist trae siempre la base IPERC más los controles extra.
export interface Petar {
  numero: string
  checklist: string[]
  firmado_por: string | null
  emitido_en: string
}

// Una regla evaluada para el admin. La fila de aptitud nunca trae valores clínicos (sin límite ni base legal).
export interface ReglaEvaluada {
  dato: string
  valor: string
  limite: string | null
  resultado: 'ok' | 'ambar' | 'rojo'
  base_legal: string | null
  fuente: string
}

export interface Ptw {
  ptw_id: string
  estado: EstadoPtw
  solicitud: Solicitud
  consultas: {
    incidentes: Consulta<DatosIncidentes>
    area: Consulta<DatosArea>
    gemelo: ConsultaGemelo
  }
  nanda: FichaNanda[]
  propuesta?: Propuesta
  petar?: Petar
  explicacion?: string | null
  tipo_tarea?: string
  tipo_labor?: string
  creado_en?: string
  cerrado_en?: string
  checklist_base?: string[]
  evaluacion?: ReglaEvaluada[]
  resultado?: Resultado
}

export interface ItemBandeja {
  ptw_id: string
  nivel: Nivel
  requiere_supervisor: boolean
  trabajador_nombre: string
  tarea: string
  labor: string
  turno: Turno
  creado_en: string
  tipo: 'revision' | 'aviso'
}

export interface Firma {
  accion: AccionFirma
  supervisor: string
  controles_finales: string[]
}

export interface Resultado {
  resultado: ResultadoTarea
  controles_cumplidos: boolean
  observacion: string
}

export interface EstadoVisual {
  apto_para_tarea: Aptitud
  motivo_visible: string
  energia: number
  dia_rotacion: number
  total_rotacion: number
  exposicion_nivel: 'baja' | 'media' | 'alta'
  historial_energia: number[]
}

export interface Avatar {
  trabajador_id: string
  nombre: string
  cargo: string
  empresa: string
  empleador: Empleador
  seed: string | number
  color_casco: string
  estado_visual: EstadoVisual
}
