"""Vigía - UI de demo: vista trabajador, bandeja del supervisor y fuentes."""

import csv
import json
import os
import time
from pathlib import Path

import httpx
import streamlit as st

PTW_URL = os.getenv("PTW_URL", "http://localhost:8000").rstrip("/")
DATA = Path(__file__).resolve().parents[1] / "data"
COLORES = {"verde": "#1e8e3e", "ambar": "#e37400", "rojo": "#c5221f"}
DECISIONES = {"autorizar": "Autorizar", "autorizar_con_controles": "Autorizar con controles",
              "reasignar": "Reasignar o esperar"}
ESTADOS = {
    "procesando": "Procesando",
    "emitido": "PETAR emitido",
    "en_revision": "En revisión del supervisor",
    "bloqueado": "Bloqueado",
    "autorizado_con_controles": "Autorizado con controles",
    "rechazado": "Rechazado",
    "en_ejecucion": "En ejecución",
    "cerrado": "Cerrado",
}

st.set_page_config(page_title="Vigía - PETAR dinámico", page_icon="⛑️", layout="wide")


def api(metodo: str, ruta: str, **kwargs):
    try:
        respuesta = httpx.request(metodo, f"{PTW_URL}{ruta}", timeout=180, **kwargs)
    except httpx.HTTPError as e:
        st.error(f"No se pudo conectar con vigia-ptw en {PTW_URL}: {e}")
        st.stop()
    if respuesta.status_code >= 400:
        st.error(f"Error {respuesta.status_code}: {respuesta.json().get('detail', respuesta.text)}")
        return None
    return respuesta.json()


def semaforo(propuesta: dict) -> None:
    supervisor = " · requiere supervisor" if propuesta["requiere_supervisor"] else ""
    st.markdown(
        f"<div style='background:{COLORES[propuesta['nivel']]};color:white;padding:0.6rem 1rem;"
        f"border-radius:0.5rem;font-weight:600;font-size:1.1rem'>{propuesta['nivel'].upper()} · "
        f"{DECISIONES[propuesta['decision']]}{supervisor}</div>",
        unsafe_allow_html=True,
    )


def avatar(trabajador_id: str) -> None:
    datos = api("GET", f"/trabajadores/{trabajador_id}/avatar")
    if not datos:
        return
    visual = datos["estado_visual"]
    casco, texto = st.columns([1, 5])
    casco.markdown(
        f"<div style='width:64px;height:64px;border-radius:50%;background:{datos['color_casco']};"
        f"border:3px solid #333;margin:auto'></div>",
        unsafe_allow_html=True,
    )
    texto.markdown(f"**{datos['nombre']}** · {datos['cargo']} · {datos['empresa']} ({datos['empleador']})")
    texto.progress(visual["energia"] / 100, text=f"Energía {visual['energia']}/100 · día {visual['dia_rotacion']} "
                   f"de {visual['total_rotacion']} · exposición {visual['exposicion_nivel']}")
    texto.caption(f"{visual['apto_para_tarea'].replace('_', ' ')}: {visual['motivo_visible']}")
    st.line_chart(visual["historial_energia"], height=120)


def detalle(ptw: dict) -> None:
    st.caption(f"{ESTADOS[ptw['estado']]} · NANDA: "
               + (", ".join(f"{a['id']} ({a['firma']})" for a in ptw["nanda"]) or "sin respuesta"))
    if not ptw.get("propuesta"):
        return
    propuesta = ptw["propuesta"]
    semaforo(propuesta)
    izquierda, derecha = st.columns([3, 2])
    with izquierda:
        st.markdown("**Por qué**")
        for motivo in propuesta["porque"]:
            st.markdown(f"- {motivo}")
        st.markdown("**Controles extra**")
        for control in propuesta["controles_extra"] or ["Ninguno"]:
            st.markdown(f"- {control}")
        st.markdown(f"**Alternativa:** {propuesta['alternativa']}")
        if ptw.get("explicacion"):
            st.info(ptw["explicacion"], icon="📝")
    with derecha:
        consultas = ptw["consultas"]
        if consultas["area"].get("data"):
            st.markdown("**Condiciones de la labor**")
            st.dataframe([consultas["area"]["data"]], hide_index=True)
        if consultas["gemelo"].get("data"):
            aptitud = consultas["gemelo"]["data"]
            st.markdown(f"**Aptitud (zona clínica):** {aptitud['apto_para_tarea'].replace('_', ' ')}")
            st.caption(f"{aptitud['motivo_visible']}. Sin detalle clínico.")
        if consultas["incidentes"].get("data"):
            incidentes = consultas["incidentes"]["data"]
            st.markdown(f"**Incidentes similares:** {incidentes['casos_similares']} "
                        f"(potencial máx. {incidentes['riesgo_potencial_max']})")
            st.caption(incidentes["patron"])
    if ptw.get("petar"):
        petar = ptw["petar"]
        firma = petar["firmado_por"] or "emisión automática"
        with st.expander(f"{petar['numero']} · {firma} · {len(petar['checklist'])} controles"):
            for control in petar["checklist"]:
                st.markdown(f"- {control}")


def esperar_evaluacion(ptw_id: str) -> dict:
    with st.status("Consultando agentes en paralelo...", expanded=True) as estado:
        vistas: set[str] = set()
        while True:
            ptw = api("GET", f"/ptw/{ptw_id}")
            for agente, consulta in ptw["consultas"].items():
                if consulta["estado"] != "pendiente" and agente not in vistas:
                    vistas.add(agente)
                    st.write(f"{'✅' if consulta['estado'] == 'ok' else '⚠️'} {agente}")
            if ptw["estado"] != "procesando":
                estado.update(label=ESTADOS[ptw["estado"]], state="complete")
                return ptw
            time.sleep(0.5)


def vista_trabajador() -> None:
    st.header("Solicitar permiso de trabajo (PETAR)")
    solicitudes = json.loads((DATA / "synthetic" / "solicitudes.json").read_text(encoding="utf-8"))
    i = st.selectbox("Caso de demo", range(len(solicitudes)), format_func=lambda n: solicitudes[n]["caso"])
    base = solicitudes[i]["solicitud"]
    with st.form("solicitud"):
        c1, c2, c3 = st.columns(3)
        tarea = c1.text_input("Tarea", base["tarea"], key=f"tarea{i}")
        labor = c2.text_input("Labor", base["labor"], key=f"labor{i}")
        trabajador_id = c3.text_input("Trabajador", base["trabajador_id"], key=f"trab{i}")
        turno = c1.selectbox("Turno", ["dia", "noche"], index=["dia", "noche"].index(base["turno"]), key=f"turno{i}")
        tipo_mineria = c2.selectbox("Tipo de minería", ["subterranea", "tajo_abierto"],
                                    index=["subterranea", "tajo_abierto"].index(base["tipo_mineria"]), key=f"tm{i}")
        empleador = c3.selectbox("Empleador", ["titular", "contratista"],
                                 index=["titular", "contratista"].index(base["empleador"]), key=f"emp{i}")
        altitud = c1.number_input("Altitud (msnm)", 0, 6500, base["altitud_msnm"], key=f"alt{i}")
        enviado = st.form_submit_button("Solicitar PETAR", type="primary")
    avatar(trabajador_id)
    if enviado:
        aceptada = api("POST", "/ptw/solicitud", json={
            "tarea": tarea, "labor": labor, "turno": turno, "trabajador_id": trabajador_id,
            "altitud_msnm": int(altitud), "tipo_mineria": tipo_mineria, "empleador": empleador,
        })
        if aceptada:
            detalle(esperar_evaluacion(aceptada["ptw_id"]))

    st.subheader("Mis permisos")
    for ptw in api("GET", "/ptw", params={"trabajador_id": trabajador_id}) or []:
        titulo = f"{ptw['ptw_id']} · {ptw['solicitud']['tarea']} · {ESTADOS[ptw['estado']]}"
        with st.expander(titulo, expanded=ptw["estado"] in ("emitido", "autorizado_con_controles", "en_ejecucion")):
            detalle(ptw)
            if ptw["estado"] in ("emitido", "autorizado_con_controles"):
                if st.button("Iniciar tarea", key=f"inicio_{ptw['ptw_id']}") and api("POST", f"/ptw/{ptw['ptw_id']}/inicio"):
                    st.rerun()
            if ptw["estado"] in ("emitido", "autorizado_con_controles", "en_ejecucion"):
                with st.form(f"resultado_{ptw['ptw_id']}"):
                    resultado = st.radio("Resultado", ["sin_novedad", "casi_incidente", "incidente"], horizontal=True)
                    cumplidos = st.checkbox("Cumplí todos los controles", value=True)
                    observacion = st.text_area("Observación")
                    if st.form_submit_button("Reportar fin de tarea") and api(
                        "POST", f"/ptw/{ptw['ptw_id']}/resultado",
                        json={"resultado": resultado, "controles_cumplidos": cumplidos, "observacion": observacion},
                    ):
                        st.rerun()


def vista_supervisor() -> None:
    st.header("Bandeja del supervisor")
    st.caption("Solo llegan los casos en duda: ámbar o trabajo de alto riesgo (revisión) y rojos (aviso). "
               "Los verdes se emiten solos.")
    items = api("GET", "/ptw/bandeja") or []
    if not items:
        st.info("Bandeja vacía.")
    for item in items:
        ptw = api("GET", f"/ptw/{item['ptw_id']}")
        icono = "✍️ Revisión" if item["tipo"] == "revision" else "🚫 Aviso"
        with st.container(border=True):
            st.subheader(f"{icono} · {item['trabajador_nombre']} · {item['tarea']} · {item['labor']}")
            st.caption(f"{item['ptw_id']} · turno {item['turno']} · {item['creado_en'][:16].replace('T', ' ')}")
            detalle(ptw)
            if item["tipo"] != "revision":
                continue
            propuesta = ptw["propuesta"]
            with st.form(f"firma_{item['ptw_id']}"):
                supervisor = st.text_input("Supervisor que firma")
                accion = st.radio("Acción", ["aceptar", "ajustar", "rechazar"], horizontal=True)
                finales = st.multiselect("Controles extra finales (al ajustar)", propuesta["controles_extra"],
                                         default=propuesta["controles_extra"])
                adicional = st.text_input("Control adicional (opcional, al ajustar)")
                if st.form_submit_button("Firmar", type="primary"):
                    cuerpo = {"accion": accion, "supervisor": supervisor, "controles_finales": []}
                    if accion == "ajustar":
                        cuerpo["controles_finales"] = finales + ([adicional] if adicional.strip() else [])
                    if api("POST", f"/ptw/{item['ptw_id']}/firma", json=cuerpo):
                        st.rerun()

    st.header("Historial")
    st.dataframe(
        [
            {
                "ptw": p["ptw_id"],
                "estado": ESTADOS[p["estado"]],
                "nivel": (p.get("propuesta") or {}).get("nivel", ""),
                "tarea": p["solicitud"]["tarea"],
                "labor": p["solicitud"]["labor"],
                "trabajador": p["solicitud"]["trabajador_id"],
                "petar": (p.get("petar") or {}).get("numero", ""),
                "firmado_por": (p.get("petar") or {}).get("firmado_por") or "",
            }
            for p in api("GET", "/ptw") or []
        ],
        hide_index=True,
    )


def vista_fuentes() -> None:
    st.header("Fuentes de reglas y datos")
    with (DATA / "sheets" / "fuentes.csv").open(encoding="utf-8") as f:
        fuentes = list(csv.DictReader(f))
    st.dataframe(fuentes, hide_index=True, column_config={"link": st.column_config.LinkColumn("link")})


with st.sidebar:
    st.title("⛑️ Vigía")
    st.caption("PETAR / IPERC continuo dinámico · DS 024-2016-EM")
    vista = st.radio("Vista", ["Trabajador", "Supervisor", "Fuentes"])
    salud = api("GET", "/health")
    st.caption(f"vigia-ptw: {PTW_URL} · mock: {salud['mock_mode'] if salud else '?'}")
    st.caption("La decisión la toman reglas con base legal. El supervisor solo revisa los casos en duda.")

{"Trabajador": vista_trabajador, "Supervisor": vista_supervisor, "Fuentes": vista_fuentes}[vista]()
