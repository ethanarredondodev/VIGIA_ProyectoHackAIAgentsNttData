# Usuarios, sala de control del admin, gemelo 3D y actividad en texto libre: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que Vigía web tenga ingreso por usuario (trabajador, supervisor, admin), una sala de control animada y fiel para el admin, un gemelo 3D y la actividad en texto libre para el trabajador, y una pestaña de reportes para el supervisor.

**Architecture:** Los contratos nuevos se tipan en `src/tipos.ts`, se llaman desde `src/api.ts` y se simulan en `src/mocks/`, así todo funciona sin backend. La lógica que decide (sesión, pedido, repetición de la sala, parámetros del minero) vive en módulos puros con tests; los componentes solo la muestran. three.js se carga con import dinámico solo en la vista del trabajador.

**Tech Stack:** React 18, Vite 7, TypeScript 5.9, Tailwind 4, TanStack Query 5, React Router 6.30, MSW 2, Vitest 3, three 0.160.1 (`@types/three` 0.160.0).

**Spec:** [../specs/2026-10-17-vigia-web-usuarios-admin-3d-design.md](../specs/2026-10-17-vigia-web-usuarios-admin-3d-design.md). Maquetas aprobadas en `../specs/maquetas/`.

Todas las rutas de este plan son relativas a `web/`.

## Global Constraints

- Solo se edita `web/`. El backend lo implementa la otra sesión; ya recibió el pedido de contratos.
- Los contratos actuales no cambian. Todo campo nuevo es opcional y el front funciona sin él.
- Una sola dependencia nueva: `three@0.160.1` (más `@types/three@0.160.0` en desarrollo).
- El front nunca envía `actividad_id` ni `interpretacion` si `POST /tareas/interpretar` no respondió (el backend actual los rechaza con 422). El cliente nunca envía `tipo_tarea`: el servidor lo deriva de la tabla a partir de `actividad_id` (acordado con la sesión de backend).
- El texto libre del trabajador no viaja en la solicitud, salvo con "Otra actividad".
- Ningún componente muestra `diagnostico` ni datos clínicos; `src/api.ts` sigue filtrando gemelo y avatar por lista blanca.
- El color siempre va con texto o ícono; foco visible; `prefers-reduced-motion` respetado; objetivos táctiles de 56 px o más en la vista del trabajador.
- Copy en español neutro, sin voseo, voz activa y mayúscula solo inicial.
- Sin commits: el usuario no los pidió. Cada tarea termina con tests, `npx tsc --noEmit` y `npx vitest run` en verde.

## Review Focus

1. Backend real sin los contratos nuevos (el de hoy): `/actividades`, `/labores` y `/tareas/interpretar` dan 404. El trabajador debe poder pedir el permiso con la lista base y la labor escrita a mano, y la solicitud no debe llevar campos nuevos. Test en la tarea 3.
2. Escritura rápida con respuestas fuera de orden: la tarjeta "Vigía entendió" debe corresponder al último texto, no a una respuesta vieja que llegó tarde. Test en la tarea 3.
3. Cambiar de PETAR a mitad de la animación del admin: la repetición vuelve a empezar para el nuevo y no mezcla etapas. Test en la tarea 5.
4. `sessionStorage` bloqueado (modo privado o cookies bloqueadas): el ingreso funciona igual en memoria. Test en la tarea 2.
5. WebGL que falla al crear el contexto aunque el navegador diga que lo soporta: se muestra el gemelo 2D, no un recuadro negro. Test en la tarea 4.

---

### Task 1: Contratos nuevos y mocks

**Files:**
- Modify: `src/tipos.ts`, `src/api.ts`, `src/mocks/datos.ts`, `src/mocks/handlers.ts`
- Create: `src/pedido.ts` (solo la constante `ACTIVIDADES_BASE` en esta tarea)
- Test: `src/test/contratos.test.ts`

**Interfaces:**
- Produces (tipos):
  ```ts
  export type Confianza = 'alta' | 'media' | 'baja'
  export interface Actividad { id: string; actividad: string; tipo_tarea: string }
  export interface Labor { labor: string; tipo_labor: string }
  export interface Interpretacion { actividad: Actividad | null; labor: string | null; tipo_labor: string | null; confianza: Confianza; alternativas: Actividad[] }
  export interface ReglaEvaluada { dato: string; valor: string; limite: string | null; resultado: 'ok' | 'ambar' | 'rojo'; base_legal: string | null; fuente: string } // fuente = id del agente (vigia-area, vigia-incidentes, vigia-gemelo)
  // Solicitud += actividad_id?: string | null; interpretacion?: { actividad_id: string | null; confianza: Confianza }
  // Ptw += tipo_tarea?, tipo_labor?, creado_en?, cerrado_en?: string; checklist_base?: string[]; evaluacion?: ReglaEvaluada[]; resultado?: Resultado
  ```
- Produces (api): `obtenerActividades(): Promise<Actividad[]>`, `obtenerLabores(): Promise<Labor[]>`, `interpretarTarea(texto: string): Promise<Interpretacion>`, `listarPtw(): Promise<Ptw[]>` (filtra el gemelo igual que `obtenerPtw`), hooks `useActividades()`, `useLabores()` (ambos `staleTime: Infinity`, `retry: false`) y `usePtwLista()` (`refetchInterval: 4000`).
- Produces (pedido): `export const ACTIVIDADES_BASE: Actividad[]` con 11 filas, una por `TIPOS_TAREA` salvo `otro`, en este orden y con estos nombres: ACT-01 Perforación de frente (perforacion), ACT-02 Voladura (voladura), ACT-03 Desatado de rocas (desatado), ACT-04 Sostenimiento con pernos y malla (sostenimiento), ACT-05 Carguío y limpieza (carguio), ACT-06 Acarreo de mineral (acarreo), ACT-07 Mantenimiento de equipos (mantenimiento), ACT-08 Izaje con winche (izaje), ACT-09 Trabajo en altura (trabajo_en_altura), ACT-10 Trabajo en espacio confinado (espacio_confinado), ACT-11 Soldadura y oxicorte (trabajo_en_caliente).
- Produces (mocks): reemplazan los datos inventados por los datos sintéticos de la base de datos del backend (sin nada clínico), para que la demo sea igual con y sin backend:
  - `ACTIVIDADES` (= `ACTIVIDADES_BASE` + `sinonimos: string[]` tomados de `_PALABRAS_TAREA` de `../contracts/vocabulario.py`). La tabla real será una hoja de cálculo (decisión del usuario).
  - `LABORES` con sus condiciones: las 13 de `../data/synthetic/labores.json` (`labor`, `unidad`, gases, ruido, desatado), con `tipo_labor` por prefijo como `clasificar_labor`.
  - `TRABAJADORES`: los 11 trabajadores de los casos de `../data/synthetic/solicitudes.json`, con nombre, cargo, empresa y empleador de `../data/synthetic/trabajadores.json`. `estado_visual` es inventado y no clínico, coherente con el resultado de cada caso.
  - `INCIDENTES`: los 25 de `../data/synthetic/incidentes_etiquetados.json`, solo `id`, `tipo_tarea`, `labor_tipo`, `turno`, `riesgo_critico`, `causa_probable`, `potencial` y `resumen_es`.
  - `evaluar(solicitud, aptitud, incidentes): ReglaEvaluada[]` con las reglas reales del backend:
    - De `../data/sheets/limites_area.csv`: O₂ < 19.5 → rojo; CO > 25 → rojo; ruido > 85 → ámbar; y, solo en subterránea, desatado > 12 h → ámbar y ventilación distinta de "operativa" → rojo.
    - De `agents/ptw/reglas_riesgo.py`: no apto → rojo; con observaciones → ámbar; 3 o más casos parecidos con potencial alto o crítico → ámbar.
  - `SEMILLAS` = los casos 2 a 11 de `solicitudes.json`, con ids `PTW-SEED-02` a `PTW-SEED-11`. El caso 1 (Juan, TJ-12, ámbar) es la demo en vivo. Cerrados con `resultado`:
    - `PTW-SEED-02` Juan en GA-07: `incidente`, "Cayó roca menor del hastial; sin lesionados; se reforzó el desatado.".
    - `PTW-SEED-04` María: `casi_incidente`, "Un volquete invadió el carril en la rampa; se detuvo a tiempo.".
    - `PTW-SEED-09` Yeni: `sin_novedad`.
  - `?escenario=` ya no fuerza el nivel: define el estado del gemelo de Juan (ámbar: T-001 cansado; verde y rojo: T-001-D3 descansado). El nivel sale de la labor escrita y de las reglas. "Nueva solicitud de demo" usa el caso de `solicitudes.json` de cada escenario: TJ-12, GA-07 o CH-02.

- [ ] **Step 1: Escribir los tests que fallan** en `src/test/contratos.test.ts`:
  ```ts
  it('lista las 11 actividades de la tabla', async () => {
    expect((await obtenerActividades()).map((a) => a.id)).toEqual(ACTIVIDADES_BASE.map((a) => a.id))
  })
  it('interpreta una perforación con su labor', async () => {
    const r = await interpretarTarea('voy a perforar el frente del TJ-12')
    expect(r.actividad?.tipo_tarea).toBe('perforacion')
    expect(r.labor).toBe('NV-3820 TJ-12')
    expect(r.confianza).toBe('alta')
  })
  it('sin coincidencia devuelve confianza baja y todas las actividades como alternativas', async () => {
    const r = await interpretarTarea('trabajo en la zona norte')
    expect(r.actividad).toBeNull()
    expect(r.confianza).toBe('baja')
    expect(r.alternativas).toHaveLength(11)
  })
  it('no devuelve una labor que no existe', async () => {
    expect((await interpretarTarea('perforar en TJ-99')).labor).toBeNull()
  })
  it('los casos guionados de la base de datos llegan al nivel esperado', async () => {
    // nivel_esperado de ../data/synthetic/solicitudes.json
    const esperado = { 'PTW-SEED-02': 'verde', 'PTW-SEED-03': 'rojo', 'PTW-SEED-04': 'verde', 'PTW-SEED-05': 'rojo' }
    for (const [id, nivel] of Object.entries(esperado)) expect((await obtenerPtw(id)).propuesta?.nivel).toBe(nivel)
  })
  it('GET /ptw trae los cerrados con su resultado y el gemelo sin diagnóstico', async () => {
    const lista = await listarPtw()
    expect(lista.filter((p) => p.estado === 'cerrado').map((p) => p.resultado?.resultado).sort()).toEqual(['casi_incidente', 'incidente', 'sin_novedad'])
    expect(JSON.stringify(lista)).not.toMatch(/"diagnostico":"(?!null)/)
  })
  it('una solicitud con actividad "otro" exige supervisor', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    const { ptw_id } = await crearSolicitud({ ...SOLICITUD_JUAN, actividad_id: 'otro', interpretacion: { actividad_id: null, confianza: 'baja' } })
    vi.setSystemTime(Date.now() + 10_000)
    const ptw = await obtenerPtw(ptw_id)
    expect(ptw.tipo_tarea).toBe('otro')
    expect(ptw.propuesta?.requiere_supervisor).toBe(true)
    vi.useRealTimers()
  })
  ```
  `nivelMasAlto` y `SOLICITUD_JUAN` se definen dentro del test (máximo por gravedad verde < ámbar < rojo; la solicitud del caso ámbar de Juan).

- [ ] **Step 2: Correr y ver que fallan.** Run: `npx vitest run src/test/contratos.test.ts` — Expected: FAIL (funciones y exports inexistentes).

- [ ] **Step 3: Implementar.**
  - Tipos y llamadas de API según Interfaces.
  - Mocks:
    - `GET /actividades` y `GET /labores` devuelven las constantes.
    - `POST /tareas/interpretar`: normaliza sin tildes. La actividad es la primera fila cuyo sinónimo aparece; si aparecen sinónimos de dos o más filas, `confianza: 'media'`; si ninguno, `actividad: null` y `confianza: 'baja'`. La labor sale del código `TJ|GA|GL|RP|CH|XC|CX|BC-n`, con nivel opcional, y solo se devuelve si coincide con una única entrada de `LABORES`. Las `alternativas` son las otras actividades (todas si no hubo coincidencia).
    - `GET /ptw` lista todo, de lo más nuevo a lo más viejo.
  - `construir()` agrega:
    - `tipo_tarea`: derivado de `actividad_id` con `ACTIVIDADES` (`null` u `"otro"` → `"otro"`), o el del caso si la solicitud no trae `actividad_id`.
    - `tipo_labor`, `creado_en`, y `checklist_base` y `evaluacion` cuando hay propuesta.
    - `resultado` y `cerrado_en` cuando el registro tiene resultado.
    - Con `tipo_tarea === 'otro'`, la propuesta sale con `requiere_supervisor: true`.
    - La fila de aptitud de `evaluacion` no trae valores clínicos: `{ dato: 'Aptitud', valor: <apto_para_tarea>, limite: null, base_legal: null, fuente: 'vigia-gemelo' }`. Las demás filas usan `fuente` `vigia-area` o `vigia-incidentes`.
  - `evaluar()` devuelve las 7 filas (O₂, CO, ventilación, ruido, último desatado, casos parecidos y aptitud) con las reglas indicadas en Interfaces y la base legal de `../data/sheets/limites_area.csv`. La fila de aptitud va sin límite ni base legal. En tajo abierto se omiten las filas de desatado y ventilación.
  - `construir()` arma la propuesta con `evaluar()` (nivel = el más grave), `requiere_supervisor` según `trabajo_alto_riesgo` de `../data/sheets/controles_iperc.csv` para el `tipo_tarea`, y `checklist_base` y `controles_extra` desde esa hoja.
  - Actualizar a los datos nuevos los tests existentes que nombran a los trabajadores inventados (`src/test/bandeja.test.tsx` y el test de semillas en `src/test/privacidad.test.tsx`). La bandeja inicial queda en "Por revisar 4" (Carlos, Rosa Huanca, Wilber y Nely) y "Avisos 3" (Juan en CH-02, Pedro y Edwin). Los verdes (María y Yeni) no aparecen.
  - Semillas cerradas según Interfaces (Juan en GA-07, María y Yeni).

- [ ] **Step 4: Correr todo.** Run: `npx vitest run && npx tsc --noEmit` — Expected: todos los tests en verde (14 previos + 7 nuevos), sin errores de tipos.

### Task 2: Ingreso por usuario

**Files:**
- Create: `src/sesion.tsx`, `src/vistas/Ingreso.tsx`
- Modify: `src/App.tsx`, `src/main.tsx`, `src/test/render.tsx`
- Test: `src/test/acceso.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  export type Rol = 'trabajador' | 'supervisor' | 'admin'
  export interface Usuario { id: string; nombre: string; rol: Rol; trabajadorId?: string }
  export const USUARIOS: Usuario[] // juan: Juan Mamani Quispe, trabajador, T-001; rosa: Ing. Rosa Quispe, supervisor; admin: Administración, admin
  export const INICIO: Record<Rol, string> // '/trabajador' | '/supervisor' | '/admin'
  export function puedeVer(rol: Rol, ruta: string): boolean // admin ve las tres; los demás solo la suya
  export function SesionProvider(props: { children: ReactNode; inicial?: Usuario | null }): JSX.Element
  export function useSesion(): { usuario: Usuario | null; entrar(id: string): void; salir(): void } // sessionStorage 'vigia:usuario'
  ```
- Produces (tests): `renderizar(ui, ruta = '/', usuario: Usuario | null = USUARIOS[2])`.

- [ ] **Step 1: Escribir los tests que fallan** (`<App />` con `renderizar`):
  - `'sin usuario muestra "¿Quién eres?"'`: en `'/supervisor'` con `usuario = null` aparece el heading `¿Quién eres?`.
  - `'el trabajador no puede abrir el supervisor'`: con Juan en `'/supervisor'` aparece `Tu gemelo hoy` y no existe el link `Supervisor`.
  - `'el supervisor no ve el admin'`: con Rosa en `'/admin'` aparece `Bandeja`.
  - `'el admin ve las tres vistas y /monitor lo lleva a /admin'`: con admin en `'/monitor'` el link `Admin` tiene `aria-current="page"` y existen los links `Trabajador` y `Supervisor`.
  - `'elegir un usuario entra a su vista y "Cambiar de usuario" vuelve al inicio'`.
  - `'funciona si sessionStorage falla'`: `vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('bloqueado') })`; elegir a Juan muestra `Tu gemelo hoy`.

- [ ] **Step 2: Correr y ver que fallan.** Run: `npx vitest run src/test/acceso.test.tsx` — Expected: FAIL.

- [ ] **Step 3: Implementar.**
  - `Ingreso` muestra tres tarjetas grandes con nombre y rol; al elegir, navega a `INICIO[rol]`.
  - `App` agrega una ruta protegida por rol que redirige a `INICIO[rol]` si `!puedeVer`; `/monitor` redirige a `/admin` (que por ahora muestra la vista actual de `src/vistas/Monitor.tsx`).
  - La cabecera muestra el nombre del usuario y "Cambiar de usuario"; el menú solo aparece para el admin.
  - `sessionStorage` dentro de `try/catch`, con el estado en memoria como fuente.
  - `Trabajador` toma `trabajador_id` de `usuario.trabajadorId`. `Supervisor` firma con `usuario.nombre`.

- [ ] **Step 4: Correr todo.** Run: `npx vitest run && npx tsc --noEmit` — Expected: en verde.

### Task 3: Actividad en texto libre

**Files:**
- Modify: `src/pedido.ts`, `src/vistas/Trabajador.tsx` (reemplaza `Formulario`)
- Create: `src/componentes/PedidoActividad.tsx`
- Test: `src/test/pedido.test.tsx`

**Interfaces:**
- Consumes: `interpretarTarea`, `useActividades`, `useLabores`, `crearSolicitud` (tarea 1).
- Produces (`src/pedido.ts`):
  ```ts
  export const OTRA: Actividad // { id: 'otro', actividad: 'Otra actividad', tipo_tarea: 'otro' }
  export function actividadConfirmada(interp: Interpretacion | undefined, elegida: Actividad | null): Actividad | null
  export function laborValida(labor: string, labores: Labor[] | undefined): boolean // sin lista: cualquier texto de 2+ caracteres
  export function turnoSegunHora(fecha?: Date): Turno // 07:00 a 18:59 -> 'dia'
  export function armarSolicitud(p: { actividad: Actividad; texto: string; labor: string; turno: Turno; interp?: Interpretacion; perfil: PerfilTrabajador }): Solicitud
  export type PerfilTrabajador = Pick<Solicitud, 'trabajador_id' | 'altitud_msnm' | 'tipo_mineria' | 'empleador'>
  ```
- Produces: `PedidoActividad(props: { perfil: PerfilTrabajador; onCreado: (ptwId: string) => void })`.

- [ ] **Step 1: Escribir los tests que fallan.**
  - Unitarios:
    ```ts
    expect(actividadConfirmada({ ...interpAlta }, null)?.id).toBe('ACT-01')
    expect(actividadConfirmada({ ...interpAlta, confianza: 'media' }, null)).toBeNull()
    expect(actividadConfirmada({ ...interpAlta, confianza: 'baja' }, ACTIVIDADES_BASE[2])?.id).toBe('ACT-03')
    expect(armarSolicitud({ actividad: ACTIVIDADES_BASE[0], texto: 'voy a perforar', labor: 'NV-3820 TJ-12', turno: 'noche', interp: interpAlta, perfil }))
      .toEqual({ ...perfil, tarea: 'Perforación de frente', labor: 'NV-3820 TJ-12', turno: 'noche', actividad_id: 'ACT-01', interpretacion: { actividad_id: 'ACT-01', confianza: 'alta' } })
    expect(armarSolicitud({ actividad: ACTIVIDADES_BASE[0], texto: 'x', labor: 'L', turno: 'dia', perfil })).not.toHaveProperty('actividad_id')
    expect(armarSolicitud({ actividad: OTRA, texto: ' limpiar cunetas ', labor: 'L', turno: 'dia', interp: interpBaja, perfil })).toMatchObject({ tarea: 'limpiar cunetas', actividad_id: 'otro' })
    expect(turnoSegunHora(new Date('2026-10-17T23:00:00'))).toBe('noche')
    expect(turnoSegunHora(new Date('2026-10-17T10:00:00'))).toBe('dia')
    ```
  - Componente con MSW (captura el cuerpo de `POST /ptw/solicitud` con `servidor.use`):
    - `'entiende la actividad y la solicitud no lleva el texto libre'`: se escribe "voy a perforar el frente del TJ-12" y aparecen "Vigía entendió", "Perforación de frente" y "NV-3820 TJ-12". Tras "Pedir permiso", el cuerpo tiene `actividad_id: 'ACT-01'`, no tiene `tipo_tarea` y `JSON.stringify(cuerpo)` no contiene "voy a perforar".
    - `'con confianza baja hay que tocar una actividad'`: "Pedir permiso" queda deshabilitado hasta tocar "Desatado de rocas" y elegir una labor válida.
    - `'si la interpretación falla, elige de la lista y no envía campos nuevos'`: `/tareas/interpretar` → 500; aparece "Elige la actividad"; el cuerpo enviado no tiene `actividad_id` ni `interpretacion`.
    - `'backend antiguo: sin /actividades, /labores ni /tareas/interpretar'`: los tres → 404. Aparece la lista de `ACTIVIDADES_BASE`; se acepta "NV-3820 TJ-12" escrita a mano; el cuerpo no tiene campos nuevos.
    - `'una respuesta vieja que llega tarde no pisa a la nueva'`: la respuesta para "voy a perforar" tarda 1500 ms y la de "voy a desatar la corona" 50 ms. Al final la tarjeta muestra "Desatado de rocas".
    - `'una labor que no existe no habilita el pedido'`: con "TJ-99" escrito, el botón sigue deshabilitado.

- [ ] **Step 2: Correr y ver que fallan.** Run: `npx vitest run src/test/pedido.test.tsx` — Expected: FAIL.

- [ ] **Step 3: Implementar** según la maqueta `../specs/maquetas/trabajador-3d.html`:
  - Campo "¿Qué actividad vas a realizar?" con la ayuda "Escribe solo la actividad. No escribas datos de salud: de eso se encarga el área clínica." (el texto se envía a Claude para interpretarlo). La interpretación espera 700 ms sin escribir y usa `useQuery(['interpretar', texto])`, que descarta las respuestas de textos anteriores.
  - Tarjeta "Vigía entendió" con actividad y lugar. Con confianza media o baja pregunta "¿Es esto?". Debajo, opciones para corregir y "Otra actividad". Si falta la labor, un campo con `datalist` de labores.
  - Turno Día/Noche según la hora. "Pedir permiso" de 64 px.
  - Si fallan las actividades, se usa `ACTIVIDADES_BASE`.

- [ ] **Step 4: Correr todo.** Run: `npx vitest run && npx tsc --noEmit` — Expected: en verde.

### Task 4: Gemelo 3D del trabajador

**Files:**
- Modify: `package.json` (`npm i three@0.160.1 && npm i -D @types/three@0.160.0`)
- Create: `src/componentes/rasgos.ts` (mueve `azar`, `rasgos`, `sombra` y `mezcla` desde `AvatarGemelo.tsx`)
- Modify: `src/componentes/AvatarGemelo.tsx`: importa de `rasgos.ts`; exporta `InfoGemelo({ avatar }: { avatar: Avatar })` (aptitud, chips, mini gráfico y motivo) y `etiquetaGemelo(avatar: Avatar): string`, sin cambiar lo que muestra.
- Create: `src/tres/parametros.ts`, `src/tres/soporte.ts`, `src/tres/escena.ts`, `src/componentes/AvatarGemelo3D.tsx`
- Modify: `src/vistas/Trabajador.tsx` (cabecera con `lazy(() => import('../componentes/AvatarGemelo3D'))` y `Suspense` con el 2D)
- Test: `src/test/gemelo3d.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  export interface ParametrosMinero { piel: string; pielSombra: string; pelo: string; ropa: string; peinado: 'patillas' | 'corto' | 'largo' | 'trenza'; casco: string; energia: number; parpados: boolean; colorAnillo: string }
  export function parametrosMinero(avatar: Avatar): ParametrosMinero // energia 0..1; parpados = energia < 40; anillo: apto #4cc273, observaciones #f5be3c, no apto #ff6b5e
  export function soporta3D(): boolean // WebGL disponible y sin navigator.connection.saveData
  export function crearEscena(lienzo: HTMLCanvasElement, p: ParametrosMinero, opciones: { quieto: boolean }): { actualizar(p: ParametrosMinero): void; destruir(): void }
  export default function AvatarGemelo3D(props: { trabajadorId: string }): JSX.Element
  ```

- [ ] **Step 1: Escribir los tests que fallan:**
  ```ts
  expect(parametrosMinero(TRABAJADORES['T-001'])).toEqual(parametrosMinero(TRABAJADORES['T-001']))
  expect(new Set(Object.values(TRABAJADORES).map((a) => JSON.stringify(parametrosMinero(a)))).size).toBe(Object.keys(TRABAJADORES).length)
  expect(parametrosMinero({ ...juan, estado_visual: { ...juan.estado_visual, energia: 35 } })).toMatchObject({ energia: 0.35, parpados: true })
  expect(Object.keys(parametrosMinero({ ...juan, diagnostico: 'X' } as Avatar)).sort()).toEqual(['casco', 'colorAnillo', 'energia', 'parpados', 'peinado', 'pelo', 'piel', 'pielSombra', 'ropa'])
  ```
  - `'en jsdom muestra el gemelo 2D sin datos clínicos'`: `<AvatarGemelo3D trabajadorId="T-001" />` con el avatar filtrado del test de privacidad. Aparece el rol `img` con nombre `/Juan Mamani Quispe: Apto con observaciones/` y el HTML no contiene la cadena clínica.
  - `'si WebGL falla al crear la escena, muestra el 2D'`: con `vi.mock('../tres/soporte', () => ({ soporta3D: () => true }))` y `crearEscena` lanzando un error, aparece el rol `img` del 2D.

- [ ] **Step 2: Correr y ver que fallan.** Run: `npx vitest run src/test/gemelo3d.test.tsx` — Expected: FAIL.

- [ ] **Step 3: Implementar.**
  - `crearEscena` reproduce la maqueta aprobada `../specs/maquetas/trabajador-3d.html`: socavón, minero con brazos, chaleco abierto y reflectivos, foco, haz y halo, anillo, `OrbitControls` con límites y movimiento suave.
  - Con `opciones.quieto` no anima. `pixelRatio` hasta 2 y `destruir()` libera geometrías, materiales y el renderer.
  - `AvatarGemelo3D` usa `useAvatar`. Si `!soporta3D()` o `crearEscena` lanza un error, muestra `<AvatarGemelo size="md" />`. Si no, muestra el lienzo con `role="img"`, `aria-label={etiquetaGemelo(avatar)}` y `<InfoGemelo />`.

- [ ] **Step 4: Correr todo y revisar el build.** Run: `npx vitest run && npx tsc --noEmit && npm run build` — Expected: en verde, y en `dist/assets/` un chunk aparte para `AvatarGemelo3D` (three no queda en el chunk principal).

### Task 5: Repetición fiel de la sala (lógica pura)

**Files:**
- Create: `src/sala.ts`
- Test: `src/test/sala.test.ts`

**Interfaces:**
- Produces:
  ```ts
  export type Etapa = 'trabajador' | 'ptw' | 'nanda' | 'incidentes' | 'area' | 'gemelo' | 'reglas' | 'decision' | 'destino'
  export type Fase = 'espera' | 'proceso' | 'listo' | 'error'
  export type EstadoSala = Record<Etapa, Fase>
  export const ORDEN: Etapa[] // ['trabajador', 'ptw', 'nanda', 'area', 'incidentes', 'gemelo', 'reglas', 'decision', 'destino']
  export const INICIAL: EstadoSala // trabajador listo, ptw proceso, el resto espera
  export function salaReal(ptw: Ptw): EstadoSala
  export function avanzar(mostrado: EstadoSala, real: EstadoSala): EstadoSala // completa una sola etapa; devuelve el mismo objeto si no hay nada que completar
  export function useSala(ptw: Ptw | undefined, pasoMs?: number): EstadoSala // por defecto 900 ms; con prefers-reduced-motion devuelve salaReal
  ```
- Dependencias: ptw ← trabajador; nanda ← ptw; consultas ← nanda; reglas ← las tres consultas (listo o error); decision ← reglas; destino ← decision.
- `salaReal`:
  - nanda: `listo` si hay fichas, `proceso` si no.
  - Cada consulta: `ok` → `listo`, `error` → `error`, `pendiente` → `proceso` (si nanda ya está lista) o `espera`.
  - reglas y decision: `listo` con propuesta. Sin propuesta, reglas está en `proceso` si las consultas terminaron.
  - destino: `listo` cuando `estado !== 'procesando'`.

- [ ] **Step 1: Escribir los tests que fallan:**
  - `'un PETAR terminado se muestra etapa por etapa'`: desde `INICIAL` y con `real` todo listo, 8 llamadas a `avanzar` completan las etapas en el orden de `ORDEN`, de a una.
  - `'nunca se adelanta al dato real'`: con `real.nanda = 'proceso'`, tras completar `ptw` la siguiente llamada devuelve el mismo objeto (`toBe`).
  - `'una consulta con error deja seguir a reglas'`: con área en `error`, se muestra `error` y luego reglas pasa a `listo`.
  - `'cambiar de PETAR reinicia la repetición'`: `renderHook(({ ptw }) => useSala(ptw, 10), …)`; al pasar de un PTW a otro con distinto `ptw_id`, el estado vuelve a `INICIAL` antes de avanzar.

- [ ] **Step 2: Correr y ver que fallan.** Run: `npx vitest run src/test/sala.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implementar** `src/sala.ts` según Interfaces. El hook usa `setInterval(pasoMs)` mientras `avanzar` cambie algo, y se reinicia con `ptw.ptw_id`.

- [ ] **Step 4: Correr todo.** Run: `npx vitest run && npx tsc --noEmit` — Expected: en verde.

### Task 6: Vista admin: sala de control

**Files:**
- Create: `src/vistas/Admin.tsx`, `src/componentes/admin/SalaControl.tsx`, `src/componentes/admin/Detalle.tsx`, `src/componentes/admin/Paneles.tsx`
- Delete: `src/vistas/Monitor.tsx` (sus paneles de nivel, NANDA con credenciales y evidencia, y JSON pasan a `Paneles.tsx` sin cambiar lo que muestran)
- Modify: `src/App.tsx` (`/admin` → `Admin`), `src/index.css` (quita `.flecha`), `src/test/setup.ts` (agrega `window.matchMedia` que responde `true` a `prefers-reduced-motion` para que la sala se muestre al instante en tests), `src/test/privacidad.test.tsx` (`Monitor` → `Admin` en `'/admin?ptw=PTW-FUGA01'`)
- Test: `src/test/admin.test.tsx`

**Interfaces:**
- Consumes: `useSala`, `salaReal`, `Etapa`, `Fase` (tarea 5); `usePtwLista`, `usePtw`, `useAvatar` (tarea 1); `FiguraMinero` exportado desde `AvatarGemelo.tsx`.
- Produces: `SalaControl(props: { ptw: Ptw; avatar?: Avatar; sala: EstadoSala })` y `DetalleEtapa(props: { etapa: Etapa; fase: Fase; ptw: Ptw; avatar?: Avatar })`.

- [ ] **Step 1: Escribir los tests que fallan** (con `renderizar(<Admin />, '/admin?ptw=…')` y el admin como usuario):
  - `'el detalle de Reglas muestra la tabla de verificación'`: al enfocar el botón `Reglas: ver detalle` aparecen "Ruido", "91 dBA", "máximo 85 dBA" y "Ámbar".
  - `'el detalle del Gemelo prueba diagnostico: null'`: al enfocar `Gemelo: ver detalle` aparece `diagnostico: null`.
  - `'el detalle del Agente PTW muestra lo que propuso la IA y lo confirmado'`: con una solicitud que trae `actividad_id: 'ACT-01'` e `interpretacion: { actividad_id: 'ACT-01', confianza: 'alta' }` aparece "confianza alta".
  - `'la lista de solicitudes permite cambiar de PETAR'`: al hacer clic en otra solicitud de la lista cambia el subtítulo.
  - Los tests de privacidad existentes pasan con `Admin`.

- [ ] **Step 2: Correr y ver que fallan.** Run: `npx vitest run src/test/admin.test.tsx src/test/privacidad.test.tsx` — Expected: FAIL.

- [ ] **Step 3: Implementar** según `../specs/maquetas/sala-control-v3.html` y la sección "Vista admin" del diseño:
  - Tablero SVG oscuro con chispas por `requestAnimationFrame`, que no corren con movimiento reducido.
  - Trabajador en 2D con `FiguraMinero`. El destino y el regreso al trabajador dependen del nivel.
  - Detalle al costado con hover, foco o toque, con la fase arriba. Las tablas salen de `evaluacion`; sin ella se usa `propuesta.porque`.
  - Lista vertical bajo 1024 px.
  - Selector de solicitudes con `usePtwLista`: por defecto la más nueva; `?ptw=` la fija.
  - Botón "Nueva solicitud de demo" y paneles debajo.

- [ ] **Step 4: Correr todo.** Run: `npx vitest run && npx tsc --noEmit` — Expected: en verde.

### Task 7: Supervisor: reportes y checklist base

**Files:**
- Modify: `src/vistas/Supervisor.tsx`, `src/negocio.ts` (agrega `NIVEL_DE_RESULTADO: Record<ResultadoTarea, Nivel>` = sin_novedad verde, casi_incidente ámbar, incidente rojo)
- Test: `src/test/reportes.test.tsx`

**Interfaces:**
- Consumes: `usePtwLista` (tarea 1), `useSesion` (tarea 2), `NIVEL_DE_RESULTADO`.

- [ ] **Step 1: Escribir los tests que fallan** (con Rosa como usuaria):
  - `'Reportes lista las tareas cerradas con su resultado'`: en la pestaña `Reportes` aparecen María Condori con "Casi incidente" y "Un volquete invadió el carril en la rampa; se detuvo a tiempo.", Juan Mamani con "Incidente" y Yeni Torres con "Sin novedad". La pestaña se llama `/Reportes\s*2/` (casi incidentes más incidentes).
  - `'la bandeja no cambia'`: `/Por revisar\s*4/` y `/Avisos\s*3/`.
  - `'antes de firmar se ve el checklist base'`: en el caso de Carlos Huanca (`PTW-SEED-06`) aparece el texto "Checklist base IPERC" y el primer control base del caso.
  - `'firma con el nombre del usuario'`: al aceptar, el cuerpo capturado de `POST /ptw/{id}/firma` trae `supervisor: 'Ing. Rosa Quispe'`.

- [ ] **Step 2: Correr y ver que fallan.** Run: `npx vitest run src/test/reportes.test.tsx` — Expected: FAIL.

- [ ] **Step 3: Implementar.**
  - Tercera pestaña con la misma semántica `tablist`. Cada reporte muestra el avatar `sm`, la actividad, la labor, la fecha (`haceCuanto`), el resultado con ícono y texto, "Controles cumplidos: Sí/No" y la observación. Primero los más recientes.
  - En `Decision`, la lista de solo lectura "Checklist base IPERC (va siempre)" antes de los controles extra.

- [ ] **Step 4: Correr todo.** Run: `npx vitest run && npx tsc --noEmit` — Expected: en verde.

### Task 8: Pulido visual, README y verificación

**Files:**
- Modify: `src/App.tsx`, `src/index.css` (cabecera por usuario y consistencia), `README.md`

- [ ] **Step 1: README.** Documentar:
  - Ingreso de demo y usuarios.
  - Vista admin (sala de control, repetición fiel) y gemelo 3D (respaldo 2D).
  - Actividad en texto libre y qué datos viajan.
  - Pestaña Reportes.
  - Contratos nuevos y el estado de cada uno en el backend.
- [ ] **Step 2: Verificación completa.** Run: `npx tsc --noEmit && npx vitest run && npm run build` — Expected: sin errores, todos los tests en verde y `dist/` con el chunk del 3D separado.
- [ ] **Step 3: Revisión visual** con Chrome headless (scripts en el scratchpad, fuera del repo). Capturas de ingreso, trabajador (3D y texto libre), supervisor (bandeja, detalle y reportes) y admin (tablero con detalle abierto y lista angosta):
  - A 360, 390, 1280, 1366 y 1920 px, en claro y oscuro, y con movimiento reducido.
  - Sin errores de consola ni scroll horizontal.
- [ ] **Step 4: Prueba contra el backend real** (`vigia-ptw` local con `MOCK_MODE=true`): el flujo completo funciona aunque el backend aún no tenga los contratos nuevos, y no hay respuestas 422.
