import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { crearSolicitud, useAvatar, usePtw, usePtwLista } from '../api'
import { FichasNanda, NivelFinal, RespuestasAgentes } from '../componentes/admin/Paneles'
import { ListaEtapas, SalaControl } from '../componentes/admin/SalaControl'
import { SelloNivel } from '../componentes/Sello'
import { capitalizar, haceCuanto, TEXTO_TURNO } from '../negocio'
import { useSala } from '../sala'
import type { Solicitud } from '../tipos'

// El caso guionado de Juan en la base de datos: perforación de frente en TJ-12, turno noche.
const SOLICITUD_DEMO: Solicitud = {
  tarea: 'Perforación de frente',
  labor: 'NV-3820 TJ-12',
  turno: 'noche',
  trabajador_id: 'T-001',
  altitud_msnm: 4210,
  tipo_mineria: 'subterranea',
  empleador: 'contratista',
}

function useMedia(consulta: string) {
  const [coincide, setCoincide] = useState(() => window.matchMedia?.(consulta).matches ?? true)
  useEffect(() => {
    const medio = window.matchMedia?.(consulta)
    if (!medio) return
    const cambiar = () => setCoincide(medio.matches)
    medio.addEventListener?.('change', cambiar)
    return () => medio.removeEventListener?.('change', cambiar)
  }, [consulta])
  return coincide
}

export default function Admin() {
  const [params, setParams] = useSearchParams()
  const lista = usePtwLista()
  const ptwId = params.get('ptw') ?? lista.data?.[0]?.ptw_id ?? null
  const { data: ptw, isError } = usePtw(ptwId)
  const { data: avatar } = useAvatar(ptw?.solicitud.trabajador_id)
  const sala = useSala(ptw)
  const ancho = useMedia('(min-width: 1024px)')
  const animar = !useMedia('(prefers-reduced-motion: reduce)')
  const qc = useQueryClient()

  // Cuando responde el gemelo, el avatar se vuelve a pedir para reflejar su estado de hoy.
  const trabajadorId = ptw?.solicitud.trabajador_id
  const gemeloListo = ptw?.consultas.gemelo.estado === 'ok'
  useEffect(() => {
    if (gemeloListo) qc.invalidateQueries({ queryKey: ['avatar', trabajadorId] })
  }, [gemeloListo, trabajadorId, qc])

  const elegir = (id: string) => {
    params.set('ptw', id)
    setParams(params)
  }
  const demo = useMutation({ mutationFn: () => crearSolicitud(SOLICITUD_DEMO), onSuccess: ({ ptw_id }) => elegir(ptw_id) })

  return (
    <main className="mx-auto max-w-[110rem] px-4 py-6 xl:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-cond text-4xl font-bold xl:text-5xl">Sala de control</h1>
          <p className="text-lg text-tinta-2">
            {ptw
              ? `${ptw.ptw_id}: ${ptw.solicitud.tarea} en ${ptw.solicitud.labor}, turno ${TEXTO_TURNO[ptw.solicitud.turno].toLowerCase()}`
              : 'Esperando una solicitud'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => demo.mutate()}
          disabled={demo.isPending}
          className="min-h-12 rounded-md bg-azurita px-5 font-cond text-xl font-semibold text-sobre-azurita disabled:opacity-40"
        >
          {demo.isPending ? 'Enviando…' : 'Nueva solicitud de demo'}
        </button>
      </header>

      {!!lista.data?.length && (
        <nav aria-label="Solicitudes recientes" className="mt-4 flex gap-2 overflow-x-auto pb-2">
          {lista.data.slice(0, 10).map((item) => (
            <button
              key={item.ptw_id}
              type="button"
              aria-current={item.ptw_id === ptwId || undefined}
              onClick={() => elegir(item.ptw_id)}
              className="min-w-48 shrink-0 rounded-md border-2 border-linea bg-superficie px-3 py-2 text-left aria-[current]:border-azurita"
            >
              <span className="block truncate font-semibold">{capitalizar(item.solicitud.tarea)}</span>
              <span className="block text-sm text-tinta-2">
                {item.solicitud.labor}
                {item.creado_en ? `, ${haceCuanto(item.creado_en)}` : ''}
              </span>
              {item.propuesta && (
                <span className="mt-1 block">
                  <SelloNivel nivel={item.propuesta.nivel} altoRiesgo={item.propuesta.requiere_supervisor} />
                </span>
              )}
            </button>
          ))}
        </nav>
      )}

      {!ptwId ? (
        <p className="mt-6 rounded-md border-2 border-dashed border-linea p-8 text-lg text-tinta-2">
          Aún no hay solicitudes. Inicia una solicitud de demo o pide un permiso desde la vista del trabajador.
        </p>
      ) : isError ? (
        <p role="alert" className="mt-6 rounded-md border-l-4 border-rojo bg-superficie p-6 text-lg">
          No se encontró el PETAR {ptwId}. Elige otra solicitud o inicia una de demo.
        </p>
      ) : ptw ? (
        <>
          <section aria-label="Recorrido de la solicitud" className="mt-4">
            {ancho ? <SalaControl ptw={ptw} avatar={avatar} sala={sala} animar={animar} /> : <ListaEtapas ptw={ptw} avatar={avatar} sala={sala} />}
            <p className="mt-2 text-tinta-2">Pasa el mouse o toca cualquier etapa para ver en vivo lo que está procesando.</p>
          </section>
          <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_1fr_1.3fr]">
            <NivelFinal ptw={ptw} />
            <FichasNanda ptw={ptw} />
            <RespuestasAgentes ptw={ptw} />
          </div>
        </>
      ) : (
        <p className="mt-6 text-tinta-2">Cargando {ptwId}…</p>
      )}
    </main>
  )
}
