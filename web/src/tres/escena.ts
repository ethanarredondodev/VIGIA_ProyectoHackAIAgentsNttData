import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { ParametrosMinero } from './parametros'

// El gemelo 3D en un socavón: minero armado con formas simples (sin modelos externos) cuya lámpara alumbra la roca.
// Escena aprobada en docs/superpowers/specs/maquetas/trabajador-3d.html.

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

const mat = (color: string, extra: THREE.MeshStandardMaterialParameters = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.8, ...extra })

function malla(geo: THREE.BufferGeometry, material: THREE.Material, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(geo, material)
  m.position.set(x, y, z)
  m.castShadow = true
  return m
}

function socavon(escena: THREE.Scene) {
  const r = azar('socavon-nv-3820')
  const rocas = ['#4a4f55', '#58514a', '#3e4349', '#5b5f63'].map((c) => new THREE.MeshStandardMaterial({ color: c, roughness: 1, flatShading: true }))
  // Detrás del minero, el arco completo; delante, solo las paredes bajas para no tapar la cámara.
  for (let i = 0; i < 80; i++) {
    const adelante = i >= 60
    const angulo = adelante ? (r() < 0.5 ? 0.05 + 0.25 * r() : Math.PI - 0.3 + 0.25 * r()) : Math.PI * (0.02 + 0.96 * r())
    const radio = adelante ? 1.95 + 0.3 * r() : 1.7 + 0.3 * r()
    const roca = new THREE.Mesh(new THREE.IcosahedronGeometry(0.25 + 0.38 * r(), 0), rocas[i % rocas.length])
    roca.position.set(Math.cos(angulo) * radio, 0.1 + Math.sin(angulo) * radio * 0.95, adelante ? 0.2 + 1.1 * r() : -2.6 + 2.8 * r())
    roca.rotation.set(r() * 3, r() * 3, r() * 3)
    roca.receiveShadow = true
    escena.add(roca)
  }
  const piso = new THREE.Mesh(new THREE.PlaneGeometry(10, 10), new THREE.MeshStandardMaterial({ color: '#2a2d31', roughness: 1 }))
  piso.rotation.x = -Math.PI / 2
  piso.receiveShadow = true
  escena.add(piso)
}

function pelo(cabeza: THREE.Group, p: ParametrosMinero) {
  const material = mat(p.pelo)
  const alto = p.peinado === 'corto' ? 0.06 : p.peinado === 'patillas' ? 0.13 : 0.22
  ;[-1, 1].forEach((lado) => cabeza.add(malla(new THREE.BoxGeometry(0.05, alto, 0.06), material, lado * 0.232, 0.08 - alto / 2, 0.05)))
  if (p.peinado === 'largo') {
    const melena = malla(new THREE.SphereGeometry(0.3, 20, 16), material, 0, -0.1, -0.1)
    melena.scale.set(1, 1.25, 0.75)
    cabeza.add(melena)
  }
  if (p.peinado === 'trenza') {
    for (let i = 0; i < 5; i++) cabeza.add(malla(new THREE.SphereGeometry(0.05, 10, 8), material, 0.2 + i * 0.012, -0.14 - i * 0.075, -0.12))
  }
}

function minero(escena: THREE.Scene, p: ParametrosMinero) {
  const grupo = new THREE.Group()
  grupo.rotation.y = -0.28
  escena.add(grupo)
  const cuerpo = new THREE.Group()
  grupo.add(cuerpo)

  const torso = malla(new THREE.CapsuleGeometry(0.34, 0.5, 8, 24), mat(p.ropa), 0, 0.7, 0)
  torso.scale.set(1.35, 1, 0.78)
  cuerpo.add(torso)
  // Chaleco sin mangas que sigue la forma del torso, abierto al frente, con cintas reflectivas.
  const perfil = [[0.365, 0.36], [0.375, 0.6], [0.372, 0.86], [0.33, 1.0], [0.24, 1.08]].map(([x, y]) => new THREE.Vector2(x, y))
  const chaleco = malla(new THREE.LatheGeometry(perfil, 40, 0.42, Math.PI * 2 - 0.84), mat('#d3e23a', { side: THREE.DoubleSide, roughness: 0.55 }))
  chaleco.scale.set(1.36, 1, 0.8)
  cuerpo.add(chaleco)
  const reflectivo = mat('#d6dbe2', { roughness: 0.3, metalness: 0.4, emissive: '#3a3d42' })
  ;[0.6, 0.8].forEach((y) => {
    const giro = new THREE.Group()
    giro.rotation.x = Math.PI / 2
    giro.position.y = y
    const banda = malla(new THREE.TorusGeometry(0.378, 0.02, 6, 48, Math.PI * 2 - 0.84), reflectivo)
    banda.rotation.z = Math.PI / 2 + 0.42
    banda.scale.set(1.36, 0.8, 1)
    giro.add(banda)
    cuerpo.add(giro)
  })
  ;[-1, 1].forEach((lado) => {
    const brazo = malla(new THREE.CapsuleGeometry(0.1, 0.46, 6, 16), mat(p.ropa), lado * 0.53, 0.74, 0)
    brazo.rotation.z = lado * 0.16
    cuerpo.add(brazo)
    cuerpo.add(malla(new THREE.SphereGeometry(0.085, 14, 12), mat(p.pielSombra), lado * 0.585, 0.38, 0.02))
  })

  // Respirador colgado al cuello, con filtros P100.
  const respirador = new THREE.Group()
  respirador.position.set(0, 0.92, 0.3)
  const mascara = malla(new THREE.CapsuleGeometry(0.06, 0.08, 6, 16), mat('#8e979f', { roughness: 0.5 }))
  mascara.rotation.z = Math.PI / 2
  mascara.scale.set(1, 1, 0.75)
  respirador.add(mascara)
  ;[-0.12, 0.12].forEach((x) => {
    const filtro = malla(new THREE.CylinderGeometry(0.055, 0.055, 0.05, 20), mat('#c23b78', { roughness: 0.45 }), x, -0.01, 0.02)
    filtro.rotation.x = Math.PI / 2
    respirador.add(filtro)
  })
  cuerpo.add(respirador)
  cuerpo.add(malla(new THREE.CylinderGeometry(0.11, 0.12, 0.22, 20), mat(p.pielSombra), 0, 1.3, 0))

  const cabeza = new THREE.Group()
  cabeza.position.y = 1.55
  grupo.add(cabeza)
  const craneo = malla(new THREE.SphereGeometry(0.27, 32, 24), mat(p.piel, { roughness: 0.7 }))
  craneo.scale.set(0.92, 1.1, 0.95)
  cabeza.add(craneo)
  ;[-1, 1].forEach((lado) => {
    const oreja = malla(new THREE.SphereGeometry(0.06, 12, 10), mat(p.pielSombra), lado * 0.245, 0, 0)
    oreja.scale.set(0.6, 1, 0.8)
    cabeza.add(oreja)
  })
  pelo(cabeza, p)
  const nariz = malla(new THREE.SphereGeometry(0.045, 12, 10), mat(p.pielSombra), 0, -0.02, 0.255)
  nariz.scale.set(0.8, 1, 0.9)
  cabeza.add(nariz)

  const parpados: THREE.Mesh[] = []
  ;[-1, 1].forEach((lado) => {
    const blanco = malla(new THREE.SphereGeometry(0.045, 16, 12), mat('#f3efe8', { roughness: 0.4 }), lado * 0.095, 0.04, 0.222)
    blanco.scale.set(1, 0.75, 0.6)
    cabeza.add(blanco)
    cabeza.add(malla(new THREE.SphereGeometry(0.026, 12, 10), mat('#1d1410', { roughness: 0.3 }), lado * 0.095, 0.036, 0.247))
    const ceja = malla(new THREE.BoxGeometry(0.09, 0.018, 0.02), mat(p.pelo), lado * 0.095, 0.11, 0.236)
    ceja.rotation.z = lado * -0.08
    cabeza.add(ceja)
    const parpado = malla(new THREE.SphereGeometry(0.05, 16, 12), mat(p.piel, { roughness: 0.7 }), lado * 0.095, 0.09, 0.224)
    parpado.scale.set(1.08, 0.62, 0.66)
    cabeza.add(parpado)
    parpados.push(parpado)
  })
  const boca = malla(new THREE.TorusGeometry(0.06, 0.011, 6, 16, Math.PI), mat('#5a2e22'), 0, -0.1, 0.236)
  boca.rotation.z = Math.PI
  cabeza.add(boca)

  const colorCasco = mat(p.casco, { roughness: 0.42 })
  const domo = malla(new THREE.SphereGeometry(0.31, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), colorCasco, 0, 0.06, 0)
  domo.scale.set(1, 0.9, 1.08)
  cabeza.add(domo)
  const ala = malla(new THREE.CylinderGeometry(0.4, 0.4, 0.025, 40), colorCasco, 0, 0.06, 0.03)
  ala.scale.set(1, 1, 1.15)
  cabeza.add(ala)
  const cresta = malla(new THREE.TorusGeometry(0.29, 0.022, 6, 24, Math.PI), colorCasco, 0, 0.06, 0)
  cresta.rotation.y = Math.PI / 2
  cresta.scale.set(1, 0.9, 1.08)
  cabeza.add(cresta)
  const portaLampara = malla(new THREE.BoxGeometry(0.12, 0.085, 0.06), mat('#2e353d', { roughness: 0.5 }), 0, 0.18, 0.305)
  portaLampara.rotation.x = -0.35
  cabeza.add(portaLampara)
  const lente = new THREE.Mesh(
    new THREE.CylinderGeometry(0.036, 0.036, 0.014, 20),
    new THREE.MeshStandardMaterial({ color: '#fff6cf', emissive: '#ffe29a', emissiveIntensity: 1 }),
  )
  lente.rotation.x = Math.PI / 2 - 0.35
  lente.position.set(0, 0.185, 0.338)
  cabeza.add(lente)
  const curvaCable = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0.06, 0.18, 0.31), new THREE.Vector3(0.26, 0.12, 0.18), new THREE.Vector3(0.31, 0, -0.1), new THREE.Vector3(0.2, -0.22, -0.25),
  ])
  cabeza.add(new THREE.Mesh(new THREE.TubeGeometry(curvaCable, 24, 0.009, 6), mat('#1c2126')))

  // La lámpara alumbra de verdad: foco, haz visible y halo.
  const foco = new THREE.SpotLight('#ffe2a0', 30, 0, 0.42, 0.55, 1.6)
  foco.position.set(0, 0.185, 0.36)
  foco.castShadow = true
  foco.shadow.mapSize.set(512, 512)
  const objetivo = new THREE.Object3D()
  objetivo.position.set(0, -0.55, 3)
  cabeza.add(foco, objetivo)
  foco.target = objetivo

  const haces = [[0.55, 0.06], [0.24, 0.1]].map(([radio, opacidad]) => {
    const geo = new THREE.ConeGeometry(radio, 2.6, 32, 1, true)
    geo.translate(0, -1.3, 0)
    const haz = new THREE.Mesh(
      geo,
      new THREE.MeshBasicMaterial({ color: '#ffd76a', transparent: true, opacity: opacidad, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }),
    )
    haz.position.copy(foco.position)
    haz.rotation.x = -Math.PI / 2 + 0.2
    haz.userData.base = opacidad
    cabeza.add(haz)
    return haz
  })

  const lienzoHalo = document.createElement('canvas')
  lienzoHalo.width = lienzoHalo.height = 64
  const g = lienzoHalo.getContext('2d')!
  const degradado = g.createRadialGradient(32, 32, 0, 32, 32, 32)
  degradado.addColorStop(0, 'rgba(255,246,207,1)')
  degradado.addColorStop(0.3, 'rgba(255,212,92,.55)')
  degradado.addColorStop(1, 'rgba(255,212,92,0)')
  g.fillStyle = degradado
  g.fillRect(0, 0, 64, 64)
  const textura = new THREE.CanvasTexture(lienzoHalo)
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: textura, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }))
  halo.position.set(0, 0.185, 0.36)
  cabeza.add(halo)

  return { cuerpo, cabeza, foco, lente, haces, halo, parpados, boca, textura }
}

export function crearEscena(lienzo: HTMLCanvasElement, p: ParametrosMinero, opciones: { quieto: boolean }) {
  const renderer = new THREE.WebGLRenderer({ canvas: lienzo, antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap

  const escena = new THREE.Scene()
  escena.background = new THREE.Color('#12171c')
  escena.fog = new THREE.Fog('#12171c', 4, 8)

  const camara = new THREE.PerspectiveCamera(34, 1, 0.1, 30)
  camara.position.set(0.3, 1.5, 3.7)
  const controles = new OrbitControls(camara, lienzo)
  controles.target.set(0, 1.28, 0)
  controles.enableZoom = false
  controles.enablePan = false
  controles.enableDamping = !opciones.quieto
  controles.minPolarAngle = 1.15
  controles.maxPolarAngle = 1.7
  controles.minAzimuthAngle = -1.1
  controles.maxAzimuthAngle = 1.1
  controles.update()

  escena.add(new THREE.HemisphereLight('#c8d4ea', '#2a241e', 1.1))
  const principal = new THREE.DirectionalLight('#fff1dc', 1.6)
  principal.position.set(1.5, 2.2, 3)
  const contraluz = new THREE.DirectionalLight('#8db4ff', 1.4)
  contraluz.position.set(-2.5, 3, -3)
  escena.add(principal, contraluz)

  socavon(escena)
  const m = minero(escena, p)
  const anillo = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.02, 8, 72), new THREE.MeshBasicMaterial({ color: p.colorAnillo }))
  anillo.rotation.x = Math.PI / 2
  anillo.position.y = 0.02
  escena.add(anillo)

  let meta = p
  const actual = { luz: p.energia, parpado: p.parpados ? 1 : 0, color: new THREE.Color(p.colorAnillo) }
  const reloj = new THREE.Clock()
  let cuadroId = 0

  function ajustar() {
    const { clientWidth: ancho, clientHeight: alto } = lienzo
    renderer.setSize(ancho, alto, false)
    camara.aspect = ancho / Math.max(alto, 1)
    camara.updateProjectionMatrix()
  }

  function pintar() {
    const dt = Math.min(reloj.getDelta(), 0.05)
    const paso = opciones.quieto ? 1 : Math.min(1, dt * 2.5)
    actual.luz += (meta.energia - actual.luz) * paso
    actual.parpado += ((meta.parpados ? 1 : 0) - actual.parpado) * paso
    actual.color.lerp(new THREE.Color(meta.colorAnillo), paso)
    m.foco.intensity = 4 + 46 * actual.luz
    ;(m.lente.material as THREE.MeshStandardMaterial).emissiveIntensity = 0.3 + 2.4 * actual.luz
    m.haces.forEach((h) => ((h.material as THREE.MeshBasicMaterial).opacity = h.userData.base * (0.25 + actual.luz)))
    m.halo.scale.setScalar(0.12 + 0.42 * actual.luz)
    m.parpados.forEach((parpado) => (parpado.position.y = 0.09 - 0.032 * actual.parpado))
    m.boca.scale.y = 1 - 0.65 * actual.parpado
    ;(anillo.material as THREE.MeshBasicMaterial).color.copy(actual.color)
    if (!opciones.quieto) {
      const t = reloj.elapsedTime
      m.cabeza.rotation.y = 0.22 * Math.sin(t * 0.55)
      m.cabeza.rotation.x = 0.05 * Math.sin(t * 0.35)
      m.cuerpo.scale.y = 1 + 0.012 * Math.sin(t * 1.4)
    }
    controles.update()
    renderer.render(escena, camara)
  }

  const observador = new ResizeObserver(() => {
    ajustar()
    if (opciones.quieto) pintar()
  })
  observador.observe(lienzo)
  ajustar()

  if (opciones.quieto) {
    controles.addEventListener('change', pintar)
    pintar()
  } else {
    const bucle = () => {
      pintar()
      cuadroId = requestAnimationFrame(bucle)
    }
    bucle()
  }

  return {
    actualizar(nuevo: ParametrosMinero) {
      meta = nuevo
      if (opciones.quieto) pintar()
    },
    destruir() {
      cancelAnimationFrame(cuadroId)
      observador.disconnect()
      controles.dispose()
      escena.traverse((objeto) => {
        if (objeto instanceof THREE.Mesh || objeto instanceof THREE.Sprite) {
          objeto.geometry.dispose()
          ;[objeto.material].flat().forEach((material) => material.dispose())
        }
      })
      m.textura.dispose()
      renderer.dispose()
    },
  }
}
