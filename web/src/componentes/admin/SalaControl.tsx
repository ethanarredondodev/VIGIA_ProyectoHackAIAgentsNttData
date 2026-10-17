import { useEffect, useRef, useState, type ReactNode } from 'react'
import { destinoSupervisor, TEXTO_APTITUD, TEXTO_NIVEL, TEXTO_TRABAJADOR } from '../../negocio'
import type { EstadoSala, Etapa, Fase } from '../../sala'
import type { Avatar, Ptw } from '../../tipos'
import { FiguraMinero } from '../AvatarGemelo'
import { DetalleEtapa, TITULO_ETAPA } from './Detalle'

// Tablero aprobado en docs/superpowers/specs/maquetas/sala-control-v3.html.
const NODOS: { etapa: Exclude<Etapa, 'trabajador'>; x: number; y: number; w: number; h: number }[] = [
  { etapa: 'ptw', x: 185, y: 162, w: 130, h: 56 },
  { etapa: 'nanda', x: 345, y: 162, w: 135, h: 56 },
  { etapa: 'incidentes', x: 520, y: 62, w: 150, h: 56 },
  { etapa: 'area', x: 520, y: 162, w: 150, h: 56 },
  { etapa: 'gemelo', x: 520, y: 262, w: 150, h: 56 },
  { etapa: 'reglas', x: 705, y: 162, w: 105, h: 56 },
  { etapa: 'decision', x: 845, y: 152, w: 100, h: 76 },
  { etapa: 'destino', x: 975, y: 162, w: 120, h: 56 },
]

const TUBOS: { hacia: Etapa; d: string }[] = [
  { hacia: 'ptw', d: 'M96 168 C140 166 150 190 185 190' },
  { hacia: 'nanda', d: 'M315 190 H345' },
  { hacia: 'incidentes', d: 'M480 190 H500 V90 H520' },
  { hacia: 'area', d: 'M480 190 H520' },
  { hacia: 'gemelo', d: 'M480 190 H500 V290 H520' },
  { hacia: 'reglas', d: 'M670 90 H688 V190 H705' },
  { hacia: 'reglas', d: 'M670 190 H705' },
  { hacia: 'reglas', d: 'M670 290 H688 V190 H705' },
  { hacia: 'decision', d: 'M810 190 H845' },
  { hacia: 'destino', d: 'M945 190 H975' },
]
const REGRESO = 'M895 228 V352 H20 V190 H36'

const SUBTITULO_FASE: Record<Fase, string> = { espera: 'en espera', proceso: 'trabajando…', listo: '', error: 'sin respuesta' }
const ICONO: Record<string, string> = { verde: '✓', ambar: '!', rojo: '✕' }

function resumen(etapa: Etapa, ptw: Ptw): string {
  const c = ptw.consultas
  const p = ptw.propuesta
  const fuera = (fuente?: string) => (ptw.evaluacion ?? []).filter((f) => f.resultado !== 'ok' && (!fuente || f.fuente === fuente)).length
  switch (etapa) {
    case 'ptw':
      return 'pedido recibido'
    case 'nanda': {
      const malas = ptw.nanda.filter((f) => f.firma !== 'valida').length
      return malas ? `${malas} descartada${malas > 1 ? 's' : ''}` : `${ptw.nanda.length} fichas válidas`
    }
    case 'incidentes':
      return `${c.incidentes.data?.casos_similares ?? 0} casos parecidos`
    case 'area':
      return ptw.evaluacion ? (fuera('vigia-area') ? `${fuera('vigia-area')} fuera de límite` : 'dentro de límites') : 'medido'
    case 'gemelo':
      return c.gemelo.data ? TEXTO_APTITUD[c.gemelo.data.apto_para_tarea] : ''
    case 'reglas':
      // Sin evaluacion (backend de hoy) no se sabe cuáles pasaron: se cuentan los motivos.
      if (!ptw.evaluacion) return p ? `${p.porque.length} motivo${p.porque.length === 1 ? '' : 's'}` : ''
      return fuera() ? `${fuera()} en ${p ? TEXTO_NIVEL[p.nivel].toLowerCase() : 'alerta'}` : 'todo dentro'
    case 'destino':
      return p?.nivel === 'rojo' ? 'aviso al supervisor' : p && destinoSupervisor(p) ? 'Ing. Rosa Quispe' : 'al trabajador'
    default:
      return ''
  }
}

function tituloDestino(ptw: Ptw): string {
  const p = ptw.propuesta
  if (!p) return 'Destino'
  if (p.nivel === 'rojo') return 'Bloqueada'
  return destinoSupervisor(p) ? 'Bandeja' : 'PETAR emitido'
}

// Luz de la lámpara que recorre un tubo mientras la etapa de destino trabaja.
function Chispa({ d, activa, cada = 1400 }: { d: string; activa: boolean; cada?: number }) {
  const ruta = useRef<SVGPathElement>(null)
  const chispa = useRef<SVGCircleElement>(null)
  useEffect(() => {
    const p = ruta.current
    const c = chispa.current
    if (!activa || !p || !c || typeof p.getTotalLength !== 'function') return
    const largo = p.getTotalLength()
    const inicio = performance.now()
    let id = 0
    const mover = (ahora: number) => {
      const t = ((ahora - inicio) % cada) / cada
      const punto = p.getPointAtLength(t * largo)
      c.setAttribute('cx', String(punto.x))
      c.setAttribute('cy', String(punto.y))
      id = requestAnimationFrame(mover)
    }
    id = requestAnimationFrame(mover)
    return () => cancelAnimationFrame(id)
  }, [activa, cada])
  return (
    <>
      <path ref={ruta} d={d} fill="none" stroke="none" />
      {activa && <circle ref={chispa} r="5" className="chispa" />}
    </>
  )
}

interface Props {
  ptw: Ptw
  avatar?: Avatar
  sala: EstadoSala
  animar: boolean
}

export function SalaControl({ ptw, avatar, sala, animar }: Props) {
  const tablero = useRef<HTMLDivElement>(null)
  const [mirando, setMirando] = useState<{ etapa: Etapa; x: number; y: number } | null>(null)
  const p = ptw.propuesta
  const nivel = p?.nivel

  const abrir = (etapa: Etapa) => (e: { currentTarget: Element }) => {
    const r = e.currentTarget.getBoundingClientRect()
    const base = tablero.current!.getBoundingClientRect()
    const derecha = r.right - base.left + 14
    setMirando({ etapa, x: derecha + 360 <= base.width ? derecha : Math.max(8, r.left - base.left - 374), y: Math.max(8, r.top - base.top - 40) })
  }
  const cerrar = () => setMirando(null)
  const interactivo = (etapa: Etapa) => ({
    role: 'button',
    tabIndex: 0,
    'aria-label': `${TITULO_ETAPA[etapa]}: ver detalle`,
    onMouseEnter: abrir(etapa),
    onFocus: abrir(etapa),
    onClick: abrir(etapa),
    onMouseLeave: cerrar,
    onBlur: cerrar,
    onKeyDown: (e: { key: string }) => e.key === 'Escape' && cerrar(),
  })

  let burbuja: ReactNode = null
  if (sala.destino === 'listo' && p) {
    const texto = TEXTO_TRABAJADOR[ptw.estado]
    burbuja = (
      <g className="burbuja">
        <rect x="8" y="58" width="196" height="38" rx="8" />
        <path d="M80 95 L90 112 L100 95 Z" />
        <text x="22" y="82">
          {texto}
        </text>
      </g>
    )
  }

  return (
    <div ref={tablero} className="relative rounded-lg bg-[#1f2730] p-4">
      <svg className="sala" viewBox="0 0 1100 380" role="group" aria-label="Recorrido de la solicitud por los agentes de Vigía">
        {TUBOS.map((t, i) => {
          const fase = sala[t.hacia]
          return (
            <g key={i}>
              <path className={`tubo ${fase !== 'espera' ? 'on' : ''}`} d={t.d} />
              {animar && <Chispa d={t.d} activa={fase === 'proceso'} />}
            </g>
          )
        })}
        <path className={`tubo ${sala.destino === 'listo' ? 'on' : ''}`} d={REGRESO} />
        {animar && <Chispa d={REGRESO} activa={sala.destino === 'listo'} cada={2600} />}

        <g className="juan" {...interactivo('trabajador')}>
          {avatar && (
            <foreignObject x="32" y="132" width="116" height="116">
              <FiguraMinero avatar={avatar} consultando={sala.gemelo !== 'listo'} />
            </foreignObject>
          )}
          <text className="nombre" x="90" y="268" textAnchor="middle">
            {avatar?.nombre ?? ptw.solicitud.trabajador_id}
          </text>
          <text className="cargo" x="90" y="285" textAnchor="middle">
            {avatar?.cargo.toLowerCase() ?? ''}
          </text>
        </g>
        {burbuja}

        {NODOS.map((n) => {
          const fase = sala[n.etapa]
          const esDecision = n.etapa === 'decision'
          const titulo = n.etapa === 'destino' ? tituloDestino(ptw) : TITULO_ETAPA[n.etapa]
          const sub = fase === 'listo' ? resumen(n.etapa, ptw) : SUBTITULO_FASE[fase]
          return (
            <g key={n.etapa} className={`nodo fase-${fase} ${esDecision && fase === 'listo' && nivel ? `decision nivel-${nivel}` : ''}`} {...interactivo(n.etapa)}>
              <rect x={n.x} y={n.y} width={n.w} height={n.h} rx="8" />
              {esDecision && fase === 'listo' && nivel ? (
                <text className="grande" x={n.x + n.w / 2} y={n.y + 46} textAnchor="middle">
                  {ICONO[nivel]} {TEXTO_NIVEL[nivel]}
                </text>
              ) : (
                <>
                  <text className="titulo" x={n.x + 13} y={n.y + 23}>
                    {titulo}
                  </text>
                  <text className="estado" x={n.x + 13} y={n.y + 43}>
                    {sub}
                  </text>
                </>
              )}
            </g>
          )
        })}
      </svg>
      {mirando && (
        <div className="absolute z-10 w-[350px] rounded-lg bg-superficie p-4 text-tinta shadow-2xl" style={{ left: mirando.x, top: mirando.y }} role="tooltip">
          <DetalleEtapa etapa={mirando.etapa} fase={sala[mirando.etapa]} ptw={ptw} avatar={avatar} />
        </div>
      )}
    </div>
  )
}

// En pantallas angostas: las mismas etapas en lista, con el detalle en vivo al tocarlas.
export function ListaEtapas({ ptw, avatar, sala }: Omit<Props, 'animar'>) {
  const [abierta, setAbierta] = useState<Etapa | null>(null)
  const etapas: Etapa[] = ['trabajador', ...NODOS.map((n) => n.etapa)]
  return (
    <ol className="space-y-2">
      {etapas.map((etapa) => {
        const fase = sala[etapa]
        return (
          <li key={etapa} className="rounded-md bg-superficie">
            <button
              type="button"
              aria-expanded={abierta === etapa}
              onClick={() => setAbierta(abierta === etapa ? null : etapa)}
              className="flex min-h-12 w-full items-center justify-between gap-3 px-4 text-left"
            >
              <span className="font-cond text-lg font-semibold">{TITULO_ETAPA[etapa]}</span>
              <span className={`text-sm font-semibold ${fase === 'error' ? 'text-rojo-texto' : fase === 'listo' ? 'text-verde-texto' : 'text-tinta-2'}`}>
                {fase === 'listo' ? 'Listo' : fase === 'proceso' ? 'Procesando…' : fase === 'error' ? 'Sin respuesta' : 'En espera'}
              </span>
            </button>
            {abierta === etapa && (
              <div className="border-t border-linea px-4 py-3">
                <DetalleEtapa etapa={etapa} fase={fase} ptw={ptw} avatar={avatar} />
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}
