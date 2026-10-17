import { rasgos, sombra } from '../componentes/rasgos'
import type { Aptitud, Avatar } from '../tipos'

export interface ParametrosMinero {
  piel: string
  pielSombra: string
  pelo: string
  ropa: string
  peinado: 'patillas' | 'corto' | 'largo' | 'trenza'
  casco: string
  energia: number
  parpados: boolean
  colorAnillo: string
}

// Colores de nivel del modo oscuro: la escena 3D siempre es un socavón oscuro.
const ANILLO: Record<Aptitud, string> = { apto: '#4cc273', apto_con_observaciones: '#f5be3c', no_apto: '#ff6b5e' }

// Privacidad: el minero 3D sale solo de la seed, el color del casco y el estado visual del gemelo.
export function parametrosMinero(avatar: Avatar): ParametrosMinero {
  const r = rasgos(String(avatar.seed))
  const ev = avatar.estado_visual
  return {
    piel: r.piel,
    pielSombra: sombra(r.piel, 0.2),
    pelo: r.pelo,
    ropa: r.ropa,
    peinado: r.peinado,
    casco: avatar.color_casco,
    energia: Math.min(100, Math.max(0, ev.energia)) / 100,
    parpados: ev.energia < 40,
    colorAnillo: ANILLO[ev.apto_para_tarea],
  }
}
