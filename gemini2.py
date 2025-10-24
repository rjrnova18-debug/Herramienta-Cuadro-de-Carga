import streamlit as st
import pandas as pd
import numpy as np
import io
import altair as alt 
from accesibilidad_heatmaps import render_mapa_calor_accesible
import streamlit.components.v1 as components


st.set_page_config(page_title="Cuadro de Carga - Dashboard", layout="wide")

# ======== TÍTULO GENERAL ========
st.title("📊 Cuadro de Carga (Load Duration Curve)")
st.markdown("Bienvenido al sistema para cargar, validar y analizar datos eléctricos.")

# ======== PESTAÑAS ========
tab1, tab2 = st.tabs(["⚡ Carga y Validación de Datos", "⚙️ Procesamiento y Análisis"])

# Función auxiliar para reindexar la columna Item
def reindexar_items(df):
    """Asigna un índice secuencial (1, 2, 3...) a la columna 'Item'."""
    if not df.empty:
        # Crea una nueva columna 'Item' basada en el índice actual + 1
        df['Item'] = range(1, len(df) + 1)
        # Aseguramos que 'Item' sea un tipo de dato entero
        df['Item'] = df['Item'].astype('Int64')
    return df

# ---------------------------------------------------------------------------
# 🟩 PESTAÑA 1: CARGA Y VALIDACIÓN DE DATOS
# ---------------------------------------------------------------------------
with tab1:
    st.header("⚡ Carga y Validación de Datos")
    st.markdown("Sube o edita tu archivo de consumo eléctrico antes de continuar con el análisis.")

    # ======== INFO GENERAL ========
    st.info(
        "💡 **Instrucciones:**\n"
        "1. Sube un archivo en formato **CSV** o **Excel (XLSX)** que contenga las columnas "
        "`Carga`, `Potencia (W)` y las horas `0` a `23`.\n"
        "2. Puedes editar directamente los valores en la tabla.\n"
        "3. Cuando los datos estén correctos, presiona **Validar Datos** para continuar."
    )

    # ======== VARIABLES GLOBALES ========
    columnas_horas = [f"{i}" for i in range(24)]
    columnas = ["Item", "Carga", "Potencia (W)"] + columnas_horas

    if "tabla_datos" not in st.session_state:
        # Usamos float por defecto para Potencia (W) para evitar problemas de tipo después de NaN
        st.session_state["tabla_datos"] = pd.DataFrame(columns=columnas).astype({"Item": 'Int64', "Potencia (W)": float})


    # ======== CARGA DE ARCHIVO ========
    archivo = st.file_uploader("📂 Cargar archivo CSV o Excel", type=["csv", "xlsx"], label_visibility="collapsed")

    if archivo is not None:
        try:
            if archivo.name.endswith(".csv"):
                df = pd.read_csv(archivo)
            else:
                df = pd.read_excel(archivo)

            # FORZAR CONVERSIÓN NUMÉRICA DESPUÉS DE LA CARGA
            if "Potencia (W)" in df.columns:
                # Convertir a numérico; errores se convierten a NaN
                df["Potencia (W)"] = pd.to_numeric(df["Potencia (W)"], errors='coerce')

            # Preparamos las columnas para la fusión
            for col in columnas:
                if col not in df.columns:
                    df[col] = 0
            
            # Eliminamos la columna 'Item' si existe en el archivo cargado para evitar conflictos
            if "Item" in df.columns:
                df = df.drop(columns=["Item"])
            
            # Garantizamos el orden de las columnas sin el Item temporalmente para el merge
            cols_sin_item = [col for col in columnas if col != "Item"]
            if not df.empty:
                df = df[cols_sin_item]
                
            # Fusionar con los datos existentes, eliminando duplicados basados en 'Carga'
            df_consolidado = pd.concat(
                [st.session_state["tabla_datos"].drop(columns=["Item"], errors='ignore'), df],
                ignore_index=True
            ).drop_duplicates(subset=["Carga"], keep="last")
            
            # APLICAMOS REINDEXACIÓN DE 'Item' Y REINICIAMOS EL ÍNDICE DE PANDAS
            df_consolidado = reindexar_items(df_consolidado)
            st.session_state["tabla_datos"] = df_consolidado.reset_index(drop=True)

            st.success("✅ Archivo cargado correctamente.")
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
    else:
        if st.session_state["tabla_datos"].empty:
            st.info("Puedes cargar un archivo o comenzar a ingresar datos manualmente.")

    # ======== INGRESO MANUAL ========
    st.subheader("✍️ Agregar carga manualmente")

    col1, col2 = st.columns([2, 1])
    with col1:
        carga = st.text_input("Nombre de la carga")
    with col2:
        # Aseguramos que el input de potencia siempre sea float
        potencia = st.number_input("Potencia (W)", min_value=0.0, step=10.0, format="%.2f")

    horas_activas = st.multiselect(
        "Selecciona las horas activas (1):",
        options=columnas_horas,
        default=[],
        help="Selecciona las horas del día en que esta carga está encendida."
    )

    if st.button("➕ Agregar carga"):
        if not carga:
            st.warning("Debes ingresar un nombre de carga.")
        elif potencia == 0:
            st.warning("Debes ingresar una potencia mayor que 0.")
        else:
            # Crear fila con horas activas = 1 y las demás = 0
            fila = {col: (1 if col in horas_activas else 0) for col in columnas_horas}
            fila.update({
                "Carga": carga, 
                "Potencia (W)": float(potencia) # Aseguramos que sea float
                })

            df_nuevo = pd.DataFrame([fila])
            
            # Consolidamos la tabla, eliminamos duplicados por Carga
            df_consolidado = pd.concat(
                [st.session_state["tabla_datos"].drop(columns=["Item"], errors='ignore'), df_nuevo],
                ignore_index=True
            )
            
            # ELIMINAR DUPLICADOS MANTENIENDO EL ÚLTIMO (EL MANUAL)
            df_consolidado = df_consolidado.drop_duplicates(subset=["Carga"], keep="last")
            
            # APLICAMOS REINDEXACIÓN DE 'Item' Y REINICIAMOS EL ÍNDICE DE PANDAS
            df_consolidado = reindexar_items(df_consolidado)
            st.session_state["tabla_datos"] = df_consolidado.reset_index(drop=True)
            
            st.success(f"✅ Carga '{carga}' agregada correctamente.")

    # ======== TABLA EDITABLE ========
    st.markdown("### 🧾 Vista previa de los datos cargados o ingresados")
    st.caption("Puedes editar directamente cualquier celda o eliminar filas según sea necesario.")

    # Almacenamos el DataFrame original para detectar eliminaciones/ediciones
    df_original = st.session_state["tabla_datos"].copy()

    edited_df = st.data_editor(
        df_original,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_order=columnas,
        key="editor_tabla",
    )
    
    # Lógica para detectar si se eliminaron filas o se modificó el DataFrame
    if not edited_df.equals(df_original):
        if not edited_df.empty:
            df_reindexed = reindexar_items(edited_df)
            # REINICIAMOS EL ÍNDICE DE PANDAS DESPUÉS DE LA EDICIÓN/ELIMINACIÓN
            st.session_state["tabla_datos"] = df_reindexed.reset_index(drop=True)
        else:
            # Caso de tabla vacía
            st.session_state["tabla_datos"] = edited_df.reset_index(drop=True)

    # ======== DESCARGA ========
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1]) 
    
    with col1:
        # Botón para descargar como CSV (EXISTENTE)
        st.download_button(
            "💾 Descargar como CSV",
            data=st.session_state["tabla_datos"].to_csv(index=False).encode("utf-8"),
            file_name="datos_cuadro_carga.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        # Botón para descargar como XLSX (NUEVO)
        # 1. Creamos un objeto BytesIO
        output = io.BytesIO()
        # 2. Guardamos el DataFrame en el buffer en formato Excel
        st.session_state["tabla_datos"].to_excel(output, index=False)
        # 3. Descargamos el contenido del buffer
        st.download_button(
            "💾 Descargar como Excel (XLSX)",
            data=output.getvalue(),
            file_name="datos_cuadro_carga.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# ======== VALIDACIÓN ========
    st.markdown("---")
    st.subheader("🔍 Validación de Datos")

    def validar_datos(df):
        errores = []

        # Columnas requeridas
        if not all(col in df.columns for col in columnas):
            errores.append("❌ Faltan columnas requeridas o el formato no es correcto.")
            return errores

        # Potencia debe ser numérica y no negativa
        # Comprobamos que el dtype sea numérico (incluyendo float para NaN)
        if not pd.api.types.is_numeric_dtype(df["Potencia (W)"]):
             errores.append("⚠️ 'Potencia (W)' debe ser un valor numérico.")
        
        # Comprobamos si hay valores NaN después de la conversión forzada (errores en el archivo)
        if df["Potencia (W)"].isnull().any():
             errores.append("⚠️ Hay valores no numéricos o faltantes en 'Potencia (W)'. Revise el archivo.")

        # Comprobamos si hay valores negativos entre los números válidos
        if (df["Potencia (W)"].dropna() < 0).any():
            errores.append("⚠️ Hay valores negativos en 'Potencia (W)'.")

        # Validar columnas H00–H23 (solo 0 o 1)
        for col in columnas_horas:
            if not df[col].fillna(0).astype(int).isin([0, 1]).all():
                errores.append(f"❌ La columna {col} contiene valores distintos de 0 o 1.")

        # Faltantes (ya cubiertos en Potencia, pero se revisa el resto)
        if df.isnull().drop(columns=["Potencia (W)"], errors='ignore').any().any():
            errores.append("⚠️ Hay valores faltantes en la tabla (excepto Potencia (W) donde ya se chequeó).")

        # Duplicados
        if df["Carga"].duplicated().any():
            errores.append("⚠️ Existen cargas duplicadas.")

        return errores

    col_1, col_2 = st.columns([1, 1])
    with col_1:

        if st.button("✅ Validar y Guardar Datos", use_container_width=True):
            df = st.session_state["tabla_datos"]
            if df.empty:
                st.error("No hay datos para validar.")
            else:
                errores = validar_datos(df)
                if errores:
                    st.error("Se encontraron los siguientes problemas:")
                    for e in errores:
                        st.write(e)
                else:
                    st.success("✅ Datos validados correctamente. El formato es correcto.")
                    st.session_state["datos_validos"] = df
                    st.balloons()

    ####
                # Redirigir automáticamente a la segunda pestaña
            components.html(
                """
                <script>
                const tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
                if (tabs && tabs.length > 1) { tabs[1].click(); }  // 0 = pestaña 1, 1 = pestaña 2
                </script>
                """,
                height=0, width=0
            )


# ---------------------------------------------------------------------------
# 🟦 PESTAÑA 2: PROCESAMIENTO
# ---------------------------------------------------------------------------
with tab2:
    st.header("⚙️ Análisis y Consumo de Carga")

    if "datos_validos" not in st.session_state or st.session_state["datos_validos"].empty:
        st.warning("⚠️ Primero, carga y valida los datos en la Pestaña 1 para comenzar el análisis.")
    else:
        
        df_base = st.session_state["datos_validos"].copy()
        st.success("✅ Datos listos para el análisis.")
    
        # --- SECCIÓN DE CONFIGURACIÓN DE SEGMENTACIÓN ---
        st.subheader("🛠️ Configuración de Segmentación Diurna/Nocturna")

        # Creamos dos columnas para los sliders
        col_diurno_start, col_diurno_end = st.columns(2)

        with col_diurno_start:
            # Horario de inicio diurno
            st.session_state["hora_diurna_inicio"] = st.slider(
                "Hora de Inicio del Período Diurno",
                min_value=0, 
                max_value=23, 
                value=6, # Valor por defecto a las 6:00 AM
                step=1, 
                format="%02d:00 h",
                key="diurno_inicio"
            )
    
        with col_diurno_end:
            # Horario de fin diurno
            st.session_state["hora_diurna_fin"] = st.slider(
                "Hora de Fin del Período Diurno",
                min_value=0, 
                max_value=23, 
                value=18, # Valor por defecto a las 18:00 PM
                step=1, 
                format="%02d:00 h",
                key="diurno_fin"
            )
    
        # Obtener las configuraciones
        diurno_inicio = st.session_state.get("hora_diurna_inicio", 6)
        diurno_fin = st.session_state.get("hora_diurna_fin", 18)
        columnas_horas = [f"{i}" for i in range(24)]

        st.markdown(
            f"El **Período Diurno**☀️ se considerará desde las **{diurno_inicio:02d}:00** "
            f"hasta las **{diurno_fin:02d}:00**."
        )

        # Cálculo del período nocturno complementario
        if diurno_inicio < diurno_fin:
            # Caso normal: el día no cruza medianoche
            st.markdown(
                f"El **Período Nocturno**🌙 se considerará desde las **{diurno_fin:02d}:00** "
                f"hasta las **{diurno_inicio:02d}:00** del día siguiente."
            )   
        else:
            # Caso en que el día cruza medianoche
            st.markdown(
                f"El **Período Nocturno**🌙 se considerará desde las **{diurno_fin:02d}:00** "
                f"hasta las **{diurno_inicio:02d}:00** del mismo día."
            )
        
        # --- CÁLCULO ROBUSTO DE HORAS DIURNAS/NOCTURNAS (SOLUCIÓN AL ERROR 1) ---
        
        def get_horas_segmento(inicio, fin):
            """Calcula las columnas de horas para el segmento (incluso si cruza la medianoche)."""
            horas = []
            if inicio < fin:
                # Caso normal: 07:00 a 19:00
                for h in range(inicio, fin):
                    horas.append(f"{h}")
            else:
                # Caso cruce de medianoche: 22:00 a 06:00 (ejemplo 22, 23, 0, 1, 2, 3, 4, 5)
                # Desde inicio hasta 23
                for h in range(inicio, 24):
                    horas.append(f"{h}")
                # Desde 0 hasta fin
                for h in range(0, fin):
                    horas.append(f"{h}")
            return horas

        horas_diurnas_cols = get_horas_segmento(diurno_inicio, diurno_fin)
        horas_nocturnas_cols = [col for col in columnas_horas if col not in horas_diurnas_cols]

        st.markdown("---")

        # =========================================================================
        #    FILTRO ESTACIONAL (MES Y DÍA)
        # =========================================================================

        st.subheader("📆 Filtro por Período de Análisis (Ajuste Estacional)")
        st.markdown("Selecciona el mes de referencia y el número de días exactos a considerar para la proyección de energía. El número máximo de días se ajusta al mes seleccionado.")

        col_mes, col_dias = st.columns(2)

        # Diccionario auxiliar para días por mes (asumiendo año no bisiesto por simplicidad)
        dias_por_mes = {
            "Enero": 31, "Febrero": 28, "Marzo": 31, "Abril": 30, "Mayo": 31, "Junio": 30,
            "Julio": 31, "Agosto": 31, "Septiembre": 30, "Octubre": 31, "Noviembre": 30, "Diciembre": 31
        }
        
        # Definimos el orden de los meses para usarlo en los gráficos
        orden_meses = list(dias_por_mes.keys())

        with col_mes:
            # Selector de Mes de Referencia
            mes_seleccionado = st.selectbox(
                "Mes de Referencia:",
                options=orden_meses,
                index=0, 
                key="filtro_mes_ref"
            )
            # Días totales del mes de referencia (usado para establecer el límite y el valor por defecto)
            max_dias = dias_por_mes[mes_seleccionado]

        with col_dias:
            # Entrada numérica para el número de días
            # Usamos una clave condicional para que el valor por defecto se resetee al cambiar el mes
            dias_a_considerar = st.number_input(
                f"Días a considerar del período ({mes_seleccionado}):",
                min_value=1,
                max_value=max_dias, # El rango máximo cambia aquí
                value=max_dias,     # El valor por defecto cambia aquí
                step=1,
                help=f"Ingresa el número exacto de días (máximo {max_dias}).",
                key=f"dias_analisis_simple_{mes_seleccionado}" # Clave dinámica para resetear valor
            )

        st.info(f"Proyección de Energía para **{mes_seleccionado}** se realizará sobre **{dias_a_considerar} días**.")
            
        st.markdown("---")

        # =========================================================================
        #    NUEVA SECCIÓN: AJUSTES ESTACIONALES
        # =========================================================================
        st.subheader("🍃 Aplicar Ajustes Estacionales")
        st.markdown("Ajusta el consumo proyectado para cada mes (p.ej., por estacionalidad). **1.0x (100%)** es el valor base sin cambios.")

        # Inicializar los multiplicadores en session_state si no existen
        if "ajustes_mensuales" not in st.session_state:
            st.session_state.ajustes_mensuales = {mes: 1.0 for mes in orden_meses}
        
        if "ajuste_general" not in st.session_state:
            st.session_state.ajuste_general = 1.0

        modo_ajuste = st.radio(
            "Modo de Ajuste", 
            ["Mensual", "General"], 
            key="modo_ajuste_estacional",
            horizontal=True,
            help="**Mensual**: Ajuste individual por mes. **General**: Un solo ajuste para todos los meses."
        )

        multiplicadores_mes = {}

        if modo_ajuste == "General":
            ajuste_general = st.slider(
                "Ajustar multiplicador (%) General (50% a 150%)", 
                min_value=0.5, 
                max_value=1.5, 
                # Usamos el valor guardado en session_state
                value=st.session_state.ajuste_general, 
                step=0.01, 
                format="x%.2f",
                key="slider_general"
            )
            # Actualizar el valor general en session_state para que persista
            st.session_state.ajuste_general = ajuste_general
            
            # Crear el diccionario de multiplicadores (todos iguales)
            multiplicadores_mes = {mes: ajuste_general for mes in orden_meses}
        
        else: # modo_ajuste == "Mensual"
            st.markdown("Ajustar multiplicador (%) para cada mes (50% a 150%)")
            
            # Crear 3 columnas para los 12 meses (4 meses por columna)
            col1, col2, col3 = st.columns(3)
            cols = [col1, col2, col3]
            
            mes_index = 0
            for mes in orden_meses:
                # Asigna 4 meses a cada columna
                col_actual = cols[mes_index // 4] 
                
                with col_actual:
                    # Usamos st.session_state para almacenar el valor de CADA slider
                    clave_slider_mes = f"ajuste_{mes}"
                    
                    # Si la clave no existe, la inicializa con el valor guardado
                    if clave_slider_mes not in st.session_state:
                        st.session_state[clave_slider_mes] = st.session_state.ajustes_mensuales.get(mes, 1.0)
                    
                    valor_ajuste = st.slider(
                        f"{mes} (%)",
                        min_value=0.5,
                        max_value=1.5,
                        value=st.session_state[clave_slider_mes], # Lee el valor guardado
                        step=0.01,
                        format="x%.2f",
                        key=f"slider_{mes}" # Clave única para el widget
                    )
                    
                    # Actualizar el valor en session_state Y en el diccionario
                    st.session_state[clave_slider_mes] = valor_ajuste
                    st.session_state.ajustes_mensuales[mes] = valor_ajuste
                    multiplicadores_mes[mes] = valor_ajuste
                
                mes_index += 1
            
            # Asegurarse de que el diccionario esté completo
            for mes in orden_meses:
                if mes not in multiplicadores_mes:
                    multiplicadores_mes[mes] = st.session_state.ajustes_mensuales.get(mes, 1.0)

        # Guardamos el diccionario resultante en session_state para usarlo en los cálculos
        st.session_state.multiplicadores_finales = multiplicadores_mes
        
        st.markdown("---")
        # =========================================================================

        # =========================================================================
        # 0. CÁLCULOS PRINCIPALES (BASE Y AJUSTADOS)
        # =========================================================================

        # Recuperar los multiplicadores estacionales (NO MODIFICAR)
        multiplicadores_mes = st.session_state.get(
            "multiplicadores_finales", 
            {mes: 1.0 for mes in orden_meses} # Default por si acaso
        )
        
        # 🟢 NUEVO: Obtener el multiplicador actual para el mes de referencia
        multiplicador_actual = multiplicadores_mes.get(mes_seleccionado, 1.0)


        df_calculo = df_base[["Potencia (W)"] + columnas_horas].copy()
        
        # Cálculo de Potencia Total por Hora (en W) - BASE SIN AJUSTE
        potencia_horaria = df_calculo[columnas_horas].mul(df_calculo["Potencia (W)"], axis=0).sum(axis=0)
        potencia_horaria.name = "Potencia Total (W)"
        
        # df_potencia_total contiene la potencia horaria BASE
        df_potencia_total = pd.DataFrame(potencia_horaria).T

        # Energía Diaria (en kWh/día) - BASE SIN AJUSTE
        energia_diurna_dia = (df_potencia_total[horas_diurnas_cols].sum(axis=1).iloc[0])/1000.0 if horas_diurnas_cols else 0.0 # kWh/día
        energia_nocturna_dia = (df_potencia_total[horas_nocturnas_cols].sum(axis=1).iloc[0])/1000.0 if horas_nocturnas_cols else 0.0 # kWh/día
        energia_total_dia = energia_diurna_dia + energia_nocturna_dia # kWh/día

        # Potencia Máxima/Mínima/Media (BASE SIN AJUSTE)
        potencia_max_w = df_potencia_total.iloc[0].max()
        hora_max = df_potencia_total.iloc[0].idxmax()
        potencia_min_w = df_potencia_total.iloc[0].min()
        hora_min = df_potencia_total.iloc[0].idxmin()

        num_horas_diurnas = len(horas_diurnas_cols)
        num_horas_nocturnas = len(horas_nocturnas_cols)
        
        potencia_media_total_w = (energia_total_dia * 1000) / 24 
        
        if num_horas_diurnas > 0:
            potencia_media_diurna_w = (energia_diurna_dia * 1000) / num_horas_diurnas
            potencia_max_diurna_w = df_potencia_total[horas_diurnas_cols].iloc[0].max()
            hora_max_diurna = df_potencia_total[horas_diurnas_cols].iloc[0].idxmax()
        else:
            potencia_media_diurna_w = 0
            potencia_max_diurna_w = 0
            hora_max_diurna = 'N/A'

        if num_horas_nocturnas > 0:
            potencia_media_nocturna_w = (energia_nocturna_dia * 1000) / num_horas_nocturnas
            potencia_max_nocturna_w = df_potencia_total[horas_nocturnas_cols].iloc[0].max()
            hora_max_nocturna = df_potencia_total[horas_nocturnas_cols].iloc[0].idxmin()
        else:
            potencia_media_nocturna_w = 0
            potencia_max_nocturna_w = 0
            hora_max_nocturna = 'N/A'
            
        factor_carga_general = (potencia_media_total_w / potencia_max_w) * 100 if potencia_max_w > 0 else 0
        factor_carga_diurno = (potencia_media_diurna_w / potencia_max_diurna_w) * 100 if potencia_max_diurna_w > 0 else 0
        factor_carga_nocturno = (potencia_media_nocturna_w / potencia_max_nocturna_w) * 100 if potencia_max_nocturna_w > 0 else 0


        # ---------------------------------------------------------------------------------
        # 🟢 CÁLCULOS AJUSTADOS (PARA EL MES SELECCIONADO)
        # ---------------------------------------------------------------------------------

        # 1. Potencia Horaria Ajustada
        potencia_horaria_ajustada = potencia_horaria * multiplicador_actual
        df_potencia_total_ajustada = pd.DataFrame(potencia_horaria_ajustada).T

        # 2. Energía Diaria Ajustada
        energia_total_dia_ajustada = energia_total_dia * multiplicador_actual
        energia_diurna_dia_ajustada = energia_diurna_dia * multiplicador_actual
        energia_nocturna_dia_ajustada = energia_nocturna_dia * multiplicador_actual
        
        # 3. Métricas de Potencia (Ajustadas)
        potencia_max_w_ajustada = df_potencia_total_ajustada.iloc[0].max()
        hora_max_ajustada = df_potencia_total_ajustada.iloc[0].idxmax()
        potencia_min_w_ajustada = df_potencia_total_ajustada.iloc[0].min()
        hora_min_ajustada = df_potencia_total_ajustada.iloc[0].idxmin()
        
        # Potencia Media Ajustada
        potencia_media_total_w_ajustada = (energia_total_dia_ajustada * 1000) / 24 
        
        if num_horas_diurnas > 0:
            potencia_media_diurna_w_ajustada = (energia_diurna_dia_ajustada * 1000) / num_horas_diurnas
            potencia_max_diurna_w_ajustada = df_potencia_total_ajustada[horas_diurnas_cols].iloc[0].max()
            hora_max_diurna_ajustada = df_potencia_total_ajustada[horas_diurnas_cols].iloc[0].idxmax()
        else:
            potencia_media_diurna_w_ajustada = 0
            potencia_max_diurna_w_ajustada = 0
            hora_max_diurna_ajustada = 'N/A'

        if num_horas_nocturnas > 0:
            potencia_media_nocturna_w_ajustada = (energia_nocturna_dia_ajustada * 1000) / num_horas_nocturnas
            potencia_max_nocturna_w_ajustada = df_potencia_total_ajustada[horas_nocturnas_cols].iloc[0].max()
            hora_max_nocturna_ajustada = df_potencia_total_ajustada[horas_nocturnas_cols].iloc[0].idxmin()
        else:
            potencia_media_nocturna_w_ajustada = 0
            potencia_max_nocturna_w_ajustada = 0
            hora_max_nocturna_ajustada = 'N/A'
            
        # Factores de Carga Ajustados (El factor de carga no cambia con el ajuste si es uniforme,
        # pero se recalculan para usar los valores de Pico Ajustado vs. Media Ajustada, manteniendo la consistencia)
        factor_carga_general_ajustado = (potencia_media_total_w_ajustada / potencia_max_w_ajustada) * 100 if potencia_max_w_ajustada > 0 else 0
        factor_carga_diurno_ajustado = (potencia_media_diurna_w_ajustada / potencia_max_diurna_w_ajustada) * 100 if potencia_max_diurna_w_ajustada > 0 else 0
        factor_carga_nocturno_ajustado = (potencia_media_nocturna_w_ajustada / potencia_max_nocturna_w_ajustada) * 100 if potencia_max_nocturna_w_ajustada > 0 else 0
        
        # ---------------------------------------------------------------------------------
        # 🟢 FIN CÁLCULOS AJUSTADOS
        # ---------------------------------------------------------------------------------


        # =========================================================================
        # 1. MÉTRICAS CLAVE (DISPLAY)
        # =========================================================================
        
        st.subheader("1. Métricas Clave 🔢 (Ajustadas)")

        # Notificación del ajuste
        st.caption(f"💡 Las métricas mostradas reflejan el perfil de potencia ajustado por el multiplicador de **{mes_seleccionado} (x{multiplicador_actual:.2f})**.")
        
        # POTENCIA MÁXIMA Y MÍNIMA
        st.markdown("#### 1.1. Potencia Pico y Base (W) y Ocurrencia")

        col_max, col_min, col_pico_diurno, col_pico_nocturno = st.columns(4)
        
        with col_max:
            # USAR AJUSTADO: potencia_max_w_ajustada
            st.metric(
                "📈 Potencia Máxima (Pico) Total", 
                f"{potencia_max_w_ajustada:,.0f} W",
                f"Ocurre a las {int(hora_max_ajustada):02d}:00 h"
            )
        
        with col_min:
            # USAR AJUSTADO: potencia_min_w_ajustada
            st.metric(
                "📉 Potencia Mínima (Base) Total", 
                f"{potencia_min_w_ajustada:,.0f} W",
                f"Ocurre a las {int(hora_min_ajustada):02d}:00 h"
            )

        with col_pico_diurno:
            # USAR AJUSTADO: potencia_max_diurna_w_ajustada
            st.metric(
                "Pico Diurno (W)", 
                f"{potencia_max_diurna_w_ajustada:,.0f} W",
                f"Ocurre a las {int(hora_max_diurna_ajustada):02d}:00 h" if hora_max_diurna_ajustada != 'N/A' else 'N/A'
            )

        with col_pico_nocturno:
            # USAR AJUSTADO: potencia_max_nocturna_w_ajustada
            st.metric(
                "Pico Nocturno (W)", 
                f"{potencia_max_nocturna_w_ajustada:,.0f} W",
                f"Ocurre a las {int(hora_max_nocturna_ajustada):02d}:00 h" if hora_max_nocturna_ajustada != 'N/A' else 'N/A'
            )
        
        st.markdown("---")

        # POTENCIA MEDIA
        st.markdown("#### 1.2. Potencia Media Diaria (W) 📊")

        col_pm_gen, col_pm_diu, col_pm_noc = st.columns(3)

        with col_pm_gen:
            # USAR AJUSTADO: potencia_media_total_w_ajustada
            st.metric(
                "Potencia Media General",
                f"{potencia_media_total_w_ajustada:,.0f} W",
                "Promedio de 24 horas"
            )
        with col_pm_diu:
            # USAR AJUSTADO: potencia_media_diurna_w_ajustada
            st.metric(
                "☀️ Potencia Media Diurna",
                f"{potencia_media_diurna_w_ajustada:,.0f} W",
                f"Promedio de {num_horas_diurnas} horas"
            )
        with col_pm_noc:
            # USAR AJUSTADO: potencia_media_nocturna_w_ajustada
            st.metric(
                "🌙 Potencia Media Nocturna",
                f"{potencia_media_nocturna_w_ajustada:,.0f} W",
                f"Promedio de {num_horas_nocturnas} horas"
            )

        st.markdown("---")
        
        # FACTOR DE CARGA
        st.markdown("#### 1.3. Factor de Carga (%)")

        col_fc_gen, col_fc_diu, col_fc_noc = st.columns(3)

        with col_fc_gen:
            # USAR AJUSTADO: factor_carga_general_ajustado
            st.metric(
                "Factor de Carga General", 
                f"{factor_carga_general_ajustado:,.2f} %",
                "Promedio vs. Pico Total"
            )
        with col_fc_diu:
            # USAR AJUSTADO: factor_carga_diurno_ajustado
            st.metric(
                "Factor de Carga Diurno", 
                f"{factor_carga_diurno_ajustado:,.2f} %",
                "Promedio Diurno vs. Pico Diurno"
            )
        with col_fc_noc:
            # USAR AJUSTADO: factor_carga_nocturno_ajustado
            st.metric(
                "Factor de Carga Nocturno", 
                f"{factor_carga_nocturno_ajustado:,.2f} %",
                "Promedio Nocturno vs. Pico Nocturno"
            )

        st.markdown("---")
        
        # =========================================================================
        # 2. PROYECCIONES DE ENERGÍA (kWh)
        # =========================================================================

        st.subheader("2. Proyecciones de Energía (kWh) 🔋")

        # ENERGÍA DIARIA
        st.markdown("#### 2.1. Perfil de Energía Diaria")
        
        # Aquí la energía total diaria sigue siendo la BASE (sin ajuste)
        col_tot_dia, col_diurno_dia, col_nocturno_dia = st.columns(3)

        with col_tot_dia:
            st.metric("Energía Total Diaria (Base)", f"{energia_total_dia:,.2f} kWh")
        with col_diurno_dia:
            st.metric("☀️ Energía Total Diurna (Base)", f"{energia_diurna_dia:,.2f} kWh")
        with col_nocturno_dia:
            st.metric("🌙 Energía Total Nocturna (Base)", f"{energia_nocturna_dia:,.2f} kWh")
        
        st.markdown("---")

        # ENERGÍA DEL PERÍODO
        st.markdown("#### 2.2. Perfil de Energía del Periodo")
        
        # NOTA: En este punto, ya tenemos energia_total_dia_ajustada, etc. del paso 0.
        # Por lo tanto, el cálculo se simplifica, ya que solo necesitamos multiplicar por los días.
        
        # Calcular la energía del período usando los valores ajustados
        energia_periodo_kwh = energia_total_dia_ajustada * dias_a_considerar
        energia_perido_diurna = energia_diurna_dia_ajustada * dias_a_considerar
        energia_periodo_nocturna = energia_nocturna_dia_ajustada * dias_a_considerar     

        col_tot_mes, col_diurno_mes, col_nocturno_mes = st.columns(3)

        with col_tot_mes:
            st.metric(f"Energía Total Calculada ({dias_a_considerar} días)", f"{energia_periodo_kwh:,.2f} kWh")
            if multiplicador_actual != 1.0:
                 st.caption(f"Aplicando ajuste de **{multiplicador_actual:.2f}x** por mes.")
        with col_diurno_mes:
            st.metric(f"☀️ Energía Total Diurna", f"{energia_perido_diurna:,.2f} kWh")
        with col_nocturno_mes:
            st.metric(f"🌙 Energía Total Nocturna", f"{energia_periodo_nocturna:,.2f} kWh")
        
        st.markdown("---")

        # ENERGÍA ANUAL
        st.markdown("#### 2.3. Proyección de Energía Anual")

        # ¡MODIFICADO! Calcular la suma anual basada en los multiplicadores
        energia_anual_kwh = 0
        energia_anual_diurna = 0
        energia_anual_nocturna = 0

        # Iterar por cada mes, aplicar su multiplicador y días, y sumar
        for mes, dias in dias_por_mes.items():
            multiplicador = multiplicadores_mes.get(mes, 1.0)
            # USAR VALORES BASE (SIN AJUSTAR) para evitar doble conteo
            energia_anual_kwh += (energia_total_dia * multiplicador) * dias
            energia_anual_diurna += (energia_diurna_dia * multiplicador) * dias
            energia_anual_nocturna += (energia_nocturna_dia * multiplicador) * dias
        
        total_dias_anual = sum(dias_por_mes.values())

        col_tot_anual, col_diurno_anual, col_nocturno_anual = st.columns(3)

        with col_tot_anual:
            st.metric(f"Energía Total Anual ({total_dias_anual} días)", f"{energia_anual_kwh:,.2f} kWh")
            st.caption("Ajuste mensual aplicado a la proyección anual.")
        with col_diurno_anual:
            st.metric(f"☀️ Energía Total Diurna", f"{energia_anual_diurna:,.2f} kWh")
        with col_nocturno_anual:
            st.metric(f"🌙 Energía Total Nocturna", f"{energia_anual_nocturna:,.2f} kWh")
        
        st.markdown("---")

        # =========================================================================
        # 3. VISUALIZACIÓN DE PERFILES (GRÁFICOS) 📈
        # =========================================================================

        st.subheader("3. Visualización de Perfiles")

        # --- GRÁFICO 3.1: CUADRO DE CARGA (LDC) ---
        st.markdown("#### 3.1. Cuadro de Carga (Load Duration Curve - LDC) de 24 Horas")

        # 1. Preparar datos para LDC
        # Se usa df_potencia_total_ajustada (calculado en el paso 0)
        df_ldc = df_potencia_total_ajustada.T.reset_index(drop=True).rename(columns={0: 'Potencia Total (W)'})
        
        # 🟢 MODIFICACIÓN 3: Notificar el ajuste
        st.info(f"El Cuadro de Carga (LDC) está ajustado por el multiplicador de **{mes_seleccionado} (x{multiplicador_actual:.2f})**.")

        # Ordenar los valores (ahora ajustados)
        df_ldc = df_ldc.sort_values(by='Potencia Total (W)', ascending=False).reset_index(drop=True)

        # La duración es la posición en el índice (0 a 23), +1 para que sea 1 a 24
        df_ldc['Duración (horas)'] = df_ldc.index + 1
        
        # 🟢 MODIFICACIÓN 4: Recalcular Pico y Media AJUSTADOS para el gráfico LDC
        # Se usan los valores ajustados ya calculados en la Sección 0.
        #potencia_max_w_ajustada = df_ldc['Potencia Total (W)'].max()
        #potencia_media_total_w_ajustada = df_ldc['Potencia Total (W)'].mean()
        
        # 2. Crear la Curva LDC (Línea)
        ldc_curve = alt.Chart(df_ldc).mark_line(point=True, color='#007F5F').encode(
            x=alt.X('Duración (horas):Q', title='Duración (horas/día)', scale=alt.Scale(domain=[1, 24])),
            y=alt.Y('Potencia Total (W):Q', title='Potencia Total (W)'),
            tooltip=['Duración (horas)', alt.Tooltip('Potencia Total (W)', format=',.0f')]
        ).properties(
            height=500,
            title='Curva de Duración de Carga (LDC) de 24 Horas (Ajustada)'
        )
        
        # 3. Línea de Potencia Máxima (Pico) - Usa el valor ajustado
        if potencia_max_w_ajustada > 0:
            df_pico = pd.DataFrame({'Potencia Total (W)': [potencia_max_w_ajustada], 'Etiqueta': [f"Pico Ajustado: {potencia_max_w_ajustada:,.1f} W"]})
            line_pico = alt.Chart(df_pico).mark_rule(color='blue', strokeDash=[2, 2]).encode(
                y='Potencia Total (W)',
                size=alt.value(2),
            )
            
            text_pico = line_pico.mark_text(
                align='right',
                dx=5,
                dy=-5,
                color='blue'
            ).encode(
                text='Etiqueta:N',
                x=alt.value(800)
            )
        else:
            line_pico = alt.Chart(pd.DataFrame({'Potencia Total (W)': []})).mark_rule()
            text_pico = alt.Chart(pd.DataFrame({'Potencia Total (W)': []})).mark_text()

        # 4. Línea de Potencia Media - Usa el valor ajustado
        if potencia_media_total_w_ajustada > 0:
            df_media = pd.DataFrame({'Potencia Total (W)': [potencia_media_total_w_ajustada], 'Etiqueta': [f"Media Ajustada: {potencia_media_total_w_ajustada:,.1f} W"]})
            line_media = alt.Chart(df_media).mark_rule(color='red', strokeDash=[5, 5]).encode(
                y='Potencia Total (W)',
                size=alt.value(2),
            )

            text_media = line_media.mark_text(
                align='right',
                dx=5,
                dy=8,
                color='red'
            ).encode(
                text='Etiqueta:N',
                x=alt.value(800)
            )
        else:
            line_media = alt.Chart(pd.DataFrame({'Potencia Total (W)': []})).mark_rule()
            text_media = alt.Chart(pd.DataFrame({'Potencia Total (W)': []})).mark_text()

        # Combinar las capas
        chart_ldc = alt.layer(ldc_curve, line_pico, text_pico, line_media, text_media)

        st.altair_chart(chart_ldc, use_container_width=True)
        
        # Interpretación
        st.markdown("""
        **Interpretación:** El **Cuadro de Carga (LDC)** muestra la potencia demandada (eje Y) para cada hora del día, ordenada de mayor a menor, frente al número de horas (eje X) durante las cuales esa potencia o una superior es requerida. La curva y las líneas **azul punteada (Pico)** y **roja punteada (Media)** han sido ajustadas por el factor estacional del mes de referencia.
        """)

        # Botones de descarga para el gráfico LDC
        col_descarga_ldc_csv, col_descarga_ldc_excel = st.columns(2)
        with col_descarga_ldc_csv:
            # Los datos descargados (df_ldc) ya están ajustados
            st.download_button(
                "💾 Descargar datos LDC (CSV)",
                data=df_ldc.to_csv(index=False).encode("utf-8"),
                file_name="datos_ldc_ajustado.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_descarga_ldc_excel:
            # Los datos descargados (df_ldc) ya están ajustados
            output_ldc = io.BytesIO()
            df_ldc.to_excel(output_ldc, index=False)
            st.download_button(
                "💾 Descargar datos LDC (Excel)",
                data=output_ldc.getvalue(),
                file_name="datos_ldc_ajustado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        st.markdown("---")

        # --- GRÁFICO 3.2: CONSUMO HORARIO SEGMENTADO ---
        st.markdown("#### 3.2. Potencia Horaria Diurna vs. Nocturna (W)")

        # 1. Preparar los datos para el gráfico
        # Se usa df_potencia_total_ajustada (calculado en el paso 0)
        df_plot_horario = df_potencia_total_ajustada.T.reset_index()
        df_plot_horario.columns = ['Hora', 'Potencia (W)']
        df_plot_horario['Hora'] = df_plot_horario['Hora'].astype(int)

        st.info(f"El perfil mostrado está ajustado por el multiplicador de **{mes_seleccionado} (x{multiplicador_actual:.2f})**.")
        
        def get_segmento(hora):
            return 'Diurno ☀️' if f"{hora}" in horas_diurnas_cols else 'Nocturno 🌙'

        df_plot_horario['Segmento'] = df_plot_horario['Hora'].apply(get_segmento)

        # Crear el gráfico de barras con Altair
        chart_horario = alt.Chart(df_plot_horario).mark_bar().encode(
            x=alt.X('Hora:O', title='Hora del Día', axis=alt.Axis(labelAngle=0)),
            y=alt.Y('Potencia (W):Q', title='Potencia (W)'),
            color=alt.Color('Segmento:N', 
                            legend=alt.Legend(title="Período"),
                            scale=alt.Scale(domain=['Diurno ☀️', 'Nocturno 🌙'], 
                                            range=['#ffcc66', '#4c78a8'])),
            tooltip=['Hora', 'Potencia (W)', 'Segmento']
        ).properties(
            title='Perfil de Consumo Horario Segmentado'
        ).properties(height=400)

        st.altair_chart(chart_horario, use_container_width=True)
        st.markdown("""
        **Interpretación:** Este gráfico de barras detalla la potencia total demandada por el sistema en cada una de las 24 horas del día. La segmentación de colores **Diurno/Nocturno** permite identificar visualmente los períodos de mayor y menor actividad de carga. Es crucial para verificar la concordancia entre los horarios configurados y los picos de consumo.
        """)

        # Botones de descarga para el gráfico horario
        col_descarga_horario_csv, col_descarga_horario_excel = st.columns(2)
        with col_descarga_horario_csv:
            st.download_button(
                "💾 Descargar datos horario (CSV)",
                data=df_plot_horario.to_csv(index=False).encode("utf-8"),
                file_name="datos_potencia_horaria_ajustada.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_descarga_horario_excel:
            output_horario = io.BytesIO()
            df_plot_horario.to_excel(output_horario, index=False)
            st.download_button(
                "💾 Descargar datos horario (Excel)",
                data=output_horario.getvalue(),
                file_name="datos_potencia_horaria_ajustada.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.markdown("---")

        # --- GRÁFICO 3.3: ENERGÍA TOTAL POR MES ---
        st.markdown("#### 3.3. Proyección de Energía Total por Mes (kWh)")

        df_mensual = pd.DataFrame(list(dias_por_mes.items()), columns=['Mes', 'Días'])
        
        # Aplicar los multiplicadores al DataFrame del gráfico
        df_mensual['Multiplicador'] = df_mensual['Mes'].map(multiplicadores_mes)
        # USAR VALOR BASE (energia_total_dia) para que el ajuste sea solo por el multiplicador
        df_mensual['Energía (kWh)'] = df_mensual['Días'] * energia_total_dia * df_mensual['Multiplicador']
        
        # orden_meses ya está definido arriba
        df_mensual['Mes'] = pd.Categorical(df_mensual['Mes'], categories=orden_meses, ordered=True)
        df_mensual = df_mensual.sort_values('Mes')

        # Calcular la energía mensual promedio para la línea horizontal
        energia_mensual_promedio = df_mensual['Energía (kWh)'].mean()

        # Capas para el gráfico
        bars = alt.Chart(df_mensual).mark_bar(color="#07A57E").encode(
            x=alt.X('Mes:O', sort=orden_meses, title='Mes del Año'), # Asegurar orden
            y=alt.Y('Energía (kWh):Q', title='Energía Proyectada (kWh)'),
            tooltip=['Mes', alt.Tooltip('Energía (kWh)', format=',.2f')]
        )

        # Capa para las etiquetas de texto sobre las barras
        text = bars.mark_text(
            align='center',
            baseline='bottom',
            dy=-5 # Desplazar el texto un poco hacia arriba de la barra
        ).encode(
            text=alt.Text('Energía (kWh)', format=',.0f'), # Formato sin decimales para el texto
            color=alt.value('black') # Color del texto
        )

        # Capa para la línea de energía promedio
        line_promedio = alt.Chart(pd.DataFrame({'Energía (kWh)': [energia_mensual_promedio]})).mark_rule(color='red', strokeDash=[5,5]).encode(
            y='Energía (kWh)',
            size=alt.value(2),
            tooltip=[alt.Tooltip('Energía (kWh)', title='Energía Promedio Mensual', format=',.2f')]
        )
        
        # Texto para la línea de energía promedio
        text_promedio = line_promedio.mark_text(
            align='left',
            dx=5, # Desplazar el texto un poco a la derecha de la línea
            dy=-5, # Desplazar el texto un poco hacia arriba de la línea
            color='red'
        ).encode(
            text=alt.Text('Energía (kWh)', title='Energía Promedio Mensual', format=',.2f'),
        )


        # Combinar las capas
        chart_mensual = alt.layer(bars, text, line_promedio, text_promedio).properties(
            title='Proyección de Consumo Energético Mensual (Ajustado por Multiplicadores Estacionales)',
            height=450
        )

        st.altair_chart(chart_mensual, use_container_width=True)
        st.markdown("""
        **Interpretación:** Este gráfico de barras proyecta el consumo total de energía (kWh) para cada mes del año, basándose en la energía diaria (kWh/día) del perfil de carga actual y aplicando el **Ajuste Estacional** seleccionado. La línea **roja punteada** representa la **Energía Mensual Promedio**, lo que permite identificar rápidamente los meses de consumo superior e inferior al promedio anual.
        """)

        # Botones de descarga para el gráfico mensual
        col_descarga_mensual_csv, col_descarga_mensual_excel = st.columns(2)
        with col_descarga_mensual_csv:
            st.download_button(
                "💾 Descargar datos mensual (CSV)",
                data=df_mensual.to_csv(index=False).encode("utf-8"),
                file_name="datos_energia_mensual_ajustada.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_descarga_mensual_excel:
            output_mensual = io.BytesIO()
            df_mensual.to_excel(output_mensual, index=False)
            st.download_button(
                "💾 Descargar datos mensual (Excel)",
                data=output_mensual.getvalue(),
                file_name="datos_energia_mensual_ajustada.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.markdown("---")

        # =========================================================================
        # 4. MAPA DE CALOR DE CONSUMO HORARIO Y MENSUAL
        # =========================================================================

        # ¡MODIFICADO! Se agrega el diccionario de multiplicadores para que el mapa de calor mensual los use
        render_mapa_calor_accesible(
            df_base=df_base,                   # tu dataframe base de cargas
            potencia_horaria=potencia_horaria, # serie 0..23 ya calculada (BASE)
            default_view="Horario diario (0-23)",   # o "Horario mensual (12 meses)"
            default_scheme="blues",
            height=420,
            multiplicadores_estacionales=multiplicadores_mes # <-- NUEVO ARGUMENTO
        )

        st.markdown("---")