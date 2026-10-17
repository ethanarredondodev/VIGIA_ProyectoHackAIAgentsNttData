import { useMutation, useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { iniciar, reportar, usePtw } from '../api'
import { AvatarGemelo } from '../componentes/AvatarGemelo'
import PedidoActividad from '../componentes/PedidoActividad'
import type { PerfilTrabajador } from '../pedido'
import { useSesion } from '../sesion'
import { IconoEstado } from '../componentes/Sello'
import { TEXTO_APTITUD, TEXTO_RESULTADO, textoVentilacion } from '../negocio'
import type { Ptw, ResultadoTarea } from '../tipos'

// Si el archivo del 3D no descarga (mala señal o un despliegue nuevo), queda el gemelo 2D.
const AvatarGemelo3D = lazy(() =>
  import('../componentes/AvatarGemelo3D').catch(() => ({
    default: ({ trabajadorId }: { trabajadorId: string }) => <AvatarGemelo trabajadorId={trabajadorId} size="md" />,
  })),
)

// Perfil del trabajador con sesión iniciada: lo que no pregunta el formulario.
const PERFIL: PerfilTrabajador = {
  trabajador_id: 'T-001',
  altitud_msnm: 4210,
  tipo_mineria: 'subterranea',
  empleador: 'contratista',
}

const BOTON =
  'flex min-h-16 w-full items-center justify-center rounded-md bg-azurita px-5 font-cond text-2xl font-semibold text-sobre-azurita disabled:opacity-40'
const BOTON_SECUNDARIO =
  'flex min-h-14 w-full items-center justify-center rounded-md border-2 border-tinta px-5 font-cond text-xl font-semibold'
const OPCION =
  'flex min-h-14 cursor-pointer items-center gap-3 rounded-md border-2 border-linea bg-superficie px-4 has-[:checked]:border-azurita has-[:checked]:bg-azurita/10'
const RADIO = 'size-6 shrink-0 accent-[var(--azurita)]'

export default function Trabajador() {
  const [ptwId, setPtwId] = useState<string | null>(null)
  const ptw = usePtw(ptwId)
  // El admin también puede abrir esta vista: ve la de Juan.
  const { usuario } = useSesion()
  const perfil = { ...PERFIL, trabajador_id: usuario?.trabajadorId ?? PERFIL.trabajador_id }

  return (
    <main className="mx-auto max-w-lg space-y-6 px-4 pb-16 pt-5 text-lg">
      <section aria-labelledby="t-gemelo" className="rounded-md bg-superficie p-4">
        <h1 id="t-gemelo" className="mb-3 font-cond text-xl font-semibold text-tinta-2">
          Tu gemelo hoy
        </h1>
        <Suspense fallback={<AvatarGemelo trabajadorId={perfil.trabajador_id} size="md" />}>
          <AvatarGemelo3D key={perfil.trabajador_id} trabajadorId={perfil.trabajador_id} />
        </Suspense>
      </section>

      {!ptwId ? (
        <PedidoActividad
          perfil={perfil}
          onCreado={setPtwId}
        />
      ) : ptw.data ? (
        <Seguimiento key={ptwId} ptw={ptw.data} onNuevo={() => setPtwId(null)} />
      ) : ptw.isError ? (
        <p role="alert" className="rounded-md border-l-4 border-rojo bg-superficie p-4">
          No se pudo leer tu permiso. Revisa tu señal; Vigía lo vuelve a intentar.
        </p>
      ) : (
        <p className="text-tinta-2">Abriendo tu permiso…</p>
      )}
    </main>
  )
}

const CONSULTAS = ['incidentes', 'area', 'gemelo'] as const
type Clave = (typeof CONSULTAS)[number]

const TITULO: Record<Clave, string> = {
  incidentes: 'Historial de incidentes',
  area: 'Condiciones de la labor',
  gemelo: 'Tu gemelo digital',
}

function resumen(k: Clave, ptw: Ptw): string {
  const c = ptw.consultas
  if (c[k].estado === 'error') return 'No respondió. Tu supervisor lo tendrá en cuenta.'
  if (k === 'incidentes' && c.incidentes.data) {
    const n = c.incidentes.data.casos_similares
    return n === 0 ? 'Sin casos parecidos en esta labor.' : `${n} casos parecidos en labores como esta.`
  }
  if (k === 'area' && c.area.data) {
    const a = c.area.data
    return `O₂ ${a.o2_pct} %, CO ${a.co_ppm} ppm, ventilación ${textoVentilacion(a.ventilacion).toLowerCase()}.`
  }
  if (k === 'gemelo' && c.gemelo.data) return TEXTO_APTITUD[c.gemelo.data.apto_para_tarea]
  return ''
}

// Las consultas aparecen una por una aunque lleguen en la misma lectura.
function useRevelado(ptw: Ptw): Clave[] {
  const [vistas, setVistas] = useState<Clave[]>([])
  const siguiente = CONSULTAS.find((k) => ptw.consultas[k].estado !== 'pendiente' && !vistas.includes(k))
  useEffect(() => {
    if (!siguiente) return
    const t = setTimeout(() => setVistas((v) => [...v, siguiente]), vistas.length ? 600 : 0)
    return () => clearTimeout(t)
  }, [siguiente, vistas.length])
  return vistas
}

function Seguimiento({ ptw, onNuevo }: { ptw: Ptw; onNuevo: () => void }) {
  const vistas = useRevelado(ptw)
  if (ptw.estado === 'procesando' || vistas.length < CONSULTAS.length) return <Procesando ptw={ptw} vistas={vistas} />
  switch (ptw.estado) {
    case 'emitido':
    case 'autorizado_con_controles':
    case 'en_ejecucion':
      return <PermisoListo ptw={ptw} />
    case 'en_revision':
      return (
        <Aviso borde="border-ambar" titulo="Tu supervisor está revisando" vivo>
          <p>Hay condiciones que necesitan otra mirada. No empieces todavía: aquí verás su respuesta.</p>
          {ptw.propuesta?.requiere_supervisor && <p>Es un trabajo de alto riesgo y siempre lleva su firma.</p>}
          <Esperando texto="Esperando la firma" />
        </Aviso>
      )
    case 'bloqueado':
      return (
        <Aviso borde="border-rojo" titulo="Esta tarea está bloqueada">
          <p className="text-xl">{ptw.propuesta?.porque[0]}</p>
          {ptw.propuesta?.alternativa && (
            <div className="rounded-md bg-superficie-2 p-4">
              <h3 className="font-semibold">Qué hacer ahora</h3>
              <p>{ptw.propuesta.alternativa}</p>
            </div>
          )}
          <button type="button" className={BOTON_SECUNDARIO} onClick={onNuevo}>
            Pedir otro permiso
          </button>
        </Aviso>
      )
    case 'rechazado':
      return (
        <Aviso borde="border-rojo" titulo="Tu supervisor no autorizó la tarea">
          <p>No empieces. Habla con tu supervisor antes de continuar.</p>
          <button type="button" className={BOTON_SECUNDARIO} onClick={onNuevo}>
            Pedir otro permiso
          </button>
        </Aviso>
      )
    case 'cerrado':
      return (
        <Aviso borde="border-verde" titulo="Reporte enviado">
          <p>Gracias. Buen regreso a casa.</p>
          <button type="button" className={BOTON_SECUNDARIO} onClick={onNuevo}>
            Pedir otro permiso
          </button>
        </Aviso>
      )
  }
}

function Aviso({
  borde,
  titulo,
  vivo = false,
  children,
}: {
  borde: string
  titulo: string
  vivo?: boolean
  children: ReactNode
}) {
  return (
    <section aria-live={vivo ? 'polite' : undefined} className={`space-y-4 rounded-md border-t-8 bg-superficie p-5 ${borde}`}>
      <h2 className="font-cond text-3xl font-bold">{titulo}</h2>
      {children}
    </section>
  )
}

function Esperando({ texto }: { texto: string }) {
  return (
    <p className="flex items-center gap-3 text-tinta-2">
      <span className="size-3 rounded-full bg-azurita motion-safe:animate-latido" aria-hidden="true" />
      {texto}…
    </p>
  )
}

function Procesando({ ptw, vistas }: { ptw: Ptw; vistas: Clave[] }) {
  const faltan = CONSULTAS.length - vistas.length
  return (
    <section aria-labelledby="t-proc" className="space-y-4">
      <div>
        <h2 id="t-proc" className="font-cond text-3xl font-bold">
          Revisando tu permiso
        </h2>
        <p className="text-tinta-2">Vigía consulta tres fuentes antes de decidir.</p>
      </div>
      <ol aria-live="polite" className="space-y-3">
        {vistas.map((k) => {
          const error = ptw.consultas[k].estado === 'error'
          return (
            <li
              key={k}
              className={`flex gap-3 rounded-md border-l-4 bg-superficie p-4 motion-safe:animate-aparecer ${
                error ? 'border-rojo' : 'border-azurita'
              }`}
            >
              <IconoEstado icono={error ? 'equis' : 'check'} className={`mt-1 size-6 ${error ? 'text-rojo-texto' : ''}`} />
              <div>
                <p className="font-semibold">{TITULO[k]}</p>
                <p className="text-base text-tinta-2">{resumen(k, ptw)}</p>
              </div>
            </li>
          )
        })}
      </ol>
      {faltan > 0 ? (
        <Esperando texto={faltan === 1 ? 'Falta una consulta' : `Faltan ${faltan} consultas`} />
      ) : (
        <Esperando texto="Calculando el riesgo" />
      )}
    </section>
  )
}

function PermisoListo({ ptw }: { ptw: Ptw }) {
  const [marcados, setMarcados] = useState<Set<number>>(new Set())
  const qc = useQueryClient()
  const empezar = useMutation({
    mutationFn: () => iniciar(ptw.ptw_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ptw', ptw.ptw_id] }),
  })
  const petar = ptw.petar
  if (!petar) return <Aviso borde="border-rojo" titulo="Falta el documento PETAR">Pide ayuda a tu supervisor.</Aviso>
  if (ptw.estado === 'en_ejecucion') return <Reporte ptw={ptw} />

  const extra = new Set(ptw.propuesta?.controles_extra)
  const conControles = ptw.estado === 'autorizado_con_controles'
  const completo = marcados.size === petar.checklist.length
  const alternar = (i: number) =>
    setMarcados((m) => {
      const n = new Set(m)
      if (n.has(i)) n.delete(i)
      else n.add(i)
      return n
    })

  return (
    <article
      aria-labelledby="t-petar"
      className={`space-y-5 rounded-md border-t-8 bg-superficie p-5 ${conControles ? 'border-ambar' : 'border-verde'}`}
    >
      <header>
        <h2 id="t-petar" className="font-cond text-2xl font-semibold">
          {conControles ? 'Autorizado por tu supervisor' : 'Permiso emitido'}
        </h2>
        <p className="font-cond text-4xl font-bold tabular-nums tracking-tight">{petar.numero}</p>
        <p className="text-base text-tinta-2">
          {petar.firmado_por ? `Firmado por ${petar.firmado_por}` : 'Emitido automáticamente por Vigía'}
        </p>
      </header>

      <fieldset>
        <legend className="mb-1 font-semibold">Marca cada control antes de empezar</legend>
        <ul className="divide-y divide-linea">
          {petar.checklist.map((c, i) => (
            <li key={c}>
              <label className="flex min-h-14 cursor-pointer items-start gap-4 py-3">
                <input
                  type="checkbox"
                  checked={marcados.has(i)}
                  onChange={() => alternar(i)}
                  className="mt-0.5 size-7 shrink-0 accent-[var(--azurita)]"
                />
                <span>
                  {c}
                  {extra.has(c) && (
                    <span className="ml-2 inline-block rounded-sm bg-ambar px-1.5 font-cond text-sm font-semibold text-sobre-ambar">
                      Control extra
                    </span>
                  )}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>

      <p aria-live="polite" className="text-tinta-2">
        {marcados.size} de {petar.checklist.length} controles marcados
      </p>
      {empezar.isError && (
        <p role="alert" className="rounded-md border-l-4 border-rojo bg-superficie-2 p-4">
          No se registró el inicio. Revisa tu señal y vuelve a intentarlo.
        </p>
      )}
      <button type="button" className={BOTON} disabled={!completo || empezar.isPending} onClick={() => empezar.mutate()}>
        {empezar.isPending ? 'Registrando…' : 'Empezar trabajo'}
      </button>
    </article>
  )
}

function Reporte({ ptw }: { ptw: Ptw }) {
  const [resultado, setResultado] = useState<ResultadoTarea>('sin_novedad')
  const [cumplidos, setCumplidos] = useState<boolean | null>(null)
  const [observacion, setObservacion] = useState('')
  const qc = useQueryClient()
  const enviar = useMutation({
    mutationFn: () =>
      reportar(ptw.ptw_id, { resultado, controles_cumplidos: cumplidos!, observacion: observacion.trim() }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ptw', ptw.ptw_id] }),
  })

  return (
    <form
      aria-labelledby="t-reporte"
      className="space-y-6 rounded-md bg-superficie p-5"
      onSubmit={(e) => {
        e.preventDefault()
        if (cumplidos !== null) enviar.mutate()
      }}
    >
      <div>
        <h2 id="t-reporte" className="font-cond text-3xl font-bold">
          Reporte al terminar
        </h2>
        <p className="text-tinta-2">{ptw.petar?.numero}</p>
      </div>

      <fieldset className="space-y-2">
        <legend className="mb-2 font-semibold">¿Cómo terminó el trabajo?</legend>
        {(Object.keys(TEXTO_RESULTADO) as ResultadoTarea[]).map((r) => (
          <label key={r} className={OPCION}>
            <input type="radio" name="resultado" className={RADIO} checked={resultado === r} onChange={() => setResultado(r)} />
            {TEXTO_RESULTADO[r]}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend className="mb-2 font-semibold">¿Cumpliste todos los controles?</legend>
        <div className="grid grid-cols-2 gap-2">
          {[true, false].map((v) => (
            <label key={String(v)} className={OPCION}>
              <input type="radio" name="cumplidos" className={RADIO} checked={cumplidos === v} onChange={() => setCumplidos(v)} />
              {v ? 'Sí' : 'No'}
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <label htmlFor="observacion" className="mb-2 block font-semibold">
          Observación <span className="font-normal text-tinta-2">(opcional)</span>
        </label>
        <textarea
          id="observacion"
          rows={3}
          value={observacion}
          onChange={(e) => setObservacion(e.target.value)}
          className="w-full rounded-md border-2 border-linea bg-superficie-2 p-3"
        />
      </div>

      {enviar.isError && (
        <p role="alert" className="rounded-md border-l-4 border-rojo bg-superficie-2 p-4">
          No se envió el reporte. Revisa tu señal y vuelve a enviarlo.
        </p>
      )}
      <button type="submit" className={BOTON} disabled={cumplidos === null || enviar.isPending}>
        {enviar.isPending ? 'Enviando…' : 'Enviar reporte'}
      </button>
    </form>
  )
}
