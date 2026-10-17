import { useId } from 'react'
import { useAvatar } from '../api'
import { CLASES_NIVEL, NIVEL_DE_APTITUD, TEXTO_APTITUD } from '../negocio'
import type { Aptitud, Avatar } from '../tipos'
import { mezcla, rasgos, sombra } from './rasgos'

// Privacidad: este componente solo conoce el estado visual del gemelo. Nunca recibe datos clínicos.

type Tamano = 'sm' | 'md' | 'lg'

const ANCHO: Record<Tamano, string> = { sm: 'w-14', md: 'w-28 sm:w-32', lg: 'w-60' }

const CORTO: Record<Aptitud, string> = { apto: 'Apto', apto_con_observaciones: 'Con observ.', no_apto: 'No apto' }

const CHALECO_IZQ = 'M30 200C34 170 54 154 82 149L90 200Z'
const CHALECO_DER = 'M170 200C166 170 146 154 118 149L110 200Z'

export function FiguraMinero({ avatar, consultando }: { avatar: Avatar; consultando: boolean }) {
  const uid = useId().replace(/:/g, '')
  const r = rasgos(String(avatar.seed))
  const ev = avatar.estado_visual
  const energia = Math.min(100, Math.max(0, ev.energia)) / 100
  const cansado = ev.energia < 40
  const nivel = consultando ? null : NIVEL_DE_APTITUD[ev.apto_para_tarea]
  const anillo = nivel ? `var(--${nivel})` : 'var(--linea)'
  const pielSombra = sombra(r.piel, 0.2)
  const casco = avatar.color_casco
  const cascoBorde = sombra(casco, 0.35)
  const transicion = 'opacity 700ms ease, transform 700ms ease, fill 700ms ease, stroke 700ms ease'
  const izq = 100 - r.cara
  const der = 100 + r.cara

  return (
    <svg viewBox="0 0 200 200" className="block h-auto w-full" aria-hidden="true" focusable="false">
      <defs>
        <clipPath id={`${uid}-marco`}>
          <circle cx="100" cy="100" r="86" />
        </clipPath>
        <clipPath id={`${uid}-chaleco`}>
          <path d={CHALECO_IZQ} />
          <path d={CHALECO_DER} />
        </clipPath>
        <radialGradient id={`${uid}-luz`}>
          <stop offset="0" stopColor="#FFF6CF" stopOpacity="0.95" />
          <stop offset="0.35" stopColor="#FFD45C" stopOpacity="0.55" />
          <stop offset="1" stopColor="#FFD45C" stopOpacity="0" />
        </radialGradient>
      </defs>

      <circle
        cx="100"
        cy="100"
        r="94"
        fill="none"
        strokeWidth="7"
        strokeDasharray={nivel ? undefined : '5 7'}
        style={{ stroke: anillo, transition: transicion }}
      />

      <g clipPath={`url(#${uid}-marco)`}>
        <rect width="200" height="200" fill="#26303A" />
        <path d="M10 72L50 38L70 80L28 114Z" fill="#2E3944" />
        <path d="M148 26L192 62L178 112L138 84Z" fill="#212A33" />

        <g className="motion-safe:animate-respirar" style={{ transformBox: 'fill-box', transformOrigin: '50% 100%' }}>
          {r.peinado === 'largo' && (
            <path
              d={`M${izq - 1} 86C${izq - 7} 118 ${izq - 9} 140 ${izq + 1} 156L${der - 1} 156C${der + 9} 140 ${der + 7} 118 ${der + 1} 86Z`}
              fill={r.pelo}
            />
          )}
          <path d="M22 200C26 162 58 146 100 146C142 146 174 162 178 200Z" fill={r.ropa} />
          <rect x="88" y="120" width="24" height="32" rx="6" fill={pielSombra} />
          <path d={CHALECO_IZQ} fill="#D3E23A" />
          <path d={CHALECO_DER} fill="#D3E23A" />
          <g clipPath={`url(#${uid}-chaleco)`} fill="#C9CED6">
            <rect x="20" y="174" width="160" height="6" />
            <rect x="20" y="186" width="160" height="6" />
          </g>

          {/* Respirador colgado al cuello, con filtros P100 */}
          <path d="M84 140Q88 152 91 160M116 140Q112 152 109 160" stroke="#3A4148" strokeWidth="2" fill="none" />
          <path d="M89 160Q100 153 111 160L109 174Q100 180 91 174Z" fill="#8E979F" stroke="#6C757D" strokeWidth="1.2" />
          <circle cx="86" cy="171" r="7" fill="#C23B78" stroke="#8E2557" strokeWidth="1.5" />
          <circle cx="114" cy="171" r="7" fill="#C23B78" stroke="#8E2557" strokeWidth="1.5" />
          <circle cx="86" cy="171" r="2.6" fill="#8E2557" />
          <circle cx="114" cy="171" r="2.6" fill="#8E2557" />
          <circle cx="100" cy="169" r="3" fill="#5B646C" />

          <ellipse cx={izq - 1} cy="103" rx="5" ry="8" fill={pielSombra} />
          <ellipse cx={der + 1} cy="103" rx="5" ry="8" fill={pielSombra} />
          <ellipse cx="100" cy="100" rx={r.cara} ry="33" fill={r.piel} />

          {r.peinado !== 'largo' && r.peinado !== 'trenza' ? (
            <>
              <rect x={izq} y="84" width="6" height={r.peinado === 'patillas' ? 17 : 8} rx="2" fill={r.pelo} />
              <rect x={der - 6} y="84" width="6" height={r.peinado === 'patillas' ? 17 : 8} rx="2" fill={r.pelo} />
            </>
          ) : (
            <>
              <path d={`M${izq - 1} 84L${izq + 7} 84L${izq + 3} 118L${izq - 1} 112Z`} fill={r.pelo} />
              <path d={`M${der + 1} 84L${der - 7} 84L${der - 3} 118L${der + 1} 112Z`} fill={r.pelo} />
            </>
          )}
          {r.peinado === 'trenza' &&
            [0, 1, 2, 3, 4].map((i) => (
              <ellipse
                key={i}
                cx={der + 2 + i * 1.5}
                cy={122 + i * 9}
                rx="5"
                ry="6"
                fill={r.pelo}
                stroke={sombra(r.pelo, -0.6)}
                strokeWidth="0.8"
              />
            ))}

          {[-1, 1].map((lado) => {
            const x = 100 + lado * r.ojos
            return (
              <g key={lado}>
                <path
                  d={`M${x - 6} 93Q${x} 89.5 ${x + 6} 93`}
                  stroke={r.pelo}
                  strokeWidth={r.cejas}
                  strokeLinecap="round"
                  fill="none"
                />
                <ellipse cx={x} cy="101" rx="4.4" ry="3.3" fill="#F3EFE8" />
                <circle cx={x} cy="101.4" r="2.3" fill="#2A1D16" />
                {/* Párpado: cae cuando la energía baja de 40 */}
                <path
                  d={`M${x - 5.2} 101.4A5.2 4.6 0 0 1 ${x + 5.2} 101.4Z`}
                  fill={r.piel}
                  stroke={pielSombra}
                  strokeWidth="1.2"
                  style={{
                    transformBox: 'fill-box',
                    transformOrigin: 'top',
                    transform: `scaleY(${cansado ? 1 : 0})`,
                    opacity: cansado ? 1 : 0,
                    transition: transicion,
                  }}
                />
              </g>
            )
          })}
          <path
            d={`M100 104Q${100 + r.nariz} 111 ${100 - r.nariz * 0.4} 114`}
            stroke={pielSombra}
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
          />
          {r.bigote && <path d="M89 120Q100 112 111 120Q100 117 89 120Z" fill={r.pelo} />}
          <path
            d={`M93 124Q100 ${cansado ? 124.5 : 128} 107 124`}
            stroke="#5A2E22"
            strokeWidth="2.2"
            strokeLinecap="round"
            fill="none"
          />

          {/* Casco con lámpara: el brillo sigue a la energía */}
          <path d="M64 86C64 58 80 44 100 44C120 44 136 58 136 86Z" fill={casco} stroke={cascoBorde} strokeWidth="1.5" />
          <path d="M95 45.5Q100 44 105 45.5L105 57L95 57Z" fill={cascoBorde} opacity="0.5" />
          <rect x="54" y="82" width="92" height="9" rx="4.5" fill={casco} stroke={cascoBorde} strokeWidth="1.5" />
          <path d="M112 68C126 70 134 78 135 88" stroke="#2E353D" strokeWidth="2" fill="none" />
          <rect x="88" y="58" width="24" height="17" rx="5" fill="#2E353D" />
          <circle
            cx="100"
            cy="66.5"
            r="6.2"
            style={{ fill: mezcla('#5E5747', '#FFF6CF', energia), transition: transicion }}
          />
          <circle
            cx="100"
            cy="66.5"
            r={14 + 22 * energia}
            fill={`url(#${uid}-luz)`}
            style={{ opacity: 0.2 + 0.8 * energia, transition: transicion }}
          />
        </g>
      </g>

      {nivel && (
        <g style={{ color: `var(--sobre-${nivel})` }}>
          <circle cx="163" cy="163" r="17" stroke="var(--superficie)" strokeWidth="3" style={{ fill: anillo }} />
          <g stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" fill="none">
            {nivel === 'verde' && <path d="M155.5 163.5l5 5 9.5-10.5" />}
            {nivel === 'ambar' && (
              <>
                <path d="M163 154.5v9" />
                <circle cx="163" cy="170" r="1.2" fill="currentColor" />
              </>
            )}
            {nivel === 'rojo' && <path d="M157 157l12 12M169 157l-12 12" />}
          </g>
        </g>
      )}
    </svg>
  )
}

function Energia({ historial, energia, ancho }: { historial: number[]; energia: number; ancho: number }) {
  const alto = 28
  const paso = ancho / historial.length
  return (
    <div>
      <p className="text-xs text-tinta-2">Energía en 14 días</p>
      <div className="mt-0.5 flex items-end gap-2">
        <svg width={ancho} height={alto} viewBox={`0 0 ${ancho} ${alto}`} className="overflow-visible">
          <line x1="0" x2={ancho} y1={alto} y2={alto} className="stroke-linea" strokeWidth="1" />
          {historial.map((v, i) => {
            const h = Math.max(2, (v / 100) * (alto - 2))
            const hoy = i === historial.length - 1
            return (
              <rect
                key={i}
                x={i * paso + 1}
                y={alto - h}
                width={paso - 2}
                height={h}
                rx="1.5"
                className={hoy ? 'fill-tinta' : 'fill-tinta-2/45'}
              >
                <title>{hoy ? `Hoy: ${v}` : `Hace ${historial.length - 1 - i} días: ${v}`}</title>
              </rect>
            )
          })}
        </svg>
        <span className="text-sm leading-none text-tinta-2">
          <span className="font-cond text-xl font-semibold tabular-nums text-tinta">{energia}</span>/100
        </span>
      </div>
    </div>
  )
}

interface PropsVista {
  avatar: Avatar
  size?: Tamano
  consultando?: boolean
}

export function etiquetaGemelo(avatar: Avatar, consultando = false): string {
  const ev = avatar.estado_visual
  if (consultando) return `Gemelo de ${avatar.nombre}: consultando su aptitud.`
  const motivo = ev.motivo_visible.replace(/\.?$/, '.')
  return `Gemelo de ${avatar.nombre}: ${TEXTO_APTITUD[ev.apto_para_tarea]}. ${motivo} Día ${ev.dia_rotacion} de ${ev.total_rotacion} de la rotación, exposición ${ev.exposicion_nivel}, energía ${ev.energia} de 100.`
}

// Lo que el gemelo dice en texto, siempre visible además del color: aptitud, rotación, exposición, energía y motivo.
export function InfoGemelo({ avatar, consultando = false, lg = false }: { avatar: Avatar; consultando?: boolean; lg?: boolean }) {
  const ev = avatar.estado_visual
  const nivel = consultando ? null : NIVEL_DE_APTITUD[ev.apto_para_tarea]
  const colorTexto = nivel ? CLASES_NIVEL[nivel].texto : 'text-tinta-2'
  const chips = [`Día ${ev.dia_rotacion} de ${ev.total_rotacion}`, `Exposición: ${ev.exposicion_nivel}`]
  return (
    <div className={`min-w-0 space-y-2 ${lg ? 'flex flex-col items-center' : ''}`}>
      <p className="leading-tight">
        <span className={`block font-cond font-semibold ${lg ? 'text-3xl' : 'text-xl'}`}>{avatar.nombre}</span>
        <span className="text-sm text-tinta-2">
          {avatar.cargo}, {avatar.empresa}
        </span>
      </p>
      <p className={`font-cond font-semibold ${lg ? 'text-2xl' : 'text-lg'} ${colorTexto}`}>
        {consultando ? 'Consultando al gemelo…' : TEXTO_APTITUD[ev.apto_para_tarea]}
      </p>
      {!consultando && (
        <>
          <ul className={`flex flex-wrap gap-1.5 ${lg ? 'justify-center' : ''}`}>
            {chips.map((c) => (
              <li key={c} className="rounded-sm border border-linea bg-superficie-2 px-2 py-0.5 text-sm">
                {c}
              </li>
            ))}
          </ul>
          <Energia historial={ev.historial_energia} energia={ev.energia} ancho={lg ? 154 : 98} />
          <p className={`text-sm text-tinta-2 ${lg ? 'max-w-xs' : ''}`}>{ev.motivo_visible}</p>
        </>
      )}
    </div>
  )
}

export function AvatarGemeloVista({ avatar, size = 'md', consultando = false }: PropsVista) {
  const ev = avatar.estado_visual
  const nivel = consultando ? null : NIVEL_DE_APTITUD[ev.apto_para_tarea]
  const colorTexto = nivel ? CLASES_NIVEL[nivel].texto : 'text-tinta-2'
  const etiqueta = etiquetaGemelo(avatar, consultando)
  const figura = (
    <div className={`${ANCHO[size]} shrink-0`}>
      <FiguraMinero avatar={avatar} consultando={consultando} />
    </div>
  )

  if (size === 'sm') {
    return (
      <div role="img" aria-label={etiqueta} className="flex w-16 shrink-0 flex-col items-center gap-0.5">
        {figura}
        <span className={`text-center text-xs font-semibold leading-tight ${colorTexto}`}>
          {consultando ? '…' : CORTO[ev.apto_para_tarea]}
        </span>
      </div>
    )
  }

  const lg = size === 'lg'
  return (
    <div
      role="img"
      aria-label={etiqueta}
      className={lg ? 'flex flex-col items-center gap-3 text-center' : 'flex items-start gap-4'}
    >
      {figura}
      <InfoGemelo avatar={avatar} consultando={consultando} lg={lg} />
    </div>
  )
}

interface Props {
  trabajadorId: string | undefined
  size?: Tamano
  consultando?: boolean
}

export function AvatarGemelo({ trabajadorId, size = 'md', consultando = false }: Props) {
  const { data, isError } = useAvatar(trabajadorId)
  if (data) return <AvatarGemeloVista avatar={data} size={size} consultando={consultando} />
  return (
    <div
      role="img"
      aria-label={isError ? 'Gemelo no disponible' : 'Cargando gemelo'}
      className={`${ANCHO[size]} aspect-square shrink-0 rounded-full border-4 border-dashed border-linea`}
    />
  )
}
