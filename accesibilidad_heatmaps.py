# accesibilidad_heatmaps.py
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import altair as alt

# Paletas seguras para distintos tipos de daltonismo
# Nota: "Predeterminada (sin filtro)" usa 'blues' para volver al look original.
CB_PALETTES = {
    "Predeterminada (sin filtro)": "blues",
    "Protanopia (rojo débil)": "cividis",
    "Deuteranopia (verde débil)": "plasma",
    "Tritanopia (azul débil)": "magma",
    "Acromatopsia (monocromático)": "greys",
}

def _ui_accesibilidad(default_scheme: str = "blues") -> str:
    """
    UI de accesibilidad: checkbox + select de tipo de daltonismo.
    Si el checkbox está apagado, devuelve la paleta por defecto (default_scheme).
    """
    activar = st.checkbox("♿ Modo de inclusión (daltonismo)", value=False)
    if not activar:
        return default_scheme

    tipo = st.selectbox(
        "Selecciona tu tipo de daltonismo:",
        [
            "Protanopia (rojo débil)",
            "Deuteranopia (verde débil)",
            "Tritanopia (azul débil)",
            "Acromatopsia (monocromático)",
            "Predeterminada (sin filtro)",
        ],
        help="Aplica una paleta perceptualmente uniforme apropiada para tu visión.",
    )
    return CB_PALETTES.get(tipo, default_scheme)

# ---------- RENDERIZADORES (privados) ----------

def _heatmap_mensual(
    potencia_horaria: pd.Series,
    scheme: str,
    orden_meses=("Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"),
    titulo="Potencia Horaria Agregada por Mes (W)",
    height=420,
    # === MODIFICACIÓN 1: Añadir argumento para multiplicadores ===
    multiplicadores_estacionales=None, 
):
    # Normalizar índice 0..23
    ph = potencia_horaria.copy()
    ph.index = pd.Index([int(str(h)) for h in ph.index])
    if len(ph) != 24 or sorted(ph.index.tolist()) != list(range(24)):
        raise ValueError("La Serie 'potencia_horaria' debe tener exactamente horas 0..23.")

    # Asegurarse de que los multiplicadores sean un diccionario válido, si no, usar 1.0 para todos
    if multiplicadores_estacionales is None:
        multiplicadores_estacionales = {mes: 1.0 for mes in orden_meses} 

    # === MODIFICACIÓN 2: Aplicar el multiplicador del mes ===
    # La potencia horaria base (ph.loc[h]) se multiplica por el factor de ajuste del mes.
    df_mensual = pd.DataFrame(
        [
            (mes, h, ph.loc[h] * multiplicadores_estacionales.get(mes, 1.0)) 
            for mes in orden_meses 
            for h in range(24)
        ],
        columns=["Mes", "Hora", "Potencia (W)"]
    )
    # =======================================================
    
    df_mensual["Mes"] = pd.Categorical(df_mensual["Mes"], categories=list(orden_meses), ordered=True)
    df_mensual["Hora"] = df_mensual["Hora"].astype(int)

    chart = (
        alt.Chart(df_mensual)
        .mark_rect()
        .encode(
            x=alt.X("Hora:O", title="Hora del Día", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Mes:O", title="Mes", sort=list(orden_meses)),
            color=alt.Color("Potencia (W):Q", scale=alt.Scale(scheme=scheme), legend=alt.Legend(title="Potencia (W)")),
            tooltip=[alt.Tooltip("Mes:N"), alt.Tooltip("Hora:Q"), alt.Tooltip("Potencia (W):Q", format=",.0f")],
        )
        .properties(title=titulo, height=height)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)

def _heatmap_diario_por_carga(
    df_base: pd.DataFrame,
    scheme: str,
    titulo="Potencia por Carga Individual y Hora",
    height=420
):
    columnas_horas = [f"{i}" for i in range(24)]
    df_heatmap_diario_wide = df_base[columnas_horas].mul(df_base["Potencia (W)"], axis=0)
    df_heatmap_diario_wide["Carga"] = df_base["Carga"]
    df_long = df_heatmap_diario_wide.melt(
        id_vars=["Carga"], var_name="Hora", value_name="Potencia (W)"
    )
    df_long["Hora"] = df_long["Hora"].astype(int)

    chart = (
        alt.Chart(df_long)
        .mark_rect()
        .encode(
            x=alt.X("Hora:O", title="Hora del Día", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Carga:O", title="Carga Eléctrica"),
            color=alt.Color("Potencia (W):Q", scale=alt.Scale(scheme=scheme), legend=alt.Legend(title="Potencia (W)")),
            tooltip=["Carga", "Hora", alt.Tooltip("Potencia (W)", format=",.0f")],
        )
        .properties(title=titulo, height=height)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)

# ---------- API PÚBLICA ----------

def render_mapa_calor_accesible(
    df_base: pd.DataFrame,
    potencia_horaria: pd.Series,
    default_view: str = "Horario diario (0-23)",
    default_scheme: str = "blues",
    height: int = 420,
    # === MODIFICACIÓN 3: Añadir argumento aquí también ===
    multiplicadores_estacionales=None, 
):
    """
    Selector + mapa de calor accesible.
    - 'default_view': "Horario diario (0-23)" o "Horario mensual (12 meses)".
    - 'default_scheme': paleta por defecto cuando el modo de inclusión está DESactivado.
    """
    st.radio(
        "Selecciona el formato del mapa de calor:",
        options=["Horario diario (0-23)", "Horario mensual (12 meses)"],
        index=0 if default_view == "Horario diario (0-23)" else 1,
        key="fmt_heatmap_selector",
        horizontal=True,
        help="Cambia entre visión diaria (por carga) y mensual (12×24).",
    )
    # Leer la selección del estado (evita recrear radio cuando se reusa la función)
    formato = st.session_state.get("fmt_heatmap_selector", "Horario diario (0-23)")

    # UI de accesibilidad: devuelve la paleta a usar
    scheme = _ui_accesibilidad(default_scheme=default_scheme)

    st.markdown("### 4.1. Mapa de Calor: Carga vs. Hora (W)" if formato.startswith("Horario diario") else
                "### 4.1. Mapa de Calor: Mes vs. Hora (W)")

    if formato == "Horario diario (0-23)":
        _heatmap_diario_por_carga(df_base=df_base, scheme=scheme, height=height)
    else:
        # === MODIFICACIÓN 4: Pasar el argumento a la función interna ===
        _heatmap_mensual(
            potencia_horaria=potencia_horaria, 
            scheme=scheme, 
            height=height,
            multiplicadores_estacionales=multiplicadores_estacionales 
        )
        # ==============================================================

# Compatibilidad con tu integración previa (si la usas en otros lados)
def render_mapa_calor_mensual(potencia_horaria: pd.Series, **kwargs):
    scheme = _ui_accesibilidad(default_scheme=kwargs.pop("default_scheme", "blues"))
    # === MODIFICACIÓN 5: Capturar el nuevo argumento de kwargs (si se usa compatibilidad) ===
    multiplicadores_estacionales = kwargs.pop("multiplicadores_estacionales", None)
    _heatmap_mensual(
        potencia_horaria=potencia_horaria, 
        scheme=scheme,
        multiplicadores_estacionales=multiplicadores_estacionales, # <--- Pasar el nuevo argumento
        **kwargs
    )
    # ==============================================================

def render_mapa_calor_diario_por_carga(df_base: pd.DataFrame, **kwargs):
    scheme = _ui_accesibilidad(default_scheme=kwargs.pop("default_scheme", "blues"))
    _heatmap_diario_por_carga(df_base=df_base, scheme=scheme, **kwargs)