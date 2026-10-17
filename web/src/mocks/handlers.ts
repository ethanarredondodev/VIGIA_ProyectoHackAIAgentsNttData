import { delay, http, HttpResponse } from 'msw'
import { API } from '../api'
import { destinoSupervisor } from '../negocio'
import { ACTIVIDADES_BASE } from '../pedido'
import type {
  DatosArea,
  DatosGemelo,
  DatosIncidentes,
  EstadoPtw,
  Firma,
  Interpretacion,
  ItemBandeja,
  Nivel,
  Propuesta,
  Ptw,
  ReglaEvaluada,
  Resultado,
  Solicitud,
} from '../tipos'
import { CONTROLES_BD, INCIDENTES_BD, LABORES_BD, LIMITES_BD } from './bd'
import {
  ACTIVIDADES,
  clasificarLabor,
  clasificarTarea,
  estadoVisual,
  EVIDENCIA_SIMULADA,
  FICHAS_NANDA,
  gemeloDe,
  LABORES,
  normalizar,
  SEMILLAS,
  TRABAJADORES,
  type Escenario,
} from './datos'

type Consulta = 'incidentes' | 'area' | 'gemelo'

interface Registro {
  ptw_id: string
  solicitud: Solicitud
  escenario: Escenario
  creado_ms: number
  retrasos: Record<Consulta, number>
  firma?: Firma & { en: string }
  iniciado?: boolean
  resultado?: Resultado
  cerrado_ms?: number
}

type Db = Record<string, Registro>

// NANDA resuelve primero; luego cada consulta tarda su retraso; al final se calcula el riesgo.
const T_NANDA = 1200
const T_CALCULO = 1500

// Se guarda en localStorage para que trabajador, supervisor y admin (pestañas distintas) vean lo mismo.
const CLAVE = 'vigia-mock-v2'
let memoria: Db | undefined

function sembrar(): Db {
  const ahora = Date.now()
  return Object.fromEntries(
    SEMILLAS.map((s) => {
      const creado_ms = ahora - s.hace_min * 60_000
      return [
        s.ptw_id,
        {
          ptw_id: s.ptw_id,
          solicitud: s.solicitud,
          escenario: 'ambar',
          creado_ms,
          retrasos: { incidentes: 900, area: 1300, gemelo: 1700 },
          resultado: s.resultado,
          cerrado_ms: s.resultado ? creado_ms + 150 * 60_000 : undefined,
        },
      ]
    }),
  )
}

function guardar(db: Db) {
  memoria = db
  try {
    localStorage.setItem(CLAVE, JSON.stringify(db))
  } catch {
    /* sin almacenamiento: la demo vive en memoria de esta pestaña */
  }
}

function cargar(): Db {
  try {
    const guardado = localStorage.getItem(CLAVE)
    if (guardado) return JSON.parse(guardado)
  } catch {
    /* idem */
  }
  const db = memoria ?? sembrar()
  guardar(db)
  return db
}

export function reiniciarMocks() {
  memoria = undefined
  try {
    localStorage.removeItem(CLAVE)
  } catch {
    /* idem */
  }
}

const ESCENARIOS: Escenario[] = ['verde', 'ambar', 'rojo']

function escenarioDeUrl(): Escenario | null {
  const e = new URLSearchParams(window.location.search).get('escenario')
  return ESCENARIOS.includes(e as Escenario) ? (e as Escenario) : null
}

// Cada consulta responde entre 0.8 y 2 s, en un orden distinto cada vez.
function retrasosAlAzar(): Record<Consulta, number> {
  const tiempos = [800, 1300, 1800].map((t) => t + Math.round(Math.random() * 200))
  const orden = (['incidentes', 'area', 'gemelo'] as Consulta[]).sort(() => Math.random() - 0.5)
  return { [orden[0]]: tiempos[0], [orden[1]]: tiempos[1], [orden[2]]: tiempos[2] } as Record<Consulta, number>
}

// --- Las mismas reglas del backend (agents/ptw/reglas_riesgo.py, agents/incidentes y las hojas) ---

// El cliente manda actividad_id; el servidor deriva tipo_tarea de la tabla. Sin actividad_id clasifica el texto.
function tipoTareaDe(s: Solicitud): string {
  if (s.actividad_id === undefined) return clasificarTarea(s.tarea)
  return ACTIVIDADES.find((a) => a.id === s.actividad_id)?.tipo_tarea ?? 'otro'
}

function areaDe(labor: string): DatosArea | null {
  const fila = LABORES_BD.find((l) => l.labor === labor)
  if (!fila) return null
  const { co_ppm, o2_pct, ventilacion, ruido_dBA, ultimo_desatado_h } = fila
  return { labor, co_ppm, o2_pct, ventilacion, ruido_dBA, ultimo_desatado_h }
}

const ORDEN_POTENCIAL = ['critico', 'alto', 'medio', 'bajo']

function incidentesDe(s: Solicitud, tipoTarea: string): DatosIncidentes {
  const laborTipo = clasificarLabor(s.tarea, s.labor)
  const buscar = (turno: string | null) =>
    INCIDENTES_BD.filter(
      (f) => f.tipo_mineria === s.tipo_mineria && f.tipo_tarea === tipoTarea && f.labor_tipo === laborTipo && (!turno || f.turno === turno),
    )
      .sort((a, b) => b.fecha.localeCompare(a.fecha))
      .sort((a, b) => ORDEN_POTENCIAL.indexOf(a.potencial) - ORDEN_POTENCIAL.indexOf(b.potencial))
  let turno: string | null = s.turno
  let filas = buscar(turno)
  if (filas.length < 2) {
    turno = null
    filas = buscar(null)
  }
  let patron = 'Sin incidentes similares registrados.'
  if (filas.length) {
    const cuenta = new Map<string, number>()
    filas.forEach((f) => cuenta.set(f.riesgo_critico, (cuenta.get(f.riesgo_critico) ?? 0) + 1))
    const [riesgo, cantidad] = [...cuenta.entries()].sort((a, b) => b[1] - a[1])[0]
    const causas = [...new Set(filas.slice(0, 3).map((f) => f.causa_probable.replace(/\.$/, '')))].join('; ')
    patron = `${filas.length} casos similares, ${cantidad} de ${riesgo.replaceAll('_', ' ')} en ${laborTipo.replaceAll('_', ' ')}${
      turno ? ` durante el turno ${turno}` : ''
    }. Causas: ${causas}.`
  }
  return {
    casos_similares: filas.length,
    patron,
    riesgo_potencial_max: filas[0]?.potencial ?? 'ninguno',
    casos: filas.slice(0, 5).map(({ id, resumen_es, riesgo_critico, causa_probable }) => ({ id, resumen_es, riesgo_critico, causa_probable })),
  }
}

const NOMBRES: Record<string, string> = { co_ppm: 'CO', o2_pct: 'O₂', ruido_dBA: 'Ruido', ultimo_desatado_h: 'Último desatado', ventilacion: 'Ventilación' }
const GRAVEDAD: Record<Nivel, number> = { verde: 0, ambar: 1, rojo: 2 }

function comparar(valor: unknown, operador: string, umbral: string): boolean {
  if (operador === 'in') return umbral.split('|').map((u) => u.trim()).includes(String(valor))
  const [a, b] = [Number(valor), Number(umbral)]
  if (!Number.isNaN(a) && !Number.isNaN(b)) {
    return { '<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b, '==': a === b, '!=': a !== b }[operador] ?? false
  }
  return operador === '==' ? String(valor) === umbral : operador === '!=' ? String(valor) !== umbral : false
}

interface Evaluacion {
  nivel: Nivel
  filas: ReglaEvaluada[]
  porque: string[]
  alternativa: string
}

function evaluar(s: Solicitud, area: DatosArea | null, gemelo: DatosGemelo, inc: DatosIncidentes): Evaluacion {
  let nivel = 'verde' as Nivel
  const filas: ReglaEvaluada[] = []
  const porque: string[] = []
  const causasRojo = new Set<string>()
  const elevar = (nuevo: Nivel, motivo: string, causa: string) => {
    if (GRAVEDAD[nuevo] > GRAVEDAD[nivel]) nivel = nuevo
    if (nuevo === 'rojo') causasRojo.add(causa)
    porque.push(motivo)
  }

  if (!area) {
    filas.push({ dato: 'Condiciones de la labor', valor: 'sin datos', limite: null, resultado: 'rojo', base_legal: null, fuente: 'vigia-area' })
    elevar('rojo', 'No se obtuvieron las condiciones de la labor: no se puede verificar la atmósfera.', 'area')
  } else {
    for (const limite of LIMITES_BD) {
      if (limite.tipo_mineria !== 'todas' && limite.tipo_mineria !== s.tipo_mineria) continue
      const valor = area[limite.agente as keyof DatosArea]
      const unidad = limite.unidad ? ` ${limite.unidad}` : ''
      const minimo = limite.tipo.startsWith('min')
      const igual = limite.tipo.startsWith('igual')
      const falla = comparar(valor, minimo ? '<' : igual ? '!=' : '>', limite.limite)
      const nivelFalla: Nivel = limite.tipo.endsWith('rojo') ? 'rojo' : 'ambar'
      filas.push({
        dato: NOMBRES[limite.agente] ?? limite.agente,
        valor: `${valor}${unidad}`,
        limite: igual ? limite.limite : `${minimo ? 'mínimo' : 'máximo'} ${limite.limite}${unidad}`,
        resultado: falla ? nivelFalla : 'ok',
        base_legal: limite.base_legal,
        fuente: 'vigia-area',
      })
      if (falla) {
        const texto = minimo ? 'está por debajo del mínimo de' : igual ? 'no cumple lo requerido:' : 'supera el máximo de'
        elevar(nivelFalla, `${NOMBRES[limite.agente].replace('₂', '2')} ${valor}${unidad} ${texto} ${limite.limite}${unidad} (${limite.base_legal}).`, 'area')
      }
    }
  }

  const aptitud = gemelo.apto_para_tarea
  filas.push({
    dato: 'Aptitud',
    valor: aptitud,
    limite: null,
    resultado: aptitud === 'no_apto' ? 'rojo' : aptitud === 'apto_con_observaciones' ? 'ambar' : 'ok',
    base_legal: null,
    fuente: 'vigia-gemelo',
  })
  if (aptitud === 'no_apto') elevar('rojo', `Trabajador no apto hoy para la tarea: ${gemelo.motivo_visible}.`, 'aptitud')
  if (aptitud === 'apto_con_observaciones') elevar('ambar', `Trabajador apto con observaciones: ${gemelo.motivo_visible}.`, 'aptitud')

  const grave = inc.casos_similares >= 3 && ['alto', 'critico'].includes(inc.riesgo_potencial_max)
  filas.push({
    dato: 'Casos parecidos',
    valor: inc.casos_similares ? `${inc.casos_similares}, potencial ${inc.riesgo_potencial_max}` : '0',
    limite: 'menos de 3 con potencial alto',
    resultado: grave ? 'ambar' : 'ok',
    base_legal: null,
    fuente: 'vigia-incidentes',
  })
  if (grave) elevar('ambar', `${inc.casos_similares} incidentes similares con potencial ${inc.riesgo_potencial_max}: ${inc.patron}`, 'incidentes')

  let alternativa = 'No requiere alternativa.'
  if (nivel === 'rojo') {
    alternativa = [
      causasRojo.has('aptitud') && 'Reasignar la tarea a otro trabajador apto del mismo turno.',
      causasRojo.has('area') && 'Esperar: no ingresar a la labor hasta corregir las condiciones y repetir la medición.',
    ]
      .filter(Boolean)
      .join(' ')
  } else if (nivel === 'ambar') {
    alternativa = 'Si los controles no pueden aplicarse antes del inicio, reprogramar la tarea o reasignarla.'
  }
  return {
    nivel,
    filas,
    porque: porque.length ? porque : ['Sin desviaciones frente a límites de la labor, aptitud ni historial de incidentes.'],
    alternativa,
  }
}

// Base: disparador "siempre" o que solo depende de tipo_tarea. Extra: el resto, si se cumple.
function checklist(senales: Record<string, unknown>) {
  const base: string[] = []
  const extra: string[] = []
  let altoRiesgo = false
  for (const control of CONTROLES_BD) {
    if (base.includes(control.control) || extra.includes(control.control)) continue
    const texto = control.disparador.trim()
    let esBase = texto === 'siempre'
    if (!esBase) {
      const [, variable, operador, umbral] = texto.match(/^(\w+)\s*(<=|>=|==|!=|<|>|in)\s*(.+)$/) ?? []
      if (senales[variable] == null || !comparar(senales[variable], operador, umbral.trim())) continue
      esBase = variable === 'tipo_tarea'
    }
    ;(esBase ? base : extra).push(control.control)
    altoRiesgo ||= control.trabajo_alto_riesgo === 'si'
  }
  return { base, extra, altoRiesgo }
}

const DECISION: Record<Nivel, Propuesta['decision']> = { verde: 'autorizar', ambar: 'autorizar_con_controles', rojo: 'reasignar' }

function estadoDe(r: Registro, p: Propuesta | undefined): EstadoPtw {
  if (!p) return 'procesando'
  if (r.resultado) return 'cerrado'
  if (r.iniciado) return 'en_ejecucion'
  if (p.nivel === 'rojo') return 'bloqueado'
  if (r.firma) return r.firma.accion === 'rechazar' ? 'rechazado' : 'autorizado_con_controles'
  return destinoSupervisor(p) ? 'en_revision' : 'emitido'
}

function construir(r: Registro, ahora = Date.now()): Ptw {
  const s = r.solicitud
  const t = ahora - r.creado_ms
  const fin = T_NANDA + Math.max(...Object.values(r.retrasos)) + T_CALCULO
  const lista = (k: Consulta) => t >= T_NANDA + r.retrasos[k]

  const tipoTarea = tipoTareaDe(s)
  const area = areaDe(s.labor)
  const g = gemeloDe(s.trabajador_id, r.escenario)
  const gemelo: DatosGemelo = { trabajador_id: s.trabajador_id, apto_para_tarea: g.apto_para_tarea, motivo_visible: g.motivo_visible, diagnostico: null }
  const incidentes = incidentesDe(s, tipoTarea)
  const evaluacion = evaluar(s, area, gemelo, incidentes)
  const controles = checklist({
    ...s,
    tipo_tarea: tipoTarea,
    ...area,
    apto_para_tarea: gemelo.apto_para_tarea,
    casos_similares: incidentes.casos_similares,
    riesgo_potencial_max: incidentes.riesgo_potencial_max,
  })
  const propuesta: Propuesta | undefined =
    t >= fin
      ? {
          decision: DECISION[evaluacion.nivel],
          nivel: evaluacion.nivel,
          requiere_supervisor: controles.altoRiesgo || tipoTarea === 'otro',
          porque: evaluacion.porque,
          controles_extra: controles.extra,
          alternativa: evaluacion.alternativa,
        }
      : undefined

  const firmado = r.firma && r.firma.accion !== 'rechazar' ? r.firma : undefined
  // Como el backend: no hay PETAR hasta emitirlo; la base IPERC va siempre y "ajustar" solo cambia los extra.
  const emitidoSolo = propuesta && !destinoSupervisor(propuesta)
  const extras = firmado?.accion === 'ajustar' ? firmado.controles_finales : controles.extra
  return {
    ptw_id: r.ptw_id,
    estado: estadoDe(r, propuesta),
    solicitud: s,
    consultas: {
      incidentes: lista('incidentes') ? { estado: 'ok', data: incidentes, evidencia: EVIDENCIA_SIMULADA } : { estado: 'pendiente' },
      area: lista('area')
        ? area
          ? { estado: 'ok', data: area, evidencia: EVIDENCIA_SIMULADA }
          : { estado: 'error' }
        : { estado: 'pendiente' },
      gemelo: lista('gemelo') ? { estado: 'ok', data: gemelo, evidencia: EVIDENCIA_SIMULADA } : { estado: 'pendiente' },
    },
    nanda: t >= T_NANDA ? FICHAS_NANDA : [],
    propuesta,
    petar:
      firmado || emitidoSolo
        ? {
            numero: `PETAR-2026-${r.ptw_id.slice(-4)}`,
            checklist: [...new Set([...controles.base, ...extras])],
            firmado_por: firmado?.supervisor ?? null,
            emitido_en: firmado?.en ?? new Date(r.creado_ms + fin).toISOString(),
          }
        : undefined,
    tipo_tarea: tipoTarea,
    tipo_labor: clasificarLabor(s.tarea, s.labor),
    creado_en: new Date(r.creado_ms).toISOString(),
    ...(propuesta && { checklist_base: controles.base, evaluacion: evaluacion.filas }),
    ...(r.resultado && { resultado: r.resultado, cerrado_en: new Date(r.cerrado_ms ?? ahora).toISOString() }),
  }
}

// Simula la IA de Vigía comparando el texto con la tabla de actividades (en el backend lo hace Claude).
function interpretar(texto: string): Interpretacion {
  const n = normalizar(texto)
  const coinciden = ACTIVIDADES.filter((a) => a.sinonimos.some((s) => n.includes(s)))
  const elegida = coinciden[0] ? ACTIVIDADES_BASE.find((a) => a.id === coinciden[0].id)! : null
  const codigo = texto.toUpperCase().match(/(?:NV-?\s?(\d{4})\s*)?\b(TJ|GA|GL|RP|CH|XC|CX|BC)\s?-?\s?(\d{1,4})\b/)
  const candidatas = codigo
    ? LABORES.filter((l) => l.labor.endsWith(`${codigo[2]}-${codigo[3]}`) && (!codigo[1] || l.labor.startsWith(`NV-${codigo[1]}`)))
    : []
  const labor = candidatas.length === 1 ? candidatas[0].labor : null
  return {
    actividad: elegida,
    labor,
    tipo_labor: labor ? clasificarLabor(texto, labor) : null,
    confianza: !elegida ? 'baja' : coinciden.length > 1 ? 'media' : 'alta',
    alternativas: ACTIVIDADES_BASE.filter((a) => a.id !== elegida?.id),
  }
}

function buscar(id: string) {
  const db = cargar()
  return { db, registro: db[id] as Registro | undefined }
}

const noExiste = (id: string) => HttpResponse.json({ detail: `PTW ${id} no existe` }, { status: 404 })

export const handlers = [
  http.get(`${API}/actividades`, async () => {
    await delay()
    return HttpResponse.json(ACTIVIDADES_BASE)
  }),

  http.get(`${API}/labores`, async () => {
    await delay()
    return HttpResponse.json(LABORES)
  }),

  http.post(`${API}/tareas/interpretar`, async ({ request }) => {
    await delay()
    const { texto } = (await request.json()) as { texto: string }
    return HttpResponse.json(interpretar(texto))
  }),

  http.post(`${API}/ptw/solicitud`, async ({ request }) => {
    await delay()
    const solicitud = (await request.json()) as Solicitud
    const db = cargar()
    const ptw_id = `PTW-${Math.random().toString(36).slice(2, 8).toUpperCase()}`
    db[ptw_id] = {
      ptw_id,
      solicitud,
      escenario: escenarioDeUrl() ?? 'ambar',
      creado_ms: Date.now(),
      retrasos: retrasosAlAzar(),
    }
    guardar(db)
    return HttpResponse.json({ ptw_id, estado: 'procesando' }, { status: 201 })
  }),

  http.get(`${API}/ptw/bandeja`, async () => {
    await delay()
    const items: ItemBandeja[] = []
    for (const r of Object.values(cargar())) {
      const ptw = construir(r)
      const tipo = ptw.propuesta && destinoSupervisor(ptw.propuesta)
      if (!ptw.propuesta || !tipo || (tipo === 'revision' && ptw.estado !== 'en_revision')) continue
      if (tipo === 'aviso' && ptw.estado !== 'bloqueado') continue
      items.push({
        ptw_id: r.ptw_id,
        nivel: ptw.propuesta.nivel,
        requiere_supervisor: ptw.propuesta.requiere_supervisor,
        trabajador_nombre: TRABAJADORES[r.solicitud.trabajador_id]?.nombre ?? r.solicitud.trabajador_id,
        tarea: r.solicitud.tarea,
        labor: r.solicitud.labor,
        turno: r.solicitud.turno,
        creado_en: new Date(r.creado_ms).toISOString(),
        tipo,
      })
    }
    return HttpResponse.json(items.sort((a, b) => b.creado_en.localeCompare(a.creado_en)))
  }),

  http.get(`${API}/ptw`, async () => {
    await delay()
    const registros = Object.values(cargar()).sort((a, b) => b.creado_ms - a.creado_ms)
    return HttpResponse.json(registros.map((r) => construir(r)))
  }),

  http.get(`${API}/ptw/:id`, async ({ params }) => {
    await delay()
    const { registro } = buscar(params.id as string)
    return registro ? HttpResponse.json(construir(registro)) : noExiste(params.id as string)
  }),

  http.post(`${API}/ptw/:id/firma`, async ({ params, request }) => {
    await delay()
    const { db, registro } = buscar(params.id as string)
    if (!registro) return noExiste(params.id as string)
    if (construir(registro).estado !== 'en_revision') {
      return HttpResponse.json({ detail: 'El PTW no está en revisión' }, { status: 409 })
    }
    const firma = (await request.json()) as Firma
    if (firma.accion === 'ajustar' && firma.controles_finales.length === 0) {
      return HttpResponse.json({ detail: 'Al ajustar debes indicar los controles finales.' }, { status: 422 })
    }
    registro.firma = { ...firma, en: new Date().toISOString() }
    guardar(db)
    return HttpResponse.json(construir(registro))
  }),

  http.post(`${API}/ptw/:id/inicio`, async ({ params }) => {
    await delay()
    const { db, registro } = buscar(params.id as string)
    if (!registro) return noExiste(params.id as string)
    if (!['emitido', 'autorizado_con_controles'].includes(construir(registro).estado)) {
      return HttpResponse.json({ detail: 'El PTW no está autorizado' }, { status: 409 })
    }
    registro.iniciado = true
    guardar(db)
    return HttpResponse.json(construir(registro))
  }),

  http.post(`${API}/ptw/:id/resultado`, async ({ params, request }) => {
    await delay()
    const { db, registro } = buscar(params.id as string)
    if (!registro) return noExiste(params.id as string)
    if (!['emitido', 'autorizado_con_controles', 'en_ejecucion'].includes(construir(registro).estado)) {
      return HttpResponse.json({ detail: 'El PTW no está autorizado' }, { status: 409 })
    }
    registro.resultado = (await request.json()) as Resultado
    registro.cerrado_ms = Date.now()
    guardar(db)
    return HttpResponse.json(construir(registro))
  }),

  http.get(`${API}/trabajadores/:id/avatar`, async ({ params }) => {
    await delay()
    const avatar = TRABAJADORES[params.id as string]
    if (!avatar) return noExiste(params.id as string)
    if (avatar.trabajador_id !== 'T-001') return HttpResponse.json(avatar)
    const ultimo = Object.values(cargar())
      .filter((r) => r.solicitud.trabajador_id === 'T-001')
      .sort((a, b) => b.creado_ms - a.creado_ms)[0]
    const escenario = escenarioDeUrl() ?? ultimo?.escenario ?? 'ambar'
    return HttpResponse.json({ ...avatar, estado_visual: estadoVisual(gemeloDe('T-001', escenario)) })
  }),
]
