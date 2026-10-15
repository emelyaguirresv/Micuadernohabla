import base64
from typing import Dict, List, Tuple

from google.genai import Client, types


class ImagenAnalisis:
    """Resultados del análisis avanzado de una imagen."""

    def __init__(
        self,
        ocr: str = "",
        descripcion: str = "",
        clasificacion: str = "",
        deteccion: List[str] = None,
        respuesta_chat: str = "",
    ) -> None:
        self.ocr = ocr
        self.descripcion = descripcion
        self.clasificacion = clasificacion
        self.deteccion = deteccion or []
        self.respuesta_chat = respuesta_chat

    @property
    def tiene_resultados(self) -> bool:
        return any(
            [
                self.ocr.strip(),
                self.descripcion.strip(),
                self.clasificacion.strip(),
                self.deteccion,
            ]
        )


class ChatAnalisis:
    """Resultados de una pregunta sobre la imagen."""

    def __init__(self, respuesta: str = "") -> None:
        self.respuesta = respuesta


def _parsear_seccion(texto: str, etiqueta: str) -> str:
    """Extrae una sección siguiendo el patrón 'ETIQUETA: ...'."""
    import re

    patron = re.compile(
        rf"{re.escape(etiqueta)}:\s*(.*?)(?=(?:OCR|TEXTO|DESCRIPCI|CLASIFIC|DETECC|OBJETOS|RESPUESTA):\s*|$)",
        re.IGNORECASE | re.DOTALL,
    )
    coincidencia = patron.search(texto)
    if not coincidencia:
        return ""
    resultado = coincidencia.group(1).strip()
    return resultado


def _parsear_deteccion(texto: str) -> List[str]:
    seccion = (
        _parsear_seccion(texto, "DETECCIÓN")
        or _parsear_seccion(texto, "DETECCION")
        or _parsear_seccion(texto, "OBJETOS")
    )
    if not seccion:
        return []
    items = []
    for separador in [",", ";", "\n", "\r"]:
        if separador in seccion:
            items = [item.strip(" -•\t") for item in seccion.split(separador)]
            break
    if not items:
        items = [seccion.strip()]
    return [item for item in items if item]


def analizar_imagen_avanzado(
    datos_imagen: bytes,
    tipo_mime: str,
    cliente: Client,
    modelo: str = "gemini-2.5-flash",
) -> ImagenAnalisis:
    """Analiza una imagen: OCR, descripción, clasificación, detección."""
    prompt = (
        "Analiza esta imagen con mucho detalle. "
        "Responde ÚNICAMENTE en español salvadoreño claro y en el siguiente formato:\n"
        "OCR: [texto visible extraído palabra por palabra]\n"
        "DESCRIPCIÓN: [descripción general detallada]\n"
        "CLASIFICACIÓN: [categoría o tipo de imagen]\n"
        "DETECCIÓN: [lista separada por comas de objetos, personas, elementos detectados]\n"
        "RESPUESTA: [breve resumen del análisis]"
    )

    respuesta = cliente.models.generate_content(
        model=modelo,
        contents=[
            types.Part(text=prompt),
            types.Part.from_bytes(data=datos_imagen, mime_type=tipo_mime),
        ],
    )

    if not respuesta.text:
        raise ValueError("Gemini no devolvió el análisis de la imagen.")

    texto = respuesta.text
    ocr = _parsear_seccion(texto, "OCR") or _parsear_seccion(texto, "TEXTO")
    descripcion = _parsear_seccion(texto, "DESCRIPCIÓN") or _parsear_seccion(texto, "DESCRIPCION")
    clasificacion = _parsear_seccion(texto, "CLASIFICACIÓN") or _parsear_seccion(texto, "CLASIFICACION")
    deteccion = _parsear_deteccion(texto)
    respuesta_chat = _parsear_seccion(texto, "RESPUESTA") or texto[:500]

    return ImagenAnalisis(
        ocr=ocr,
        descripcion=descripcion,
        clasificacion=clasificacion,
        deteccion=deteccion,
        respuesta_chat=respuesta_chat,
    )


def preguntar_sobre_imagen(
    datos_imagen: bytes,
    tipo_mime: str,
    pregunta: str,
    cliente: Client,
    modelo: str = "gemini-2.5-flash",
) -> ChatAnalisis:
    """Hace una pregunta específica sobre la imagen."""
    if not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")

    prompt = (
        f"Responde en español salvadoreño claro y conciso. "
        f"Basándote ÚNICAMENTE en lo que ves en la imagen, responde: {pregunta}"
    )

    respuesta = cliente.models.generate_content(
        model=modelo,
        contents=[
            types.Part(text=prompt),
            types.Part.from_bytes(data=datos_imagen, mime_type=tipo_mime),
        ],
    )

    if not respuesta.text:
        raise ValueError("Gemini no devolvió respuesta a la pregunta.")

    return ChatAnalisis(respuesta=respuesta.text.strip())
