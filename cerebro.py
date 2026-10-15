import base64
import json

from google.genai import Client, types
from pydantic import ValidationError

from modelos import Apunte


MODELO_RESUMEN = "gemini-3.8-flash"
MODELO_IA = MODELO_RESUMEN
MODELO_IMAGEN = "gemini-2.5-flash-image"
INSTRUCCION_SISTEMA = (
    "Actúa como un profesor paciente de bachillerato de El Salvador. "
    "Escribe siempre en español salvadoreño claro. Basa tu análisis únicamente "
    "en lo que se ve en la imagen y no inventes temas. Si la foto está borrosa, "
    "dilo en el resumen en vez de inventar. Incluye al menos tres conceptos, "
    "cinco tarjetas de repaso y tres preguntas de examen; todas deben basarse "
    "en información visible en la página. Cada pregunta debe tener exactamente "
    "cuatro opciones distintas, con una respuesta correcta. Haz que las opciones "
    "incorrectas sean creíbles y varía la posición de la respuesta correcta."
)


class ImagenIlegible(Exception):
    """Indica que no se pudo obtener un apunte confiable de la imagen."""


def crear_cliente(api_key: str) -> Client:
    if not api_key or not api_key.strip():
        raise ValueError("La llave de acceso no puede estar vacía.")

    return Client(api_key=api_key)


def resumir_texto(texto: str, cliente: Client) -> str:
    if not texto or not texto.strip():
        raise ValueError("El texto que querés resumir no puede estar vacío.")

    respuesta = cliente.models.generate_content(
        model=MODELO_RESUMEN,
        contents=f"Resume en español claro y conservá las ideas principales:\n\n{texto}",
    )
    resumen = respuesta.text
    if not resumen or not resumen.strip():
        raise ValueError("La IA no devolvió un resumen. Intentá de nuevo.")
    return resumen.strip()


def generar_imagen(prompt: str, cliente: Client) -> bytes:
    if not prompt or not prompt.strip():
        raise ValueError("La descripción de la imagen no puede estar vacía.")

    respuesta = cliente.models.generate_content(
        model=MODELO_IMAGEN,
        contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    for parte in respuesta.parts or []:
        if parte.inline_data and parte.inline_data.data:
            return parte.inline_data.data

    raise ValueError("La IA no generó una imagen. Probá con otra descripción.")


def analizar_pagina(datos_imagen: bytes, tipo_mime: str, cliente: Client) -> Apunte:
    if not datos_imagen:
        raise ValueError("No se recibió una imagen para analizar.")

    respuesta = cliente.interactions.create(
        model=MODELO_IA,
        input=[
            {
                "type": "image",
                "data": base64.b64encode(datos_imagen).decode("utf-8"),
                "mime_type": tipo_mime,
            },
            {
                "type": "text",
                "text": "Analiza esta página y organiza su contenido para estudiar.",
            },
        ],
        system_instruction=INSTRUCCION_SISTEMA,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": Apunte.model_json_schema(),
        },
        generation_config={"thinking_level": "low"},
    )

    if not respuesta.output_text:
        raise ImagenIlegible(
            "Gemini no devolvió contenido. Probá con una foto clara, bien iluminada y enfocada."
        )

    try:
        contenido = json.loads(respuesta.output_text)
    except (json.JSONDecodeError, TypeError) as error:
        raise ImagenIlegible(
            "Gemini devolvió una respuesta que no tiene formato JSON válido. "
            f"Detalle: {error}"
        ) from error

    try:
        return Apunte.model_validate(contenido)
    except ValidationError as error:
        detalles = "; ".join(
            f"{'.'.join(str(parte) for parte in incidencia['loc'])}: {incidencia['msg']}"
            for incidencia in error.errors(include_input=False, include_url=False)
        )
        raise ImagenIlegible(
            "Gemini respondió, pero el contenido no cumplió el formato de la guía. "
            f"Detalle: {detalles}. Probá con una foto clara que muestre suficiente contenido."
        ) from error


def calificar(apunte: Apunte, respuestas: dict) -> tuple[int, int]:
    aciertos = sum(
        respuestas.get(indice) == pregunta.correcta
        for indice, pregunta in enumerate(apunte.examen)
    )
    return aciertos, len(apunte.examen)
