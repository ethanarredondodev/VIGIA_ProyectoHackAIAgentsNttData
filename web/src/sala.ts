import { useEffect, useState } from 'react'
import type { Ptw } from './tipos'

export type Etapa = 'trabajador' | 'ptw' | 'nanda' | 'incidentes' | 'area' | 'gemelo' | 'reglas' | 'decision' | 'destino'
export type Fase = 'espera' | 'proceso' | 'listo' | 'error'
export type EstadoSala = Record<Etapa, Fase>

// Orden en que se muestran las etapas; las tres consultas corren en paralelo y se desempatan en este orden.
export const ORDEN: Etapa[] = ['trabajador', 'ptw', 'nanda', 'area', 'incidentes', 'gemelo', 'reglas', 'decision', 'destino']

const REQUIERE: Record<Etapa, Etapa[]> = {
  trabajador: [],
  ptw: ['trabajador'],
  nanda: ['ptw'],
  area: ['nanda'],
  incidentes: ['nanda'],
  gemelo: ['nanda'],
  reglas: ['area', 'incidentes', 'gemelo'],
  decision: ['reglas'],
  destino: ['decision'],
}

export const INICIAL: EstadoSala = {
  trabajador: 'listo',
  ptw: 'proceso',
  nanda: 'espera',
  area: 'espera',
  incidentes: 'espera',
  gemelo: 'espera',
  reglas: 'espera',
  decision: 'espera',
  destino: 'espera',
}

const terminada = (f: Fase) => f === 'listo' || f === 'error'

// Lo que de verdad pasó según el último dato del backend.
export function salaReal(ptw: Ptw): EstadoSala {
  const nanda: Fase = ptw.nanda.length ? 'listo' : 'proceso'
  const consulta = (k: 'area' | 'incidentes' | 'gemelo'): Fase => {
    const estado = ptw.consultas[k].estado
    if (estado === 'ok') return 'listo'
    if (estado === 'error') return 'error'
    return nanda === 'listo' ? 'proceso' : 'espera'
  }
  const [area, incidentes, gemelo] = [consulta('area'), consulta('incidentes'), consulta('gemelo')]
  return {
    trabajador: 'listo',
    ptw: 'listo',
    nanda,
    area,
    incidentes,
    gemelo,
    reglas: ptw.propuesta ? 'listo' : [area, incidentes, gemelo].every(terminada) ? 'proceso' : 'espera',
    decision: ptw.propuesta ? 'listo' : 'espera',
    destino: ptw.estado !== 'procesando' ? 'listo' : 'espera',
  }
}

// Completa una sola etapa por paso, y solo si ya ocurrió en la realidad: nunca se adelanta ni cambia el orden.
export function avanzar(mostrado: EstadoSala, real: EstadoSala): EstadoSala {
  const etapa = ORDEN.find(
    (e) => !terminada(mostrado[e]) && terminada(real[e]) && REQUIERE[e].every((r) => terminada(mostrado[r])),
  )
  if (!etapa) return mostrado
  const nuevo: EstadoSala = { ...mostrado, [etapa]: real[etapa] }
  for (const e of ORDEN) if (nuevo[e] === 'espera' && REQUIERE[e].every((r) => terminada(nuevo[r]))) nuevo[e] = 'proceso'
  return nuevo
}

// Repetición fiel: si el backend responde en milisegundos, igual se ve a un ritmo legible.
export function useSala(ptw: Ptw | undefined, pasoMs = 900): EstadoSala {
  const quieto = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const [guardado, setGuardado] = useState<{ id?: string; sala: EstadoSala }>({ id: ptw?.ptw_id, sala: INICIAL })
  const sala = guardado.id === ptw?.ptw_id ? guardado.sala : INICIAL
  const real = ptw ? salaReal(ptw) : INICIAL
  const clave = JSON.stringify(real)

  useEffect(() => {
    if (quieto || !ptw) return
    const siguiente = avanzar(sala, real)
    if (siguiente === sala) return
    const espera = setTimeout(() => setGuardado({ id: ptw.ptw_id, sala: siguiente }), pasoMs)
    return () => clearTimeout(espera)
  }, [sala, clave, ptw?.ptw_id, quieto, pasoMs])

  return quieto ? real : sala
}
