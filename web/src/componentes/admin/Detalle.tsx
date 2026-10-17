import type { ReactNode } from 'react'
import {
  CLASES_NIVEL,
  NIVEL_DE_APTITUD,
  TEXTO_APTITUD,
  TEXTO_DECISION,
  TEXTO_ESTADO,
  TEXTO_NIVEL,
  TEXTO_TRABAJADOR,
  TEXTO_TURNO,
  textoClave,
  textoDestino,
} from '../../negocio'
import { ACTIVIDADES_BASE } from '../../pedido'
import type { Etapa, Fase } from '../../sala'
import type { Avatar, Ptw, ReglaEvaluada } from '../../tipos'
import { textoCredencial } from './Paneles'

export const TITULO_ETAPA: Record<Etapa, string> = {
  trabajador: 'Trabajador',
  ptw: 'Agente PTW',
  nanda: 'NANDA',
  incidentes: 'Incidentes',
  area: 'Área',
  gemelo: 'Gemelo',
  reglas: 'Reglas',
  decision: 'Decisión',
  destino: 'Destino',
}

const TEXTO_FASE: Record<Fase, string> = { espera: 'En espera', proceso: 'Procesando…', listo: 'Listo', error: 'Sin respuesta' }
const COLOR_FASE: Record<Fase, string> = { espera: 'text-tinta-2', proceso: 'text-azurita', listo: 'text-verde-texto', error: 'text-rojo-texto' }
const TEXTO_RESULTADO_REGLA: Record<ReglaEvaluada['resultado'], string> = { ok: '✓ Dentro', ambar: '! Ámbar', rojo: '✕ Rojo' }

const nombreActividad = (id: string | null | undefined) =>
  id === 'otro' ? 'otra actividad' : ACTIVIDADES_BASE.find((a) => a.id === id)?.actividad.toLowerCase()

function Tabla({ filas }: { filas: ReglaEvaluada[] }) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="text-left text-tinta-2">
          <th className="pb-1 pr-2 font-semibold">Dato</th>
          <th className="pb-1 pr-2 font-semibold">Valor</th>
          <th className="pb-1 pr-2 font-semibold">Límite</th>
          <th className="pb-1 font-semibold">Resultado</th>
        </tr>
      </thead>
      <tbody>
        {filas.map((f) => (
          <tr key={f.dato} className="border-t border-linea">
            <td className="py-1 pr-2">{f.dato}</td>
            <td className="py-1 pr-2 font-cond font-semibold">{f.dato === 'Aptitud' ? TEXTO_APTITUD[f.valor as keyof typeof TEXTO_APTITUD] ?? f.valor : f.valor}</td>
            <td className="py-1 pr-2 text-tinta-2">{f.limite ?? '—'}</td>
            <td className="py-1">
              {f.resultado === 'ok' ? (
                <span className="font-semibold text-verde-texto">{TEXTO_RESULTADO_REGLA.ok}</span>
              ) : (
                <span className={`rounded-sm px-1.5 font-semibold ${CLASES_NIVEL[f.resultado].relleno}`}>{TEXTO_RESULTADO_REGLA[f.resultado]}</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const Lista = ({ items }: { items: ReactNode[] }) => (
  <ul className="list-disc space-y-1 pl-5">
    {items.map((item, i) => (
      <li key={i}>{item}</li>
    ))}
  </ul>
)

function contenido(etapa: Etapa, ptw: Ptw, avatar?: Avatar): { rol: string; cuerpo: ReactNode } {
  const s = ptw.solicitud
  const c = ptw.consultas
  const p = ptw.propuesta
  const nombre = avatar?.nombre ?? s.trabajador_id
  switch (etapa) {
    case 'trabajador':
      return {
        rol: avatar ? `${avatar.cargo}, ${s.empleador}` : s.empleador,
        cuerpo: (
          <Lista
            items={[
              `Actividad: ${s.tarea}`,
              `Labor ${s.labor}, turno ${TEXTO_TURNO[s.turno].toLowerCase()}, ${s.altitud_msnm} msnm`,
              c.gemelo.data ? `Su gemelo: ${TEXTO_APTITUD[c.gemelo.data.apto_para_tarea].toLowerCase()}` : 'Su gemelo aún no responde',
            ]}
          />
        ),
      }
    case 'ptw': {
      const interp = s.interpretacion
      const items: ReactNode[] = []
      if (interp) {
        items.push(
          interp.actividad_id
            ? `La IA comparó lo escrito con la tabla y propuso ${nombreActividad(interp.actividad_id) ?? interp.actividad_id} (confianza ${interp.confianza}).`
            : `La IA no reconoció la actividad (confianza ${interp.confianza}).`,
        )
        items.push(
          s.actividad_id === interp.actividad_id ? `${nombre} lo confirmó.` : `${nombre} eligió ${nombreActividad(s.actividad_id) ?? s.tarea}.`,
        )
      } else {
        items.push(`Actividad confirmada por el trabajador: ${s.tarea}.`)
      }
      if (ptw.tipo_tarea) items.push(`Tipo de tarea: ${textoClave(ptw.tipo_tarea).toLowerCase()}${ptw.tipo_labor ? `, en ${textoClave(ptw.tipo_labor).toLowerCase()}` : ''}.`)
      items.push(`Permiso ${ptw.ptw_id}.`)
      return { rol: 'Orquesta el permiso', cuerpo: <Lista items={items} /> }
    }
    case 'nanda':
      return {
        rol: 'Verifica a quién consultar',
        cuerpo: ptw.nanda.length ? <Lista items={ptw.nanda.map((f) => `${f.id}: ${textoCredencial(f).toLowerCase()}`)} /> : <p>Buscando agentes certificados…</p>,
      }
    case 'incidentes': {
      const d = c.incidentes.data
      return {
        rol: 'Historial de la mina',
        cuerpo: d ? (
          <>
            <p className="mb-1">{d.patron}</p>
            <Lista items={[`Casos parecidos: ${d.casos_similares}. Potencial máximo: ${d.riesgo_potencial_max}.`, ...d.casos.map((k) => `${k.id}: ${k.resumen_es}`)]} />
          </>
        ) : (
          <p>{c.incidentes.estado === 'error' ? 'No respondió.' : 'Buscando casos parecidos…'}</p>
        ),
      }
    }
    case 'area': {
      const filas = ptw.evaluacion?.filter((f) => f.fuente === 'vigia-area')
      const d = c.area.data
      return {
        rol: `Sensores de ${s.labor}`,
        cuerpo: filas?.length ? (
          <Tabla filas={filas} />
        ) : d ? (
          <Lista items={[`CO ${d.co_ppm} ppm`, `O₂ ${d.o2_pct} %`, `Ventilación ${d.ventilacion}`, `Ruido ${d.ruido_dBA} dBA`, `Último desatado hace ${d.ultimo_desatado_h} h`]} />
        ) : (
          <p>{c.area.estado === 'error' ? 'Los sensores de la labor no respondieron.' : 'Midiendo…'}</p>
        ),
      }
    }
    case 'gemelo': {
      const d = c.gemelo.data
      return {
        rol: 'Zona clínica cerrada',
        cuerpo: d ? (
          <Lista
            items={[
              <span className={CLASES_NIVEL[NIVEL_DE_APTITUD[d.apto_para_tarea]].texto}>{TEXTO_APTITUD[d.apto_para_tarea]}</span>,
              `Motivo: ${d.motivo_visible}`,
              c.gemelo.diagnostico_descartado ? 'Envió un diagnóstico y Vigía lo descartó sin mostrarlo.' : <code>diagnostico: null</code>,
            ]}
          />
        ) : (
          <p>Consultando la aptitud, sin datos médicos…</p>
        ),
      }
    }
    case 'reglas':
      return {
        rol: 'Cálculo con base legal; aquí no decide la IA',
        cuerpo: ptw.evaluacion?.length ? (
          <>
            <Tabla filas={ptw.evaluacion} />
            {p && <p className="mt-2">El nivel es el más alto de la lista: <b>{TEXTO_NIVEL[p.nivel].toLowerCase()}</b>.</p>}
          </>
        ) : p ? (
          <Lista items={p.porque} />
        ) : (
          <p>Esperando las tres consultas…</p>
        ),
      }
    case 'decision':
      return {
        rol: p ? TEXTO_DECISION[p.decision] : 'Esperando las reglas',
        cuerpo: p ? (
          <Lista
            items={[
              `Nivel ${TEXTO_NIVEL[p.nivel].toLowerCase()}.`,
              ptw.checklist_base
                ? `PETAR con ${ptw.checklist_base.length} controles base IPERC y ${p.controles_extra.length} controles extra.`
                : `PETAR con el checklist base IPERC y ${p.controles_extra.length} controles extra.`,
              textoDestino(p),
            ]}
          />
        ) : (
          <p>Calculando…</p>
        ),
      }
    case 'destino':
      return {
        rol: TEXTO_ESTADO[ptw.estado],
        cuerpo: p ? (
          <Lista
            items={[
              p.nivel === 'rojo'
                ? `Tarea bloqueada. ${nombre} recibe la alternativa: ${p.alternativa}`
                : p.nivel === 'ambar' || p.requiere_supervisor
                  ? `Llega a "Por revisar" de la supervisora. ${nombre} ve: "${TEXTO_TRABAJADOR[ptw.estado]}".`
                  : `PETAR emitido directo a ${nombre}.`,
              ...(ptw.petar?.firmado_por ? [`Firmado por ${ptw.petar.firmado_por}.`] : []),
            ]}
          />
        ) : (
          <p>Esperando la decisión…</p>
        ),
      }
  }
}

export function DetalleEtapa({ etapa, fase, ptw, avatar }: { etapa: Etapa; fase: Fase; ptw: Ptw; avatar?: Avatar }) {
  const { rol, cuerpo } = contenido(etapa, ptw, avatar)
  return (
    <div className="space-y-1 text-[15px] leading-snug">
      <p className={`flex items-center gap-2 text-sm font-semibold ${COLOR_FASE[fase]}`}>
        <span className={`size-2.5 rounded-full bg-current ${fase === 'proceso' ? 'motion-safe:animate-latido' : ''}`} aria-hidden="true" />
        {TEXTO_FASE[fase]}
      </p>
      <h3 className="font-cond text-xl font-bold">{TITULO_ETAPA[etapa]}</h3>
      <p className="text-sm text-tinta-2">{rol}</p>
      {fase === 'espera' ? <p className="text-tinta-2">Todavía no le llega la solicitud.</p> : cuerpo}
    </div>
  )
}
