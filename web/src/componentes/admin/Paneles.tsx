import { capitalizar, CLASES_NIVEL, TEXTO_DECISION, TEXTO_ESTADO, TEXTO_NIVEL, textoDestino } from '../../negocio'
import type { Ptw } from '../../tipos'
import { IconoEstado, ICONO_NIVEL } from '../Sello'

const CONSULTAS = ['incidentes', 'area', 'gemelo'] as const

// Autoridades que firman las credenciales NANDA de los agentes.
export const EMISORES: Record<string, string> = { 'vigia-sso': 'SSO', 'vigia-salud-ocupacional': 'Salud Ocupacional' }

export const textoCredencial = (f: Ptw['nanda'][number]) =>
  f.firma === 'valida'
    ? `Credencial vigente de ${(f.emisores ?? []).map((e) => EMISORES[e] ?? e).join(' y ') || 'la autoridad'}`
    : `Agente descartado: ${f.motivo ?? 'firma inválida'}`

export function NivelFinal({ ptw }: { ptw: Ptw }) {
  const p = ptw.propuesta
  return (
    <section
      aria-labelledby="t-nivel"
      className={`self-start rounded-lg p-6 transition-colors duration-500 ${
        p ? CLASES_NIVEL[p.nivel].relleno : 'border-2 border-dashed border-linea bg-superficie'
      }`}
    >
      <h2 id="t-nivel" className="text-lg font-semibold">
        Nivel final
      </h2>
      <p className="mt-2 flex items-center gap-3 font-cond text-5xl font-bold leading-none sm:text-7xl">
        {p && <IconoEstado icono={ICONO_NIVEL[p.nivel]} className="size-10 sm:size-14" />}
        {p ? TEXTO_NIVEL[p.nivel] : 'Calculando…'}
      </p>
      {p && (
        <div className="mt-4 space-y-2 text-lg">
          <p className="font-cond text-3xl font-semibold">{TEXTO_DECISION[p.decision]}</p>
          <p>{textoDestino(p)}</p>
        </div>
      )}
      <p className="mt-4 border-t border-current/25 pt-3 text-lg">
        Estado: {TEXTO_ESTADO[ptw.estado]}
        {ptw.petar?.firmado_por ? `, firmado por ${ptw.petar.firmado_por}` : ''}
      </p>
    </section>
  )
}

export function FichasNanda({ ptw }: { ptw: Ptw }) {
  return (
    <section aria-labelledby="t-nanda" className="rounded-lg bg-superficie p-6">
      <h2 id="t-nanda" className="mb-4 font-cond text-2xl font-semibold">
        Fichas NANDA verificadas
      </h2>
      {ptw.nanda.length === 0 ? (
        <p className="text-tinta-2">NANDA aún está verificando las fichas de los agentes.</p>
      ) : (
        <ul className="space-y-3">
          {ptw.nanda.map((f) => {
            const valida = f.firma === 'valida'
            return (
              <li key={f.id} className="rounded-md border border-linea p-3">
                <p className="font-cond text-xl font-semibold">{f.id}</p>
                <ul className="mt-1 flex flex-wrap gap-1.5">
                  {f.capabilities.map((cap) => (
                    <li key={cap} className="rounded-sm bg-superficie-2 px-2 py-0.5 font-mono text-sm">
                      {cap}
                    </li>
                  ))}
                </ul>
                <p className={`mt-2 flex items-start gap-1.5 font-semibold ${valida ? 'text-verde-texto' : 'text-rojo-texto'}`}>
                  <IconoEstado icono={valida ? 'check' : 'equis'} className="mt-1 size-4" />
                  {textoCredencial(f)}
                </p>
                {valida && f.credencial_vence && (
                  <p className="mt-1 text-sm text-tinta-2">Vence el {new Date(f.credencial_vence).toLocaleDateString('es-PE')}</p>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

export function RespuestasAgentes({ ptw }: { ptw: Ptw }) {
  return (
    <section aria-labelledby="t-json" className="min-w-0 rounded-lg bg-superficie p-6">
      <h2 id="t-json" className="mb-4 font-cond text-2xl font-semibold">
        Respuestas de los agentes
      </h2>
      <div className="space-y-4">
        {CONSULTAS.map((k) => (
          <Json key={k} titulo={capitalizar(k === 'area' ? 'área' : k)} ptw={ptw} clave={k} />
        ))}
      </div>
    </section>
  )
}

function Json({ titulo, ptw, clave }: { titulo: string; ptw: Ptw; clave: (typeof CONSULTAS)[number] }) {
  const consulta = ptw.consultas[clave]
  const lineas = JSON.stringify(consulta.data ?? { estado: consulta.estado }, null, 2).split('\n')
  const gemelo = ptw.consultas.gemelo
  return (
    <div>
      <h3 className="mb-1 font-semibold">{titulo}</h3>
      <pre className="max-h-56 overflow-auto rounded-md bg-superficie-2 p-3 font-mono text-[13px] leading-relaxed">
        {lineas.map((l, i) =>
          clave === 'gemelo' && l.includes('"diagnostico"') ? (
            <mark key={i} className="block bg-verde/20 text-tinta">
              {l}
            </mark>
          ) : (
            <span key={i} className="block">
              {l}
            </span>
          ),
        )}
      </pre>
      {consulta.evidencia && (
        <p className="mt-2 flex items-start gap-2 text-sm font-semibold text-verde-texto">
          <IconoEstado icono="check" className="mt-0.5 size-4" />
          Firmada por el agente certificado (sha256 {consulta.evidencia.sha256.slice(0, 12)}…)
        </p>
      )}
      {clave === 'gemelo' && gemelo.estado === 'ok' && (
        <p className={`mt-2 flex items-start gap-2 font-semibold ${gemelo.diagnostico_descartado ? 'text-rojo-texto' : 'text-verde-texto'}`}>
          <IconoEstado icono={gemelo.diagnostico_descartado ? 'alerta' : 'check'} className="mt-1 size-4" />
          {gemelo.diagnostico_descartado
            ? 'El gemelo envió un diagnóstico y Vigía lo descartó sin mostrarlo.'
            : 'El gemelo respondió diagnostico: null. Ningún dato clínico sale de su zona.'}
        </p>
      )}
    </div>
  )
}
