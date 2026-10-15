import base64
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from cerebro import (
    ImagenIlegible,
    analizar_pagina,
    calificar,
    crear_cliente,
    generar_imagen,
    resumir_texto,
)
from modelos import Apunte, Pregunta


class InteraccionesFalsas:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        return self.respuesta


class ClienteFalso:
    def __init__(self, respuesta):
        self.interactions = InteraccionesFalsas(respuesta)


class ModelosFalsos:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []

    def generate_content(self, **kwargs):
        self.llamadas.append(kwargs)
        return self.respuesta


class ClienteConModelosFalsos:
    def __init__(self, respuesta):
        self.models = ModelosFalsos(respuesta)


@pytest.fixture
def datos_apunte():
    return {
        "titulo": "La célula",
        "materia": "Ciencias",
        "resumen": "Partes principales de la célula.",
        "conceptos": [
            {"termino": f"Concepto {indice}", "explicacion": "Explicación"}
            for indice in range(3)
        ],
        "tarjetas": [
            {"pregunta": f"Pregunta {indice}", "respuesta": "Respuesta"}
            for indice in range(5)
        ],
        "examen": [
            {
                "enunciado": f"Pregunta de examen {indice}",
                "opciones": ["Opción A", "Opción B", "Opción C", "Opción D"],
                "correcta": indice,
            }
            for indice in range(3)
        ],
        "dificultad": 2,
    }


@pytest.fixture
def apunte(datos_apunte):
    return Apunte.model_validate(datos_apunte)


def test_resume_texto_con_el_modelo_flash():
    cliente = ClienteConModelosFalsos(SimpleNamespace(text="Resumen breve."))

    resultado = resumir_texto("Texto original.", cliente)

    assert resultado == "Resumen breve."
    llamada = cliente.models.llamadas[0]
    assert llamada["model"] == "gemini-3.8-flash"
    assert "Texto original." in llamada["contents"]


def test_rechaza_resumir_texto_vacio_sin_llamar_a_la_ia():
    cliente = ClienteConModelosFalsos(SimpleNamespace(text=""))

    with pytest.raises(ValueError, match="texto que querés resumir no puede estar vacío"):
        resumir_texto("  ", cliente)

    assert cliente.models.llamadas == []


def test_avisa_si_la_ia_no_devuelve_un_resumen():
    cliente = ClienteConModelosFalsos(SimpleNamespace(text=None))

    with pytest.raises(ValueError, match="no devolvió un resumen"):
        resumir_texto("Texto original.", cliente)


def test_genera_imagen_con_el_modelo_de_imagen():
    parte = SimpleNamespace(inline_data=SimpleNamespace(data=b"datos de imagen"))
    cliente = ClienteConModelosFalsos(SimpleNamespace(parts=[parte]))

    resultado = generar_imagen("Un paisaje salvadoreño.", cliente)

    assert resultado == b"datos de imagen"
    llamada = cliente.models.llamadas[0]
    assert llamada["model"] == "gemini-2.5-flash-image"
    assert llamada["contents"] == "Un paisaje salvadoreño."
    assert llamada["config"].response_modalities == ["IMAGE"]


def test_rechaza_generar_imagen_sin_descripcion_sin_llamar_a_la_ia():
    cliente = ClienteConModelosFalsos(SimpleNamespace(parts=[]))

    with pytest.raises(ValueError, match="descripción de la imagen no puede estar vacía"):
        generar_imagen(" ", cliente)

    assert cliente.models.llamadas == []


def test_avisa_si_la_ia_no_devuelve_una_imagen():
    cliente = ClienteConModelosFalsos(SimpleNamespace(parts=[]))

    with pytest.raises(ValueError, match="no generó una imagen"):
        generar_imagen("Un paisaje salvadoreño.", cliente)


def test_devuelve_un_apunte_cuando_la_ia_contesta_bien(apunte):
    cliente = ClienteFalso(SimpleNamespace(output_text=apunte.model_dump_json()))

    resultado = analizar_pagina(b"imagen", "image/jpeg", cliente)

    assert resultado == apunte


def test_envia_el_esquema_y_el_formato_json_a_la_ia(apunte):
    cliente = ClienteFalso(SimpleNamespace(output_text=apunte.model_dump_json()))

    analizar_pagina(b"imagen", "image/jpeg", cliente)

    llamada = cliente.interactions.llamadas[0]
    assert llamada["model"] == "gemini-3.8-flash"
    assert llamada["response_format"]["mime_type"] == "application/json"
    assert llamada["response_format"]["schema"] == Apunte.model_json_schema()
    assert llamada["generation_config"]["thinking_level"] == "low"
    assert llamada["input"][0]["type"] == "image"
    assert llamada["input"][0]["data"] == base64.b64encode(b"imagen").decode("utf-8")
    assert llamada["input"][0]["mime_type"] == "image/jpeg"
    assert llamada["input"][1]["type"] == "text"


def test_esquema_indica_las_cantidades_minimas_requeridas():
    esquema = Apunte.model_json_schema()

    assert esquema["properties"]["conceptos"]["minItems"] == 3
    assert esquema["properties"]["tarjetas"]["minItems"] == 5
    assert esquema["properties"]["examen"]["minItems"] == 3
    pregunta = esquema["$defs"]["Pregunta"]["properties"]
    assert pregunta["opciones"]["minItems"] == 4
    assert pregunta["opciones"]["maxItems"] == 4
    assert pregunta["correcta"]["minimum"] == 0
    assert pregunta["correcta"]["maximum"] == 3


def test_recupera_el_apunte_desde_el_texto_de_la_interaccion(datos_apunte):
    respuesta = SimpleNamespace(output_text=json.dumps(datos_apunte))
    cliente = ClienteFalso(respuesta)

    resultado = analizar_pagina(b"imagen", "image/jpeg", cliente)

    assert isinstance(resultado, Apunte)
    assert resultado.titulo == "La célula"


def test_avisa_claro_cuando_la_ia_no_devuelve_nada():
    cliente = ClienteFalso(SimpleNamespace(output_text=None))

    with pytest.raises(ImagenIlegible, match="no devolvió contenido"):
        analizar_pagina(b"imagen", "image/jpeg", cliente)


def test_avisa_claro_cuando_la_ia_devuelve_texto_que_no_es_json():
    cliente = ClienteFalso(SimpleNamespace(output_text="Esto no es JSON"))

    with pytest.raises(ImagenIlegible, match="formato JSON válido"):
        analizar_pagina(b"imagen", "image/jpeg", cliente)


def test_muestra_detalle_cuando_la_respuesta_no_cumple_el_esquema(datos_apunte):
    datos_apunte["tarjetas"] = datos_apunte["tarjetas"][:2]
    cliente = ClienteFalso(SimpleNamespace(output_text=json.dumps(datos_apunte)))

    with pytest.raises(ImagenIlegible, match="tarjetas.*al menos cinco"):
        analizar_pagina(b"imagen", "image/jpeg", cliente)


def test_no_llama_a_la_ia_si_no_hay_imagen():
    cliente = ClienteFalso(SimpleNamespace(output_text=None))

    with pytest.raises(ValueError, match="No se recibió una imagen"):
        analizar_pagina(b"", "image/jpeg", cliente)

    assert cliente.interactions.llamadas == []


def test_no_se_puede_crear_cliente_sin_llave():
    with pytest.raises(ValueError, match="llave de acceso no puede estar vacía"):
        crear_cliente("  ")


def test_rechaza_una_pregunta_cuya_respuesta_correcta_es_cuatro():
    with pytest.raises(ValidationError, match="entre 0 y 3"):
        Pregunta(
            enunciado="¿Cuál es correcta?",
            opciones=["A", "B", "C", "D"],
            correcta=4,
        )


def test_rechaza_opciones_repetidas_sin_distinguir_mayusculas():
    with pytest.raises(ValidationError, match="deben ser distintas"):
        Pregunta(
            enunciado="¿Cuál es correcta?",
            opciones=["Agua", "AGUA", "Tierra", "Aire"],
            correcta=0,
        )


def test_rechaza_un_apunte_con_menos_tarjetas_de_las_pedidas(datos_apunte):
    datos_apunte["tarjetas"] = datos_apunte["tarjetas"][:4]

    with pytest.raises(ValidationError, match="al menos cinco tarjetas"):
        Apunte.model_validate(datos_apunte)


def test_rechaza_una_dificultad_fuera_de_rango(datos_apunte):
    datos_apunte["dificultad"] = 6

    with pytest.raises(ValidationError, match="entre 1 y 5"):
        Apunte.model_validate(datos_apunte)


def test_calificar_cuenta_todas_las_respuestas_buenas(apunte):
    respuestas = {indice: pregunta.correcta for indice, pregunta in enumerate(apunte.examen)}

    assert calificar(apunte, respuestas) == (3, 3)


def test_calificar_cuenta_aciertos_y_errores(apunte):
    respuestas = {0: apunte.examen[0].correcta, 1: 3, 2: apunte.examen[2].correcta}

    assert calificar(apunte, respuestas) == (2, 3)


def test_calificar_cuenta_como_incorrectas_las_preguntas_sin_responder(apunte):
    assert calificar(apunte, {}) == (0, 3)


def test_a_markdown_devuelve_la_guia_completa_con_respuestas_correctas(apunte):
    markdown = apunte.a_markdown()

    assert "# La célula" in markdown
    assert "**Materia:** Ciencias" in markdown
    assert "**Dificultad:** ⭐⭐ (2/5)" in markdown
    assert "## Resumen\n\nPartes principales de la célula." in markdown
    assert "- **Concepto 0:** Explicación" in markdown
    assert "1. **Pregunta:** Pregunta 0" in markdown
    assert "   **Respuesta:** Respuesta" in markdown
    assert "1. Pregunta de examen 0" in markdown
    assert "   a) Opción A ✓ **(respuesta correcta)**" in markdown
    assert "   b) Opción B" in markdown
    assert "3. Pregunta de examen 2" in markdown
    assert "   c) Opción C ✓ **(respuesta correcta)**" in markdown
