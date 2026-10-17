# Vigía · front web

Interfaz de Vigía. El trabajador escribe la actividad que va a realizar y recibe su PETAR. El supervisor firma solo los casos con duda y lee los reportes de las tareas cerradas. Administración ve en la sala de control cómo razona el sistema multiagente con cada solicitud.

| Ruta | Usuario de demo | Qué hace |
| --- | --- | --- |
| `/trabajador` | Juan Mamani (T-001), en celular con guantes | Ve su gemelo en 3D, escribe la actividad, recibe el permiso, marca el checklist y reporta al terminar. |
| `/supervisor` | Ing. Rosa Quispe, en tablet o laptop | Pestañas "Por revisar" (ámbar y alto riesgo), "Avisos" (rojo) y "Reportes" (tareas cerradas). Acepta, ajusta o rechaza; la firma lleva su nombre. |
| `/admin` | Administración, en pantalla grande | Sala de control: el recorrido animado de cada solicitud, con el detalle en vivo de cada etapa. También puede abrir las otras dos vistas. |

Stack: React 18, Vite, TypeScript, Tailwind CSS 4, TanStack Query, React Router 6, three.js y Mock Service Worker (MSW).

## Correr en local

Requiere Node 22.

```sh
cd web
npm install
npm run dev
```

Abre http://localhost:5173 y elige un usuario en "¿Quién eres?". Es una demo, así que no hay contraseña. Cada usuario ve solo su vista y Administración ve las tres. "Cambiar de usuario" vuelve al ingreso. `/monitor` redirige a `/admin`.

Con `npm run dev` los mocks están activos (`.env.development` define `VITE_USE_MOCKS=true`), así que no hace falta el backend.

### Escenarios de la demo

Los mocks aplican las mismas reglas del backend a los datos de la BD de demo. [src/mocks/bd.ts](src/mocks/bd.ts) se generó desde `data/synthetic` y `data/sheets`, sin datos clínicos. Por eso el nivel depende de la labor que escribe Juan:

- `NV-3820 TJ-12`: desatado hace 26 h y ruido de 91 dBA. Juan está en el día 12 de 14 de su rotación y su gemelo sale apto con observaciones. Resultado: ámbar. Va al supervisor para firmar con controles.
- `NV-3820 GA-07` con `?escenario=verde`: la labor está en orden y Juan descansado. Resultado: verde, PETAR automático.
- `NV-3700 CH-02`: O₂ 18.2 % y ventilación detenida. Resultado: rojo, tarea bloqueada con alternativa. El supervisor solo recibe un aviso.

Parámetros de la URL, válidos en cualquier vista y también antes de elegir usuario:

- `?escenario=ambar` (por defecto) fija el gemelo de Juan en el día 12 de 14, con poca energía.
- `?escenario=verde` y `?escenario=rojo` lo muestran descansado (día 3).
- `?reiniciar` borra los PETAR creados y vuelve a sembrar la demo: 11 trabajadores y 11 casos (4 por revisar, 4 avisos y 3 tareas cerradas con reporte).

Para el pitch, abre cada usuario en su propia pestaña del mismo navegador: la sesión es por pestaña (`sessionStorage`) y los mocks guardan el estado en `localStorage`. Así, lo que pide Juan aparece en la bandeja de Rosa y en la sala de control. La sala sigue la solicitud más nueva y `?ptw=PTW-XXXXXX` fija una. Dos botones lanzan los casos guionados de Juan:

- **Demo: caso aprobado**: Juan descansado en GA-07, turno día. Sale verde y el PETAR llega directo al trabajador.
- **Demo: caso para el supervisor**: Juan en TJ-12, turno noche. Sale ámbar y va a la bandeja de la supervisora.

Cada consulta simulada responde entre 0.8 y 2 s, en un orden distinto cada vez.

## Las vistas

### Trabajador: actividad en texto libre

Juan escribe solo la actividad, por ejemplo "voy a perforar el frente". Sus datos de salud ya los aporta el área clínica a través del gemelo, y la pantalla le pide no escribirlos.

- 700 ms después de que deja de escribir, el texto va a `POST /tareas/interpretar`, que lo compara con la tabla de actividades:
  - Confianza alta: "Vigía entendió".
  - Confianza media: "¿Es esto?", con un botón para confirmar.
  - Confianza baja o error: "Elige la actividad".
- Siempre puede corregir con la lista (`GET /actividades`) o elegir "Otra actividad", que va al supervisor.
- La labor se valida contra `GET /labores` y el turno se propone según la hora (día de 7:00 a 18:59).
- La solicitud lleva:
  - `tarea`: la actividad confirmada, o el texto si eligió "Otra actividad".
  - `labor` y `turno`.
  - El perfil fijo de Juan: `trabajador_id`, `altitud_msnm`, `tipo_mineria` y `empleador`.
  - `actividad_id` e `interpretacion: {actividad_id, confianza}`, solo si `/tareas/interpretar` respondió.

El gemelo se ve en 3D. Es un minero procedural (three.js, sin modelos externos) que sale siempre igual a partir de su seed, con la lámpara del casco y un anillo del color de su aptitud, y se gira arrastrando. La escena va en un chunk aparte que carga de forma diferida. Si el navegador no tiene WebGL, si está activo el ahorro de datos o si la escena falla, se muestra la ilustración 2D. Con movimiento reducido, la escena queda quieta.

### Supervisor: bandeja, firma y reportes

- "Por revisar" y "Avisos" funcionan como antes.
- Antes de firmar, la supervisora ve el checklist base IPERC (va siempre) y decide solo los controles extra.
- "Reportes" lista las tareas cerradas, la más reciente primero. Cada una muestra el resultado (sin novedad, casi incidente o incidente), si se cumplieron los controles y la observación. El número de la pestaña suma los casi incidentes y los incidentes.

### Admin: sala de control

- El tablero sigue el recorrido de la solicitud: Juan → Agente PTW → NANDA → Área, Incidentes y Gemelo → Reglas → Decisión → destino. Mientras una etapa procesa, una luz recorre el tubo que llega a ella.
- Repetición fiel: el tablero completa una etapa por paso (900 ms) y nunca se adelanta a lo que el backend ya respondió. Con movimiento reducido muestra el estado real al instante.
- Al pasar el mouse, enfocar con el teclado o tocar una etapa, aparece el detalle en vivo de esa etapa:
  - Agente PTW: qué entendió la IA y si Juan lo confirmó o lo corrigió.
  - NANDA: las credenciales de cada agente.
  - Área y Reglas: tablas con valor, límite y base legal.
  - Incidentes: los casos similares.
  - Gemelo: la prueba `diagnostico: null`.
  - Decisión y destino: el nivel y a quién llega.
- Con menos de 1024 px de ancho, el tablero se vuelve una lista de etapas desplegables.
- Debajo del tablero están el nivel final, las fichas NANDA y las respuestas de los agentes en JSON.

## Contratos nuevos

Acordados con la sesión de backend el 2026-10-17. Todos son opcionales. Al 2026-10-17, el código de `agents/` y `contracts/` todavía no tiene ninguno, y el front funciona sin ellos:

| Contrato | Si el backend no lo tiene |
| --- | --- |
| `GET /actividades` | El front usa su copia de las 11 actividades ([src/pedido.ts](src/pedido.ts)). |
| `POST /tareas/interpretar` | Aparece "Elige la actividad" y el trabajador la elige de la lista. |
| `GET /labores` | La labor se acepta sin validar contra la lista. |
| `SolicitudPTW.actividad_id` e `interpretacion` | No se envían. El backend actual rechaza campos extra con 422, por eso el front solo los manda si `/tareas/interpretar` respondió. |
| `Ptw.resultado` y `Ptw.cerrado_en` | "Reportes" muestra las tareas cerradas sin el detalle del reporte. |
| `Ptw.checklist_base` | La supervisora no ve el checklist base antes de firmar. |
| `Ptw.evaluacion` | El admin muestra los motivos de `propuesta.porque` en lugar de la tabla de reglas. |
| `Ptw.tipo_tarea`, `Ptw.tipo_labor` y `Ptw.creado_en` | El admin muestra `solicitud.tarea` y ordena las solicitudes como llegan. |

Las formas exactas están en [src/tipos.ts](src/tipos.ts).

## Tests

```sh
npm test
```

- `privacidad.test.tsx`: aunque el backend envíe `diagnostico` u otros campos clínicos, no llegan al DOM (sala de control, detalle del supervisor, avatar en sus tres tamaños y su `aria-label`). La sala muestra `"diagnostico": null`.
- `bandeja.test.tsx`: los verdes sin alto riesgo nunca aparecen en la bandeja, ni los de la demo ni uno que el backend mande por error.
- `acceso.test.tsx`: cada usuario ve solo su vista; el admin ve las tres.
- `pedido.test.tsx`: actividad en texto libre, confianza baja, backend sin los contratos nuevos, validación de la labor y qué campos viajan en la solicitud.
- `gemelo3d.test.tsx`: parámetros del minero y respaldo 2D sin WebGL.
- `sala.test.ts` y `admin.test.tsx`: la repetición fiel y el detalle en vivo de cada etapa.
- `reportes.test.tsx`: pestaña Reportes, checklist base y firma con el nombre del usuario.
- `contratos.test.ts`: los contratos nuevos en los mocks.

## Conectar con la API real

Crea `.env.development.local` (pisa a `.env.development`; un `.env.local` no alcanza porque Vite le da menos prioridad):

```sh
VITE_USE_MOCKS=false
VITE_API_URL=http://localhost:8000
```

Con el backend local (`docker compose up -d --build` en la raíz), `vigia-ptw` responde en `http://localhost:8000` y ya acepta CORS desde `http://localhost:5173`.

- La API debe permitir CORS desde el origen del front.
- Los contratos están en [src/tipos.ts](src/tipos.ts). Las llamadas y el filtro de privacidad están en [src/api.ts](src/api.ts).
- Un PETAR se consulta cada 2 s mientras está en `procesando` o `en_revision` (el trabajador espera la firma en pantalla). La lista de solicitudes se refresca cada 4 s.

## Desplegar en Cloud Run

```sh
VITE_API_URL=https://vigia-ptw-xxxxx.southamerica-west1.run.app ./deploy.sh
# o, para una demo sin backend:
VITE_USE_MOCKS=true ./deploy.sh
```

`deploy.sh` escribe `.env.production` (Vite fija las variables al compilar) y ejecuta `gcloud run deploy vigia-web --source . --region southamerica-west1 --allow-unauthenticated --quiet` (la página es pública). La imagen compila con Node y sirve el estático con nginx en el puerto 8080 ([Dockerfile](Dockerfile), [nginx.conf](nginx.conf)). `make deploy` en la raíz lo llama al final con la URL de `vigia-ptw`.

## Integración con el backend

Probado contra `vigia-ptw` local (`MOCK_MODE=true`): solicitud → bandeja → firma con ajuste → inicio → reporte → cerrado. Los mocks de `src/mocks/` siguen las mismas reglas que el backend:

- El PETAR solo existe una vez emitido. Su checklist lleva siempre la base IPERC más los controles extra.
- Al firmar, "Aceptar" deja los extra propuestos; "Ajustar" envía en `controles_finales` solo los extra que quedan (el backend responde 422 si van vacíos). Por eso la supervisora edita solo los controles extra.
- "Empezar trabajo" llama a `POST /ptw/{id}/inicio` y el PETAR pasa a `en_ejecucion`.
- `explicacion` (texto que redacta Vigía para el supervisor) se muestra plegada bajo "Por qué llegó aquí". Sin `ANTHROPIC_API_KEY` el backend repite los motivos, por eso no se muestra abierta.

Limitaciones del contrato actual:

- La bandeja no trae `trabajador_id`; cada fila lo lee de `GET /ptw/{id}` para mostrar el avatar.
- `POST /ptw/{id}/firma` no tiene campo de motivo; al rechazar se envía `controles_finales: ["Motivo del rechazo: …"]`.

## Privacidad

El gemelo es zona clínica. [src/api.ts](src/api.ts) reconstruye campo por campo el PETAR, la respuesta del gemelo y la del avatar, con `diagnostico: null`. Si el backend envía un diagnóstico, se descarta y la sala de control lo avisa sin mostrarlo. `<AvatarGemelo>` y el gemelo 3D solo reciben aptitud, motivo visible y estado visual. El texto que escribe el trabajador solo va a `POST /tareas/interpretar`.

## Estructura

```
src/
  tipos.ts                 contratos de la API
  api.ts                   llamadas, filtro de privacidad y hooks de TanStack Query
  negocio.ts               regla de la bandeja y textos del dominio
  pedido.ts                actividad confirmada, labor, turno y armado de la solicitud
  sala.ts                  estado de la sala de control y repetición fiel
  sesion.tsx               usuarios de demo, sesión y permisos por ruta
  componentes/
    AvatarGemelo.tsx       ilustración SVG del gemelo (determinista por seed) y respaldo del 3D
    AvatarGemelo3D.tsx     gemelo en 3D (carga diferida)
    PedidoActividad.tsx    actividad en texto libre, labor y turno
    Sello.tsx              sello de nivel e íconos
    rasgos.ts              rasgos del minero a partir del seed
    admin/                 tablero de la sala de control, detalle por etapa y paneles
  tres/                    escena three.js, parámetros del minero y detección de WebGL
  vistas/                  Ingreso, Trabajador, Supervisor y Admin
  mocks/                   BD de demo, reglas del backend y handlers de MSW
  test/                    Vitest + Testing Library
```
