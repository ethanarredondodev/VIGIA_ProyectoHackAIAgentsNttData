// El 3D se muestra solo si hay WebGL y el celular no pidió ahorrar datos; si no, queda el gemelo 2D.
export function soporta3D(): boolean {
  if ((navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData) return false
  if (typeof WebGLRenderingContext === 'undefined') return false
  try {
    const lienzo = document.createElement('canvas')
    return !!(lienzo.getContext('webgl2') ?? lienzo.getContext('webgl'))
  } catch {
    return false
  }
}
