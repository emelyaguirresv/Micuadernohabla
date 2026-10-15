import streamlit as st

from cerebro import ImagenIlegible, analizar_pagina, calificar, crear_cliente
from voz import decir


st.set_page_config(
    page_title="Mi cuaderno habla",
    page_icon="📓",
    layout="centered",
)

try:
    llave_api = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error(
        "No se encontró GEMINI_API_KEY. Agregala en "
        "`.streamlit/secrets.toml` con este formato: "
        '`GEMINI_API_KEY = "tu_llave"`.'
    )
    st.stop()

# Streamlit vuelve a ejecutar la app tras cada interacción; el estado conserva
# el apunte, las respuestas elegidas y si el examen ya fue entregado.
if "apunte" not in st.session_state:
    st.session_state.apunte = None
if "respuestas_examen" not in st.session_state:
    st.session_state.respuestas_examen = {}
if "examen_entregado" not in st.session_state:
    st.session_state.examen_entregado = False
if "examen_celebrado" not in st.session_state:
    st.session_state.examen_celebrado = False


def analizar_imagen(imagen) -> None:
    if imagen is None:
        st.warning("Primero tomá o subí una foto de la página.")
        return

    try:
        with st.spinner("Analizando la página..."):
            cliente = crear_cliente(llave_api)
            apunte = analizar_pagina(
                imagen.getvalue(),
                imagen.type or "application/octet-stream",
                cliente,
            )
        st.session_state.apunte = apunte
        st.session_state.respuestas_examen = {}
        st.session_state.examen_entregado = False
        st.session_state.examen_celebrado = False
        for indice in range(len(apunte.examen)):
            clave = f"respuesta_examen_{indice}"
            if clave in st.session_state:
                del st.session_state[clave]
    except ImagenIlegible as error:
        st.warning(str(error))
    except Exception as error:
        st.error(f"No se pudo analizar la página. Intentá de nuevo. Detalle: {error}")


st.title("Mi cuaderno habla")
st.write("Tomá una foto o subí la página de tu cuaderno para crear una guía de estudio.")

pestana_foto, pestana_subir = st.tabs(["Tomar foto", "Subir imagen"])

with pestana_foto:
    imagen_camara = st.camera_input("Fotografiá la página")
    if st.button("Analizar la página", key="analizar_foto"):
        analizar_imagen(imagen_camara)

with pestana_subir:
    imagen_subida = st.file_uploader(
        "Elegí una imagen de la página",
        type=["png", "jpg", "jpeg", "webp"],
    )
    if st.button("Analizar la página", key="analizar_subida"):
        analizar_imagen(imagen_subida)


apunte = st.session_state.apunte
if apunte is not None:
    st.header(apunte.titulo)
    st.write(f"**Materia:** {apunte.materia}")
    st.write(f"**Dificultad:** {'⭐' * apunte.dificultad}")

    st.subheader("Resumen")
    st.write(apunte.resumen)

    if st.toggle("🔊 Escuchar el resumen"):
        datos_audio = decir(f"{apunte.titulo}. {apunte.resumen}")
        if datos_audio is not None:
            st.audio(datos_audio, format="audio/mp3")
        else:
            st.caption("La voz no está disponible en este momento.")

    st.subheader("Conceptos")
    for concepto in apunte.conceptos:
        st.markdown(f"- **{concepto.termino}:** {concepto.explicacion}")

    st.subheader("Tarjetas de repaso")
    for indice, tarjeta in enumerate(apunte.tarjetas, start=1):
        with st.expander(f"{indice}. {tarjeta.pregunta}"):
            st.write(tarjeta.respuesta)

    st.subheader("Examen")
    for indice, pregunta in enumerate(apunte.examen):
        clave = f"respuesta_examen_{indice}"
        respuesta = st.radio(
            pregunta.enunciado,
            options=range(len(pregunta.opciones)),
            format_func=lambda opcion, opciones=pregunta.opciones: opciones[opcion],
            index=None,
            key=clave,
            disabled=st.session_state.examen_entregado,
        )
        if respuesta is not None:
            st.session_state.respuestas_examen[indice] = respuesta

        if st.session_state.examen_entregado:
            if respuesta is None:
                st.info(f"Sin responder. La respuesta correcta es: {pregunta.opciones[pregunta.correcta]}")
            elif respuesta == pregunta.correcta:
                st.success("¡Correcta!")
            else:
                st.error(f"Incorrecta. La respuesta correcta es: {pregunta.opciones[pregunta.correcta]}")

    if not st.session_state.examen_entregado:
        if st.button("Entregar examen"):
            st.session_state.examen_entregado = True
            st.rerun()
    else:
        aciertos, total = calificar(apunte, st.session_state.respuestas_examen)
        st.metric("Puntaje", f"{aciertos} / {total}")
        if aciertos == total and not st.session_state.examen_celebrado:
            st.balloons()
            st.session_state.examen_celebrado = True

    st.download_button(
        "Descargar guía de estudio",
        data=apunte.a_markdown(),
        file_name="guia_de_estudio.md",
        mime="text/markdown",
    )


# === ANÁLISIS AVANZADO DE IMÁGENES ===
try:
    from analisis_imagen import ImagenAnalisis, analizar_imagen_avanzado, preguntar_sobre_imagen
except Exception:
    ANALISIS_AVANZADO_DISPONIBLE = False
else:
    ANALISIS_AVANZADO_DISPONIBLE = True

if ANALISIS_AVANZADO_DISPONIBLE:
    with st.expander('Análisis de imagen (OCR + descripción + clasificación + detección + chat)', expanded=False):
        st.write('Sube o toma una foto para analizarla con IA vision.')
        tab_f, tab_s = st.tabs(['Tomar foto', 'Subir imagen'])
        img_bytes = None; mime = None
        with tab_f:
            cam = st.camera_input('Fotografía la imagen')
            if cam is not None:
                img_bytes = cam.getvalue(); mime = cam.type or 'image/jpeg'
        with tab_s:
            upl = st.file_uploader('Elige una imagen', type=['png','jpg','jpeg','webp','bmp','gif','tiff'], key='avanzado')
            if upl is not None:
                img_bytes = upl.getvalue(); mime = upl.type or 'image/jpeg'
        if img_bytes is not None and st.button('Analizar imagen completa'):
            try:
                with st.spinner('Analizando...'):
                    cli = crear_cliente(llave_api)
                    res = analizar_imagen_avanzado(img_bytes, mime, cli)
                st.session_state['res_av'] = res
                st.session_state['img_av'] = (img_bytes, mime)
                st.success('Listo')
            except Exception as e:
                st.error(str(e))
        sav = st.session_state.get('res_av')
        iav = st.session_state.get('img_av')
        if isinstance(sav, ImagenAnalisis) and sav.tiene_resultados:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader('OCR')
                if sav.ocr:
                    st.text_area('Texto', sav.ocr, height=160, disabled=True)
                else:
                    st.caption('Sin texto visible')
                st.subheader('Clasificación')
                st.write(sav.clasificacion or '-')
            with c2:
                st.subheader('Descripción')
                st.write(sav.descripcion or '-')
                st.subheader('Detección')
                if sav.deteccion:
                    for x in sav.deteccion: st.markdown(f'- {x}')
                else:
                    st.caption('-')
            st.subheader('Chat con la imagen')
            if iav:
                q = st.text_input('Pregunta', key='qav')
                if st.button('Preguntar') and q.strip():
                    try:
                        with st.spinner('...'):
                            c2c = crear_cliente(llave_api)
                            rc = preguntar_sobre_imagen(iav[0], iav[1], q, c2c)
                        st.write(rc.respuesta)
                    except Exception as e:
                        st.error(str(e))

