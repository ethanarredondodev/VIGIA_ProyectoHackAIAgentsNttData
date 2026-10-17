// Rasgos deterministas de cada trabajador a partir de su seed: los usan el avatar 2D y el 3D.

const PIELES = ['#E0B48C', '#C98E62', '#B07A4F', '#9A6640', '#80522F', '#6B4426']
const PELOS = ['#1B1714', '#2A201A', '#3B2C22', '#151210']
const ROPA = ['#3E4A5A', '#4B4E3C', '#2F3B4C', '#5A4F45']
const PEINADOS = ['patillas', 'corto', 'largo', 'trenza'] as const

function azar(semilla: string) {
  let h = 1779033703 ^ semilla.length
  for (let i = 0; i < semilla.length; i++) {
    h = Math.imul(h ^ semilla.charCodeAt(i), 3432918353)
    h = (h << 13) | (h >>> 19)
  }
  return () => {
    h = Math.imul(h ^ (h >>> 16), 2246822507)
    h = Math.imul(h ^ (h >>> 13), 3266489909)
    h ^= h >>> 16
    return (h >>> 0) / 4294967296
  }
}

export function rasgos(semilla: string) {
  const r = azar(semilla)
  const elegir = <T,>(lista: readonly T[]) => lista[Math.floor(r() * lista.length)]
  return {
    piel: elegir(PIELES),
    pelo: elegir(PELOS),
    ropa: elegir(ROPA),
    peinado: elegir(PEINADOS),
    bigote: r() < 0.35,
    cara: 27 + r() * 4,
    ojos: 10 + r() * 3,
    cejas: 2 + r() * 2,
    nariz: 3 + r() * 3,
  }
}

const canales = (hex: string) => {
  const n = parseInt(hex.slice(1), 16)
  return [n >> 16, (n >> 8) & 255, n & 255]
}

export const sombra = (hex: string, f: number) => `rgb(${canales(hex).map((v) => Math.round(v * (1 - f))).join(',')})`

export const mezcla = (a: string, b: string, t: number) => {
  const [ca, cb] = [canales(a), canales(b)]
  return `rgb(${ca.map((v, i) => Math.round(v + (cb[i] - v) * t)).join(',')})`
}
