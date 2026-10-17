import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { crearSolicitud, interpretarTarea, useActividades, useLabores } from '../api'
import { TEXTO_TURNO } from '../negocio'
import {
  ACTIVIDADES_BASE,
  actividadConfirmada,
  armarSolicitud,
  laborValida,
  OTRA,
  turnoSegunHora,
  type PerfilTrabajador,
} from '../pedido'
import type { Actividad, Turno } from '../tipos'

const CHIP =
  'min-h-14 rounded-md border-2 border-linea bg-superficie-2 px-3 text-left text-base font-semibold aria-pressed:border-azurita aria-pressed:bg-azurita/10'

export default function PedidoActividad({ perfil, onCreado }: { perfil: PerfilTrabajador; onCreado: (ptwId: string) => void }) {
  const [texto, setTexto] = useState('')
  const [leido, setLeido] = useState('')
  const [elegida, setElegida] = useState<Actividad | null>(null)
  const [laborEscrita, setLaborEscrita] = useState('')
  const [turno, setTurno] = useState<Turno>(() => turnoSegunHora())
  const actividades = useActividades()
  const labores = useLabores()

  // Vigía lee el texto cuando el trabajador deja de escribir.
  useEffect(() => {
    const espera = setTimeout(() => setLeido(texto.trim()), 700)
    return () => clearTimeout(espera)
  }, [texto])
  useEffect(() => setElegida(null), [leido])

  // La clave incluye el texto: una respuesta de un texto anterior no se muestra para el actual.
  const lectura = useQuery({
    queryKey: ['interpretar', leido],
    queryFn: () => interpretarTarea(leido),
    enabled: leido.length >= 4,
    retry: false,
    staleTime: Infinity,
  })
  const interp = lectura.data
  const crear = useMutation({ mutationFn: crearSolicitud, onSuccess: (r) => onCreado(r.ptw_id) })

  const actividad = actividadConfirmada(interp, elegida)
  const labor = interp?.labor ?? laborEscrita
  // La lista completa: así el trabajador siempre puede volver a la actividad que propuso Vigía.
  const opciones = actividades.data ?? ACTIVIDADES_BASE
  const preguntar = interp?.actividad && interp.confianza !== 'alta' && !elegida
  const puedePedir =
    !!actividad && laborValida(labor, labores.data) && (actividad.id !== OTRA.id || texto.trim().length >= 3) && !crear.isPending
  const mostrarTarjeta = leido.length >= 4 && (lectura.isFetching || interp || lectura.isError)

  return (
    <form
      aria-labelledby="t-actividad"
      className="space-y-6"
      onSubmit={(e) => {
        e.preventDefault()
        if (puedePedir && actividad) crear.mutate(armarSolicitud({ actividad, texto, labor, turno, interp, perfil }))
      }}
    >
      <div>
        <h2 id="t-actividad" className="font-cond text-3xl font-bold">
          ¿Qué actividad vas a realizar?
        </h2>
        <p id="ayuda-actividad" className="mt-1 text-base text-tinta-2">
          Escribe solo la actividad. No escribas datos de salud: de eso se encarga el área clínica.
        </p>
      </div>
      <textarea
        aria-labelledby="t-actividad"
        aria-describedby="ayuda-actividad"
        rows={3}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        placeholder="Ej.: voy a perforar el frente del TJ-12"
        className="min-h-24 w-full resize-none rounded-md border-2 border-linea bg-superficie p-3 text-xl"
      />

      {mostrarTarjeta && (
        <section aria-live="polite" className="space-y-3 rounded-md border-l-[6px] border-azurita bg-superficie p-4">
          {!interp && !lectura.isError ? (
            <p className="flex items-center gap-2 text-tinta-2">
              <span className="size-2.5 rounded-full bg-azurita motion-safe:animate-latido" aria-hidden="true" />
              Vigía está leyendo…
            </p>
          ) : (
            <>
              {lectura.isError && <p className="text-tinta-2">No pude leer lo que escribiste.</p>}
              {interp && !interp.actividad && <p className="text-tinta-2">No reconocí la actividad.</p>}
              {(actividad || preguntar) && (
                <>
                  <p className="font-semibold text-tinta-2">{preguntar ? '¿Es esto?' : elegida ? 'Elegiste' : 'Vigía entendió'}</p>
                  <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                    <dt className="text-tinta-2">Actividad</dt>
                    <dd className="font-cond text-xl font-bold">{(actividad ?? interp?.actividad)?.actividad}</dd>
                    <dt className="text-tinta-2">Lugar</dt>
                    <dd className="font-cond text-xl font-bold">{labor.trim() || 'Falta la labor'}</dd>
                  </dl>
                  {preguntar && (
                    <button type="button" className={CHIP} onClick={() => setElegida(interp!.actividad)}>
                      Sí, es {interp!.actividad!.actividad.toLowerCase()}
                    </button>
                  )}
                </>
              )}
              <p className="font-semibold">{actividad || preguntar ? '¿No es eso? Elige otra:' : 'Elige la actividad'}</p>
              <div className="flex flex-wrap gap-2">
                {[...opciones, OTRA].map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    aria-pressed={actividad?.id === a.id}
                    className={CHIP}
                    onClick={() => setElegida(a)}
                  >
                    {a.actividad}
                  </button>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {mostrarTarjeta && !lectura.isFetching && !interp?.labor && (
        <div>
          <label htmlFor="labor" className="mb-2 block font-semibold">
            ¿En qué labor?
          </label>
          <input
            id="labor"
            list="labores"
            value={laborEscrita}
            onChange={(e) => setLaborEscrita(e.target.value)}
            autoCapitalize="characters"
            autoComplete="off"
            placeholder="NV-3820 TJ-12"
            className="min-h-14 w-full rounded-md border-2 border-linea bg-superficie px-4 font-cond text-2xl font-semibold tracking-wide"
          />
          <datalist id="labores">
            {labores.data?.map((l) => <option key={l.labor} value={l.labor} />)}
          </datalist>
        </div>
      )}

      <fieldset>
        <legend className="mb-2 font-semibold">Turno (según la hora)</legend>
        <div className="grid grid-cols-2 gap-2">
          {(['dia', 'noche'] as Turno[]).map((t) => (
            <button
              key={t}
              type="button"
              aria-pressed={turno === t}
              onClick={() => setTurno(t)}
              className="min-h-14 rounded-md border-2 border-linea bg-superficie text-lg font-semibold aria-pressed:border-azurita aria-pressed:bg-azurita/10"
            >
              {TEXTO_TURNO[t]}
            </button>
          ))}
        </div>
      </fieldset>

      <p className="text-base text-tinta-2">
        De tu perfil: {perfil.altitud_msnm} msnm, minería {perfil.tipo_mineria === 'subterranea' ? 'subterránea' : 'a tajo abierto'},
        empresa {perfil.empleador}.
      </p>

      {crear.isError && (
        <p role="alert" className="rounded-md border-l-4 border-rojo bg-superficie p-4">
          No se envió tu solicitud. Revisa tu señal y vuelve a pedir el permiso.
        </p>
      )}
      <button
        type="submit"
        disabled={!puedePedir}
        className="flex min-h-16 w-full items-center justify-center rounded-md bg-azurita px-5 font-cond text-2xl font-semibold text-sobre-azurita disabled:opacity-40"
      >
        {crear.isPending ? 'Enviando…' : 'Pedir permiso'}
      </button>
    </form>
  )
}
