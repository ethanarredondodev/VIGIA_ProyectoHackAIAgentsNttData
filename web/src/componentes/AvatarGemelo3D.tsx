import { useEffect, useRef, useState } from 'react'
import { useAvatar } from '../api'
import { crearEscena } from '../tres/escena'
import { parametrosMinero } from '../tres/parametros'
import { soporta3D } from '../tres/soporte'
import { AvatarGemelo, etiquetaGemelo, InfoGemelo } from './AvatarGemelo'

// Se carga con import dinámico solo en la vista del trabajador: three.js no entra al paquete principal.
export default function AvatarGemelo3D({ trabajadorId }: { trabajadorId: string }) {
  const { data: avatar } = useAvatar(trabajadorId)
  const lienzo = useRef<HTMLCanvasElement>(null)
  const escena = useRef<ReturnType<typeof crearEscena> | null>(null)
  const [sin3D, setSin3D] = useState(() => !soporta3D())
  const parametros = avatar ? parametrosMinero(avatar) : null
  const clave = JSON.stringify(parametros)

  useEffect(() => {
    if (sin3D || !lienzo.current || !parametros) return
    try {
      escena.current = crearEscena(lienzo.current, parametros, {
        quieto: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
      })
    } catch {
      setSin3D(true)
      return
    }
    return () => {
      escena.current?.destruir()
      escena.current = null
    }
    // La escena se crea una vez por trabajador; los cambios de estado llegan por actualizar().
  }, [sin3D, !!parametros])

  useEffect(() => {
    if (parametros) escena.current?.actualizar(parametros)
  }, [clave])

  if (sin3D || !avatar) return <AvatarGemelo trabajadorId={trabajadorId} size="md" />

  return (
    <div>
      <div className="overflow-hidden rounded-md bg-[#12171c]">
        <canvas ref={lienzo} role="img" aria-label={etiquetaGemelo(avatar)} className="block h-[300px] w-full cursor-grab touch-none" />
        <p className="pb-2 text-center text-sm text-[#a9b2ba]">Arrastra para girar a tu gemelo</p>
      </div>
      <div className="pt-3">
        <InfoGemelo avatar={avatar} />
      </div>
    </div>
  )
}
