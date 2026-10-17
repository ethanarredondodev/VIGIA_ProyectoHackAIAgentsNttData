# Diseño: usuarios, sala de control del admin, gemelo 3D y tarea en texto libre

Fecha: 2026-10-17. Alcance: `web/` (front de Vigía) más cambios aditivos de contrato que implementa la sesión de backend.

## Por qué

Vigía se presenta ante el jurado del Reto M1 (minería peruana). Hoy el front tiene tres vistas abiertas para cualquiera y un monitor técnico. Se necesita:

- Que cada persona entre como quien es y vea solo lo suyo.
- Que el admin pueda mostrar y explicar, en vivo, cómo razona Vigía con cada solicitud.
- Que el trabajador, con guantes y poca luz, escriba su tarea con sus palabras en vez de buscarla en una lista, y que su gemelo sea memorable (3D).

## Punto de partida

- `web/`: React 18, Vite, TypeScript, Tailwind 4, TanStack Query, React Router 6 y MSW. Vistas `/trabajador`, `/supervisor` y `/monitor`. Avatar 2D en SVG (`src/componentes/AvatarGemelo.tsx`). 14 tests de Vitest pasan (privacidad, bandeja y cadena de confianza NANDA).
- La sesión de backend agregó al monitor la credencial NANDA de cada agente (`emisores`, `credencial_vence`, `motivo`) y la evidencia firmada de cada consulta (`evidencia`). Se conservan.
- Backend `vigia-ptw`: contratos en `contracts/modelos.py`; `GET /ptw` lista PETAR; la tarea se clasifica por palabras clave (`contracts/vocabulario.py`, `clasificar_tarea`); Claude solo redacta (`agents/comun/llm.py`) y siempre hay un texto de respaldo determinista. La API no tiene autenticación.

## Objetivos

1. Tres usuarios con su propia vista: trabajador, supervisor y admin.
2. Admin: sala de control animada que muestra el recorrido real de cada solicitud, con detalle en vivo al pasar el mouse.
3. Trabajador: gemelo en 3D y actividad en texto libre que la IA compara con la tabla de actividades, confirmada por el trabajador. Reportes de cierre visibles para el supervisor.
4. Mejoras visuales basadas en la investigación: fondo neutro y color solo para lo anormal (ISA-101), objetivos táctiles grandes para guantes, razonamiento fiel con pasos reales.

## No objetivos

- Autenticación real con contraseñas o tokens: el usuario eligió el ingreso de demo. La API sigue abierta.
- Rediseñar el flujo del supervisor: se mantiene, con ajustes de consistencia visual.
- Mostrar "pensamientos" de un modelo de lenguaje: el admin ve lo que el sistema hizo, con sus datos.

## Anti-objetivos (fracaso aunque funcione)

- Cualquier dato clínico en pantalla, incluido el avatar 3D.
- Que la IA decida o cambie el nivel de riesgo: lo deciden las reglas con base legal.
- Una animación que invente pasos, datos u orden. Solo el ritmo se ajusta para que se pueda leer.
- Un 3D que vuelva lenta o ilegible la pantalla del trabajador en un celular modesto.
- Romper los contratos actuales: todo cambio es aditivo y opcional.

## Restricciones

- El front se trabaja solo en `web/`. Lo del backend lo implementa la sesión de backend, coordinado por mensaje antes de empezar.
- Con `VITE_USE_MOCKS=true` todo funciona sin backend: los mocks de MSW cubren los contratos nuevos.
- Accesibilidad: el color siempre va con texto o ícono, foco visible, `prefers-reduced-motion` respetado, objetivos táctiles de 56 px o más en la vista del trabajador.
- Privacidad: `src/api.ts` sigue filtrando el gemelo y el avatar por lista blanca; los tests de privacidad se mantienen y cubren las vistas nuevas.
- Rendimiento: three.js se carga solo en la vista del trabajador (import dinámico). Una sola dependencia nueva: `three`.

## Ingreso por usuario (decidido por el usuario: demo sin contraseña)

- Pantalla de inicio "¿Quién eres?" con tres usuarios de demo, sin contraseña:
  - Juan Mamani Quispe, trabajador (`T-001`), entra a `/trabajador`.
  - Ing. Rosa Quispe, supervisora, entra a `/supervisor`.
  - Administración, entra a `/admin`.
- El usuario elegido se guarda por pestaña (`sessionStorage`), para que en la demo cada pestaña sea una persona distinta.
- Cada uno ve solo su menú. Trabajador y supervisor no pueden abrir otras rutas (se redirigen a la suya). El admin puede abrir las tres vistas.
- La cabecera muestra el nombre y "Cambiar de usuario". `/monitor` redirige a `/admin`.

## Vista admin: sala de control (aprobada con maqueta)

Referencia visual: [maquetas/sala-control-v3.html](maquetas/sala-control-v3.html) (maqueta aprobada).

- Tablero oscuro con el recorrido: Trabajador → Agente PTW → NANDA → [Incidentes ‖ Área ‖ Gemelo] → Reglas → Decisión → destino.
- El trabajador es el punto de partida, con su avatar 2D (el de la solicitud, desde `/trabajadores/{id}/avatar`). La luz de su lámpara es la solicitud: una chispa recorre cada tubo. Cuando responde el gemelo, su anillo y su cara cambian (aptitud, párpados). Al final una chispa vuelve a él con lo que recibió.
- El destino depende del nivel:
  - Verde sin alto riesgo: "PETAR emitido" y vuelve al trabajador como permiso emitido.
  - Ámbar o alto riesgo: "Bandeja de Ing. Rosa Quispe"; el trabajador recibe "Tu supervisor está revisando".
  - Rojo: "Tarea bloqueada"; el supervisor recibe un aviso y el trabajador, la alternativa.
- Cada etapa se enciende cuando el dato real llega. Al pasar el mouse, enfocar con teclado o tocar una etapa, aparece al costado un detalle que se actualiza en vivo: arriba la fase ("En espera", "Procesando…" o "Listo") y debajo los pasos a medida que ocurren:
  - Trabajador: actividad elegida de la tabla, labor, turno, altitud y estado del gemelo.
  - Agente PTW: lo que propuso la IA (tarea y confianza), si el trabajador lo confirmó o lo corrigió, y la labor. Si el backend no trae esos datos, solo "tarea confirmada por el trabajador"; nunca se muestra un paso que no ocurrió.
  - NANDA: cada agente con su credencial (emisores y vencimiento) o el motivo del descarte.
  - Incidentes: casos similares, patrón y potencial; evidencia firmada.
  - Área: tabla de medidas con valor, límite y resultado.
  - Gemelo: aptitud, motivo visible y `diagnostico: null`.
  - Reglas: tabla de verificación fila por fila (dato, valor, límite, resultado, base legal); el nivel es el más alto.
  - Decisión: nivel, controles base (`checklist_base`) y extra, y a dónde va.
- Ritmo ("repetición fiel"): los cambios que llegan por la consulta cada 2 s entran a una cola y se reproducen en orden, con un mínimo de 0.8 a 1.5 s por etapa. Si el backend responde en milisegundos, la secuencia igual dura unos 10 s; si es más lento, la animación espera al dato y nunca se adelanta.
- El admin elige qué solicitud mirar en una lista de recientes (`GET /ptw`, con nivel y estado); por defecto, la última. Se mantiene el botón "Nueva solicitud de demo".
- Debajo del tablero quedan el indicador grande del nivel final, las credenciales NANDA con la evidencia firmada y el JSON de cada respuesta (plegable), con la prueba de `diagnostico: null`.
- En pantallas de menos de 1024 px el tablero se reemplaza por una lista vertical de etapas, en el mismo orden, cada una con su estado y su detalle en vivo al tocarla; sin tubos ni chispas. La vista está pensada para pantalla grande.

## Vista del trabajador (aprobada con maqueta)

Referencia visual: [maquetas/trabajador-3d.html](maquetas/trabajador-3d.html) (maqueta aprobada).

- Gemelo 3D arriba: Juan en un socavón de roca facetada; la lámpara del casco alumbra de verdad (foco, haz visible y halo) y su brillo sigue a `energia`. Con energía menor a 40 se le caen los párpados. Un anillo en el piso toma el color de la aptitud. Se puede girar arrastrando (con límites). Respira y mueve la cabeza despacio, y con eso el haz recorre la roca; nada de esto ocurre con `prefers-reduced-motion`.
- Debajo del 3D, siempre en texto: aptitud, "Día N de M", "Exposición: …", energía, mini gráfico de 14 días y motivo visible.
- El minero 3D se arma con formas simples de three.js, sin modelos externos, y es determinista desde `seed` (piel, peinado, color de ropa) y `color_casco`. Recibe solo los datos del avatar ya filtrados. El lienzo tiene `role="img"` y un `aria-label` con nombre, aptitud y motivo, igual que el 2D.
- Respaldo 2D: se muestra el avatar 2D actual mientras carga three.js, si el navegador no tiene WebGL o si el celular pide ahorro de datos (`navigator.connection.saveData`).
- Actividad en texto libre (decidido por el usuario: el trabajador escribe solo la actividad; su salud la aporta el área clínica a través del gemelo; la actividad se compara con la lista de la tabla de actividades):
  - "¿Qué actividad vas a realizar?" con un campo grande y la ayuda "Escribe solo la actividad. No escribas datos de salud: de eso se encarga el área clínica." El texto va a Claude (un tercero) para interpretarlo; el backend no lo guarda ni lo registra.
  - Al dejar de escribir (unos 700 ms), el front pide la interpretación a `POST /tareas/interpretar`, que compara el texto con la tabla de actividades, y muestra "Vigía entendió": actividad y labor. Debajo, "¿No es eso? Elige la actividad" con las otras actividades de la tabla (`GET /actividades`) para corregir con un toque, y al final "Otra actividad".
  - Confirmación: con confianza alta, tocar "Pedir permiso" con la tarjeta "Vigía entendió" a la vista cuenta como confirmación. Con confianza media o baja, la tarjeta pregunta "¿Es esto?" y el trabajador debe tocar la tarea (la propuesta u otra) antes de poder pedir el permiso.
  - "Otra actividad" envía `actividad_id: "otro"`; el backend la convierte en `tipo_tarea: "otro"` y la trata como trabajo que requiere al supervisor, porque una actividad que no está en la tabla es un caso con duda.
  - Labor: solo se aceptan labores que existen. La lista sale de `GET /labores`; la interpretación devuelve `labor` solo si coincide con una de ellas. Si no la encontró, se le pide elegirla con un campo que sugiere las labores existentes mientras escribe. Se elimina la lista fija actual del front (dos de sus tres labores no existen en el backend).
  - "Pedir permiso" se habilita con la actividad confirmada y una labor válida. Se envía `SolicitudPTW` con `tarea` = nombre de la actividad en la tabla (por ejemplo "Perforación de frente"), `actividad_id` = el de esa fila, `interpretacion` = lo que propuso la IA (actividad y confianza), `labor`, `turno` (según la hora, editable) y el perfil. El cliente nunca envía `tipo_tarea`: el servidor lo deriva de la tabla, así nadie puede elegir un tipo de menor riesgo para evitar la firma.
  - El texto que escribió el trabajador no se envía ni se guarda: solo sirve para la comparación. La excepción es "Otra actividad", donde el texto es la única descripción y se envía en `tarea` para que el supervisor sepa qué se pidió.
  - Si la interpretación falla o el backend aún no la tiene, se muestra la lista de actividades para elegir a mano y se envía sin `actividad_id` ni `interpretacion`.
- El resto del flujo no cambia: procesando, resultado, checklist, `POST /ptw/{id}/inicio` y reporte.

## Vista del supervisor

- Mismo flujo: bandeja "Por revisar" y "Avisos", detalle y firma (aceptar, ajustar los controles extra o rechazar con motivo). Antes de firmar ve también el checklist base (`checklist_base`).
- Pestaña nueva "Reportes" (decidido por el usuario): cada tarea cerrada con el avatar del trabajador, la actividad, la labor, la fecha, el resultado (sin novedad, casi incidente o incidente, siempre con texto e ícono), si cumplió los controles y la observación. Primero los más recientes; el contador de la pestaña muestra cuántos casi incidentes o incidentes hay.
- Ajustes visuales para que sea consistente con las otras vistas (cabecera con el usuario).

## Contratos nuevos (todos opcionales y aditivos)

Los implementa la sesión de backend; el front los usa con MSW mientras tanto y funciona sin ellos.

| Contrato | Para qué | Si el backend no lo tiene |
| --- | --- | --- |
| Tabla de actividades `data/sheets/actividades.csv` (hoja de cálculo publicable como Google Sheet, igual que las otras; decidido por el usuario): `id, actividad, tipo_tarea, sinonimos, estado`. Una fila por actividad que la mina autoriza; arranca con las 11 tareas de `TIPOS_TAREA`. | La lista contra la que se compara lo que escribe el trabajador | — |
| `GET /actividades` → `[{id, actividad, tipo_tarea}]` | Opciones para corregir la actividad | El front no puede ofrecer la lista |
| `POST /tareas/interpretar` `{texto}` → `{actividad: {id, actividad, tipo_tarea} \| null, labor \| null, tipo_labor \| null, confianza: "alta" \| "media" \| "baja", alternativas: [{id, actividad, tipo_tarea}]}`. Claude compara con la tabla; respaldo con los sinónimos de la tabla y `clasificar_labor`. | Actividad en texto libre | El trabajador elige la actividad de la lista |
| `GET /labores` → `[{labor, tipo_labor}]` (las labores con datos en el agente de área) | Que la labor exista y el agente de área responda | El trabajador escribe la labor sin validación, como hoy |
| `SolicitudPTW.actividad_id?` (una fila de la tabla, o `"otro"`). El backend deriva `tipo_tarea` de la tabla en lugar de clasificar por palabras clave; `null` u `"otro"` → `tipo_tarea: "otro"`, que exige supervisor. | Respetar lo que el trabajador confirmó sin que el cliente elija el tipo | El front no lo envía |
| `SolicitudPTW.interpretacion?: {actividad_id, confianza}` (lo que propuso la IA) | Que el admin muestre qué entendió la IA y si el trabajador lo corrigió | El admin solo muestra la actividad confirmada |
| `Ptw.resultado?: {resultado, controles_cumplidos, observacion}` y `Ptw.cerrado_en?` | Pestaña "Reportes" del supervisor | La pestaña muestra los PETAR cerrados sin el detalle del reporte |
| `Ptw.tipo_tarea?`, `Ptw.tipo_labor?`, `Ptw.creado_en?` y `Ptw.checklist_base?: string[]` (controles base, ya disponibles antes de la firma) | Detalle del Agente PTW y de Decisión, orden de la lista del admin, checklist base visible al supervisor antes de firmar | Se muestra `solicitud.tarea`, se omite el checklist base y se ordena como llega |
| `Ptw.evaluacion?: [{dato, valor, limite \| null, resultado: "ok" \| "ambar" \| "rojo", base_legal \| null, fuente}]`, incluidas las reglas que pasan; `fuente` es el id del agente. La fila de aptitud solo trae `{dato: "Aptitud", valor: apto_para_tarea, limite: null, base_legal: null, fuente: "vigia-gemelo"}`, sin valores clínicos. | Tabla de Reglas y de Área en el admin | Se muestran los motivos de `propuesta.porque` |

El front solo envía `actividad_id` e `interpretacion` cuando `POST /tareas/interpretar` respondió, porque llegan en el mismo cambio del backend; así no se manda un campo que el backend actual rechazaría con 422. Formas revisadas y aceptadas por la sesión de backend el 2026-10-17.

## Pruebas

- Se mantienen los 14 tests; los del monitor pasan a la ruta `/admin`.
- Nuevos:
  - Acceso por usuario: el trabajador no ve supervisor ni admin; el supervisor no ve admin; el admin ve todo.
  - Tarea en texto libre con MSW: texto → "Vigía entendió" → corregir → la solicitud lleva `tipo_tarea` e `interpretacion`; con confianza baja no se puede pedir sin tocar una tarea; si la interpretación falla, aparece la lista manual y la solicitud va sin `tipo_tarea`.
  - Labor: una labor que no existe no habilita "Pedir permiso".
  - El texto libre no viaja en la solicitud (salvo "Otra actividad").
  - Reportes: el supervisor ve los PETAR cerrados con su resultado; los verdes también aparecen aquí, porque son reportes y no casos por revisar.
  - Privacidad del 3D: los parámetros del minero salen solo del estado visual; en jsdom (sin WebGL) se muestra el respaldo 2D sin datos clínicos.
  - Admin: el detalle en vivo muestra la fase correcta según los datos y nunca muestra `diagnostico`.
- Revisión visual con capturas a 360, 390, 1280, 1366 y 1920 px, en claro y oscuro, y con movimiento reducido.

## Decisiones tomadas por Claude (revisables)

- `sessionStorage` por pestaña para el usuario de demo.
- Los datos simulados (MSW) usan los datos sintéticos de la base de datos del backend (trabajadores, labores, casos e incidentes, sin nada clínico) y sus mismas reglas, para que la demo sea igual con y sin backend.
- three.js directo, sin React Three Fiber, para sumar una sola dependencia.
- En el diagrama del admin el trabajador va en 2D (más liviano); el 3D vive en la vista del trabajador.
- La lista de tareas disponibles es `TIPOS_TAREA` sin "otro" (11 tareas), más la opción "Otra tarea".
- Regla de confirmación según la confianza de la IA (alta: confirmación implícita al pedir; media o baja: toque explícito).
- "Otra tarea" va siempre al supervisor.
- Labores validadas contra `GET /labores`.
- Contratos extra para que el admin no invente pasos (`interpretacion`, `tipo_labor`, `checklist_base`).
- En pantallas angostas, el admin usa una lista vertical de etapas en lugar del tablero.

## Lo que queda al constructor

Estructura de componentes y archivos, nombres internos, curvas y duraciones exactas de animación, cantidad y forma de las rocas, debounce exacto, y cómo reutilizar el SVG del avatar 2D dentro del diagrama.
