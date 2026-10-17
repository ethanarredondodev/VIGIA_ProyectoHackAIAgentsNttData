import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { firmar, useAvatar, useBandeja, usePtw, usePtwLista } from '../api'
import { AvatarGemelo } from '../componentes/AvatarGemelo'
import { useSesion } from '../sesion'
import { IconoEstado, ICONO_NIVEL, SelloNivel } from '../componentes/Sello'
import {
  capitalizar,
  CLASES_NIVEL,
  haceCuanto,
  NIVEL_DE_RESULTADO,
  separarBandeja,
  TEXTO_DECISION,
  TEXTO_ESTADO,
  TEXTO_RESULTADO,
  TEXTO_TURNO,
  textoClave,
  textoVentilacion,
} from '../negocio'
import type { AccionFirma, ItemBandeja, Ptw } from '../tipos'

const BOTON = 'min-h-12 rounded-md px-5 font-cond text-lg font-semibold disabled:opacity-40'

export default function Supervisor() {
  const bandeja = useBandeja()
  const ptws = usePtwLista()
  const [pestana, setPestana] = useState<ItemBandeja['tipo'] | 'reportes'>('revision')
  const [seleccion, setSeleccion] = useState<string | null>(null)
  const { porRevisar, avisos } = separarBandeja(bandeja.data ?? [])
  const reportes = (ptws.data ?? [])
    .filter((p) => p.estado === 'cerrado')
    .sort((a, b) => (b.cerrado_en ?? '').localeCompare(a.cerrado_en ?? ''))
  const lista = pestana === 'revision' ? porRevisar : avisos
  const pestanas = [
    { id: 'revision' as const, texto: 'Por revisar', n: porRevisar.length },
    { id: 'aviso' as const, texto: 'Avisos', n: avisos.length },
    { id: 'reportes' as const, texto: 'Reportes', n: reportes.filter((r) => r.resultado && r.resultado.resultado !== 'sin_novedad').length },
  ]

  return (
    <main className="mx-auto max-w-7xl gap-8 px-4 py-6 lg:grid lg:grid-cols-[minmax(20rem,26rem)_1fr]">
      <section aria-labelledby="t-bandeja" className={seleccion ? 'hidden lg:block' : ''}>
        <h1 id="t-bandeja" className="font-cond text-3xl font-bold">
          Bandeja
        </h1>
        <p className="mt-1 text-tinta-2">Los casos verdes se emiten solos y no llegan aquí.</p>

        <div role="tablist" aria-label="Bandeja" className="mt-5 flex gap-1 border-b-2 border-linea">
          {pestanas.map((p) => (
            <button
              key={p.id}
              id={`tab-${p.id}`}
              type="button"
              role="tab"
              aria-selected={pestana === p.id}
              aria-controls="panel-bandeja"
              onClick={() => setPestana(p.id)}
              className={`-mb-0.5 flex min-h-12 items-center gap-2 border-b-[3px] px-3 font-semibold ${
                pestana === p.id ? 'border-azurita text-tinta' : 'border-transparent text-tinta-2 hover:text-tinta'
              }`}
            >
              {p.texto}
              <span className="rounded-sm bg-superficie-2 px-1.5 font-cond tabular-nums">{p.n}</span>
            </button>
          ))}
        </div>

        <div id="panel-bandeja" role="tabpanel" aria-labelledby={`tab-${pestana}`} aria-live="polite">
          {pestana === 'reportes' ? (
            <Reportes reportes={reportes} estado={ptws.status} />
          ) : bandeja.isPending ? (
            <p className="py-6 text-tinta-2">Cargando la bandeja…</p>
          ) : bandeja.isError ? (
            <p role="alert" className="py-6">
              No se pudo cargar la bandeja. Vigía lo vuelve a intentar en unos segundos.
            </p>
          ) : lista.length === 0 ? (
            <p className="py-6 text-tinta-2">
              {pestana === 'revision'
                ? 'No hay casos por revisar. Los nuevos aparecerán aquí.'
                : 'No hay tareas bloqueadas.'}
            </p>
          ) : (
            <ul className="divide-y divide-linea">
              {lista.map((item) => (
                <FilaBandeja
                  key={item.ptw_id}
                  item={item}
                  elegida={seleccion === item.ptw_id}
                  onElegir={() => setSeleccion(item.ptw_id)}
                />
              ))}
            </ul>
          )}
        </div>
      </section>

      <section aria-label="Detalle del caso" className={seleccion ? '' : 'hidden lg:block'}>
        {seleccion ? (
          <DetalleCaso ptwId={seleccion} onVolver={() => setSeleccion(null)} />
        ) : (
          <p className="rounded-md border-2 border-dashed border-linea p-8 text-tinta-2">
            Elige un caso de la bandeja para ver por qué llegó y firmarlo.
          </p>
        )}
      </section>
    </main>
  )
}

function FilaBandeja({ item, elegida, onElegir }: { item: ItemBandeja; elegida: boolean; onElegir: () => void }) {
  // La bandeja no trae el id del trabajador: se lee del PETAR (queda en caché para el detalle).
  const ptw = usePtw(item.ptw_id, false)
  return (
    <li>
      <button
        type="button"
        onClick={onElegir}
        aria-current={elegida || undefined}
        className={`flex w-full items-start gap-3 px-2 py-3 text-left hover:bg-superficie-2 ${
          elegida ? 'bg-superficie shadow-[inset_4px_0_0_var(--azurita)]' : ''
        }`}
      >
        <AvatarGemelo trabajadorId={ptw.data?.solicitud.trabajador_id} size="sm" />
        <span className="min-w-0 flex-1 space-y-0.5">
          <span className="block font-semibold">{item.trabajador_nombre}</span>
          <span className="block">{capitalizar(item.tarea)}</span>
          <span className="block text-sm text-tinta-2">
            {item.labor}, turno {TEXTO_TURNO[item.turno].toLowerCase()}, {haceCuanto(item.creado_en)}
          </span>
          <span className="block pt-1">
            <SelloNivel nivel={item.nivel} altoRiesgo={item.requiere_supervisor} />
          </span>
        </span>
      </button>
    </li>
  )
}

function Reportes({ reportes, estado }: { reportes: Ptw[]; estado: 'pending' | 'error' | 'success' }) {
  if (estado === 'pending') return <p className="py-6 text-tinta-2">Cargando los reportes…</p>
  if (estado === 'error')
    return (
      <p role="alert" className="py-6">
        Vigía no pudo cargar los reportes. Lo vuelve a intentar en unos segundos.
      </p>
    )
  if (reportes.length === 0) return <p className="py-6 text-tinta-2">Todavía no hay reportes de tareas cerradas.</p>
  return (
    <ul className="divide-y divide-linea">
      {reportes.map((ptw) => (
        <FilaReporte key={ptw.ptw_id} ptw={ptw} />
      ))}
    </ul>
  )
}

// Si el backend aún no envía el reporte, la tarea cerrada aparece sin su detalle.
function FilaReporte({ ptw }: { ptw: Ptw }) {
  const { solicitud: s, resultado: r } = ptw
  const { data: avatar } = useAvatar(s.trabajador_id)
  return (
    <li className="flex items-start gap-3 px-2 py-3">
      <AvatarGemelo trabajadorId={s.trabajador_id} size="sm" />
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="font-semibold">{avatar?.nombre ?? s.trabajador_id}</p>
        <p>{capitalizar(s.tarea)}</p>
        <p className="text-sm text-tinta-2">
          {s.labor}
          {ptw.cerrado_en && `, ${haceCuanto(ptw.cerrado_en)}`}
        </p>
        {r ? (
          <>
            <p className="pt-1">
              <span
                className={`inline-flex items-center gap-1 rounded-sm px-2 py-0.5 font-cond text-sm font-semibold ${CLASES_NIVEL[NIVEL_DE_RESULTADO[r.resultado]].relleno}`}
              >
                <IconoEstado icono={ICONO_NIVEL[NIVEL_DE_RESULTADO[r.resultado]]} className="size-3.5" />
                {TEXTO_RESULTADO[r.resultado]}
              </span>
            </p>
            <p className="text-sm">Controles cumplidos: {r.controles_cumplidos ? 'Sí' : 'No'}</p>
            <p className="text-sm">{r.observacion}</p>
          </>
        ) : (
          <p className="text-sm text-tinta-2">Sin reporte del trabajador.</p>
        )}
      </div>
    </li>
  )
}

function Bloque({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="rounded-md bg-superficie p-5">
      <h3 className="mb-3 font-cond text-xl font-semibold">{titulo}</h3>
      {children}
    </section>
  )
}

export function DetalleCaso({ ptwId, onVolver }: { ptwId: string; onVolver?: () => void }) {
  const { data: ptw, isPending, isError } = usePtw(ptwId)
  if (isPending) return <p className="text-tinta-2">Cargando el caso…</p>
  if (isError) return <p role="alert">No se pudo cargar el caso {ptwId}.</p>

  const { solicitud: s, propuesta: p, consultas: c } = ptw
  const area = c.area.data
  const incidentes = c.incidentes.data

  return (
    <article aria-labelledby="t-caso" className="space-y-4">
      {onVolver && (
        <button type="button" onClick={onVolver} className={`${BOTON} border-2 border-linea lg:hidden`}>
          Volver a la bandeja
        </button>
      )}

      <header className="grid gap-5 rounded-md bg-superficie p-5 md:grid-cols-[1fr_auto]">
        <AvatarGemelo trabajadorId={s.trabajador_id} size="md" />
        <div className="space-y-2 md:max-w-xs">
          <h2 id="t-caso" className="font-cond text-2xl font-bold leading-tight">
            {capitalizar(s.tarea)}
          </h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 text-sm">
            <dt className="text-tinta-2">Labor</dt>
            <dd className="font-semibold">{s.labor}</dd>
            <dt className="text-tinta-2">Turno</dt>
            <dd>{TEXTO_TURNO[s.turno]}</dd>
            <dt className="text-tinta-2">Altitud</dt>
            <dd>{s.altitud_msnm} msnm</dd>
            <dt className="text-tinta-2">Minería</dt>
            <dd>{s.tipo_mineria === 'subterranea' ? 'Subterránea' : 'Tajo abierto'}</dd>
            <dt className="text-tinta-2">Empleador</dt>
            <dd>{capitalizar(s.empleador)}</dd>
          </dl>
          {p && (
            <div className="space-y-1 pt-1">
              <SelloNivel nivel={p.nivel} altoRiesgo={p.requiere_supervisor} />
              <p className="font-semibold">Propuesta: {TEXTO_DECISION[p.decision].toLowerCase()}</p>
            </div>
          )}
        </div>
      </header>

      {p && (
        <Bloque titulo="Por qué llegó aquí">
          <ul className="list-disc space-y-1.5 pl-5">
            {p.porque.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          {ptw.explicacion && (
            <details className="mt-4">
              <summary className="min-h-11 cursor-pointer py-2 font-semibold">Explicación redactada por Vigía</summary>
              <p className="max-w-prose text-tinta-2">{ptw.explicacion}</p>
            </details>
          )}
        </Bloque>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        <Bloque titulo="Casos similares">
          {incidentes ? (
            <>
              <p className="mb-3">{incidentes.patron}</p>
              <ul className="space-y-3">
                {incidentes.casos.map((k) => (
                  <li key={k.id} className="border-l-2 border-linea pl-3 text-sm">
                    <p className="font-semibold">
                      {k.id}, {textoClave(k.riesgo_critico).toLowerCase()}
                    </p>
                    <p>{k.resumen_es}</p>
                    <p className="text-tinta-2">Causa probable: {k.causa_probable}</p>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-tinta-2">El historial de incidentes no respondió.</p>
          )}
        </Bloque>

        <Bloque titulo="Condiciones de la labor">
          {area ? (
            <dl className="grid grid-cols-2 gap-3">
              {[
                ['CO', `${area.co_ppm} ppm`],
                ['O₂', `${area.o2_pct} %`],
                ['Ruido', `${area.ruido_dBA} dBA`],
                ['Ventilación', textoVentilacion(area.ventilacion)],
                ['Último desatado', `hace ${area.ultimo_desatado_h} h`],
              ].map(([nombre, valor]) => (
                <div key={nombre} className="rounded-sm bg-superficie-2 px-3 py-2">
                  <dt className="text-sm text-tinta-2">{nombre}</dt>
                  <dd className="font-cond text-2xl font-semibold tabular-nums">{valor}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-tinta-2">Los sensores de la labor no respondieron.</p>
          )}
        </Bloque>
      </div>

      {p?.nivel === 'rojo' ? (
        <Bloque titulo="Vigía bloqueó esta tarea">
          <p className="mb-3">{p.alternativa}</p>
          <p className="text-tinta-2">Es solo un aviso: no necesitas firmar.</p>
        </Bloque>
      ) : ptw.estado === 'en_revision' && p ? (
        <Decision key={ptw.ptw_id} ptw={ptw} />
      ) : (
        <Bloque titulo={TEXTO_ESTADO[ptw.estado]}>
          {ptw.petar?.firmado_por && (
            <p role="status">
              {ptw.petar.numero} firmado por {ptw.petar.firmado_por}. Ya llegó al trabajador.
            </p>
          )}
        </Bloque>
      )}
    </article>
  )
}

// El checklist base IPERC entra siempre al PETAR; el supervisor decide solo los controles extra.
function Decision({ ptw }: { ptw: Ptw }) {
  const supervisor = useSesion().usuario!.nombre
  const [inicial] = useState(() => (ptw.propuesta?.controles_extra ?? []).map((texto) => ({ texto, incluido: true })))
  const [items, setItems] = useState(inicial)
  const [modo, setModo] = useState<'ver' | 'ajustar' | 'rechazar'>('ver')
  const [nuevo, setNuevo] = useState('')
  const [motivo, setMotivo] = useState('')
  const qc = useQueryClient()
  const firma = useMutation({
    mutationFn: (accion: AccionFirma) =>
      firmar(ptw.ptw_id, {
        accion,
        supervisor,
        // El contrato de firma no tiene campo de motivo: el rechazo lo envía como único control.
        controles_finales:
          accion === 'rechazar' ? [`Motivo del rechazo: ${motivo.trim()}`] : items.filter((i) => i.incluido).map((i) => i.texto),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['bandeja'] })
      qc.invalidateQueries({ queryKey: ['ptw', ptw.ptw_id] })
    },
  })
  const incluidos = items.filter((i) => i.incluido).length

  const agregar = () => {
    const texto = nuevo.trim()
    if (texto && !items.some((i) => i.texto === texto)) setItems([...items, { texto, incluido: true }])
    setNuevo('')
  }

  return (
    <section aria-labelledby="t-decision" className="space-y-4 rounded-md border-t-8 border-ambar bg-superficie p-5">
      {ptw.checklist_base && (
        <div>
          <h3 className="mb-3 font-cond text-xl font-semibold">Checklist base IPERC (va siempre)</h3>
          <ul className="space-y-1.5">
            {ptw.checklist_base.map((texto) => (
              <li key={texto} className="flex items-start gap-3 rounded-sm border-l-4 border-linea py-1.5 pl-3">
                <IconoEstado icono="check" className="mt-1 size-4 text-tinta-2" />
                <span>{texto}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h3 id="t-decision" className="font-cond text-xl font-semibold">
          Controles extra
        </h3>
        <p className="text-sm text-tinta-2">
          Firmas como {supervisor}. El checklist base IPERC va siempre en el PETAR; aquí decides los controles extra que
          propuso Vigía.
        </p>
      </div>

      {items.length === 0 && <p className="text-tinta-2">Vigía no propuso controles extra para este caso.</p>}

      <ul className="space-y-1.5">
        {items.map((item, i) => {
          return (
            <li key={item.texto} className="rounded-sm border-l-4 border-ambar bg-ambar/10 py-1.5 pl-3">
              {modo === 'ajustar' ? (
                <label className="flex min-h-11 cursor-pointer items-start gap-3">
                  <input
                    type="checkbox"
                    checked={item.incluido}
                    onChange={() => setItems(items.map((x, j) => (j === i ? { ...x, incluido: !x.incluido } : x)))}
                    className="mt-0.5 size-5 shrink-0 accent-[var(--azurita)]"
                  />
                  <span className={item.incluido ? '' : 'text-tinta-2 line-through'}>{item.texto}</span>
                </label>
              ) : (
                <p className="flex items-start gap-3">
                  <IconoEstado icono="check" className="mt-1 size-4 text-tinta-2" />
                  <span>{item.texto}</span>
                </p>
              )}
            </li>
          )
        })}
      </ul>

      {modo === 'ajustar' && (
        <div className="flex flex-wrap gap-2">
          <label htmlFor="nuevo-control" className="sr-only">
            Nuevo control
          </label>
          <input
            id="nuevo-control"
            value={nuevo}
            onChange={(e) => setNuevo(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                agregar()
              }
            }}
            placeholder="Agregar un control"
            className="min-h-12 min-w-0 flex-1 rounded-md border-2 border-linea bg-superficie-2 px-3"
          />
          <button type="button" onClick={agregar} className={`${BOTON} border-2 border-linea`}>
            Agregar
          </button>
        </div>
      )}

      {modo === 'rechazar' && (
        <div>
          <label htmlFor="motivo" className="mb-1 block font-semibold">
            Motivo del rechazo
          </label>
          <textarea
            id="motivo"
            rows={3}
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            className="w-full rounded-md border-2 border-linea bg-superficie-2 p-3"
          />
        </div>
      )}

      {firma.isError && (
        <p role="alert" className="border-l-4 border-rojo pl-3">
          No se pudo firmar: {firma.error.message}. Vuelve a intentarlo.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {modo === 'ver' && (
          <>
            <button
              type="button"
              disabled={firma.isPending}
              onClick={() => firma.mutate('aceptar')}
              className={`${BOTON} bg-azurita text-sobre-azurita`}
            >
              Aceptar y firmar
            </button>
            <button type="button" onClick={() => setModo('ajustar')} className={`${BOTON} border-2 border-tinta`}>
              Ajustar
            </button>
            <button type="button" onClick={() => setModo('rechazar')} className={`${BOTON} border-2 border-rojo text-rojo-texto`}>
              Rechazar
            </button>
          </>
        )}
        {modo === 'ajustar' && (
          <button
            type="button"
            disabled={incluidos === 0 || firma.isPending}
            onClick={() => firma.mutate('ajustar')}
            className={`${BOTON} bg-azurita text-sobre-azurita`}
          >
            Firmar con ajustes ({incluidos})
          </button>
        )}
        {modo === 'rechazar' && (
          <button
            type="button"
            disabled={!motivo.trim() || firma.isPending}
            onClick={() => firma.mutate('rechazar')}
            className={`${BOTON} bg-rojo text-sobre-rojo`}
          >
            Confirmar rechazo
          </button>
        )}
        {modo !== 'ver' && (
          <button
            type="button"
            onClick={() => {
              setItems(inicial)
              setMotivo('')
              setModo('ver')
            }}
            className={`${BOTON} text-tinta-2 hover:text-tinta`}
          >
            Cancelar
          </button>
        )}
      </div>
    </section>
  )
}
