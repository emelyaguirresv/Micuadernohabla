from pydantic import BaseModel, Field, field_validator, model_validator


class Concepto(BaseModel):
    termino: str = Field(description="Término o concepto importante que aparece en los apuntes.")
    explicacion: str = Field(description="Explicación clara del término, basada en el contenido de los apuntes.")


class Tarjeta(BaseModel):
    pregunta: str = Field(description="Pregunta breve para repasar un dato o concepto de los apuntes.")
    respuesta: str = Field(description="Respuesta correcta y concisa a la pregunta de repaso.")


class Pregunta(BaseModel):
    enunciado: str = Field(description="Enunciado de una pregunta de opción múltiple sobre los apuntes.")
    opciones: list[str] = Field(
        description="Lista de exactamente cuatro opciones de respuesta para la pregunta.",
        json_schema_extra={"minItems": 4, "maxItems": 4},
    )
    correcta: int = Field(
        description="Índice, empezando en cero, de la opción correcta entre las cuatro opciones.",
        json_schema_extra={"minimum": 0, "maximum": 3},
    )

    @field_validator("opciones")
    @classmethod
    def validar_opciones(cls, opciones: list[str]) -> list[str]:
        if len(opciones) != 4:
            raise ValueError(f"La pregunta debe tener exactamente cuatro opciones; se recibieron {len(opciones)}.")

        opciones_sin_distinguir_mayusculas = [opcion.casefold() for opcion in opciones]
        if len(set(opciones_sin_distinguir_mayusculas)) != 4:
            raise ValueError("Las cuatro opciones deben ser distintas, sin diferencias únicamente de mayúsculas y minúsculas.")

        return opciones

    @model_validator(mode="after")
    def validar_indice_correcto(self) -> "Pregunta":
        if not 0 <= self.correcta < len(self.opciones):
            raise ValueError(
                f"El índice de la opción correcta debe estar entre 0 y 3; se recibió {self.correcta}."
            )

        return self


class Apunte(BaseModel):
    titulo: str = Field(description="Título breve que identifica el tema principal de la página.")
    materia: str = Field(description="Asignatura a la que corresponde el contenido de la página.")
    resumen: str = Field(description="Resumen claro de las ideas principales de la página.")
    conceptos: list[Concepto] = Field(
        description="Al menos tres conceptos importantes extraídos de la página y sus explicaciones.",
        json_schema_extra={"minItems": 3},
    )
    tarjetas: list[Tarjeta] = Field(
        description="Al menos cinco tarjetas de pregunta y respuesta para estudiar el contenido.",
        json_schema_extra={"minItems": 5},
    )
    examen: list[Pregunta] = Field(
        description="Al menos tres preguntas de opción múltiple para evaluar la comprensión del contenido.",
        json_schema_extra={"minItems": 3},
    )
    dificultad: int = Field(
        description="Nivel de dificultad general del contenido, expresado como un número entero entre 1 y 5.",
        json_schema_extra={"minimum": 1, "maximum": 5},
    )

    @field_validator("dificultad")
    @classmethod
    def validar_dificultad(cls, dificultad: int) -> int:
        if not 1 <= dificultad <= 5:
            raise ValueError(f"La dificultad debe estar entre 1 y 5; se recibió {dificultad}.")

        return dificultad

    @field_validator("conceptos")
    @classmethod
    def validar_cantidad_conceptos(cls, conceptos: list[Concepto]) -> list[Concepto]:
        if len(conceptos) < 3:
            raise ValueError(f"El apunte debe incluir al menos tres conceptos; se recibieron {len(conceptos)}.")

        return conceptos

    @field_validator("tarjetas")
    @classmethod
    def validar_cantidad_tarjetas(cls, tarjetas: list[Tarjeta]) -> list[Tarjeta]:
        if len(tarjetas) < 5:
            raise ValueError(f"El apunte debe incluir al menos cinco tarjetas; se recibieron {len(tarjetas)}.")

        return tarjetas

    @field_validator("examen")
    @classmethod
    def validar_cantidad_preguntas(cls, examen: list[Pregunta]) -> list[Pregunta]:
        if len(examen) < 3:
            raise ValueError(f"El examen debe incluir al menos tres preguntas; se recibieron {len(examen)}.")

        return examen

    def a_markdown(self) -> str:
        lineas = [
            f"# {self.titulo}",
            "",
            f"**Materia:** {self.materia}",
            f"**Dificultad:** {'⭐' * self.dificultad} ({self.dificultad}/5)",
            "",
            "## Resumen",
            "",
            self.resumen,
            "",
            "## Conceptos clave",
            "",
        ]

        lineas.extend(
            f"- **{concepto.termino}:** {concepto.explicacion}"
            for concepto in self.conceptos
        )
        lineas.extend(["", "## Tarjetas de estudio", ""])

        for indice, tarjeta in enumerate(self.tarjetas, start=1):
            lineas.extend(
                [
                    f"{indice}. **Pregunta:** {tarjeta.pregunta}",
                    f"   **Respuesta:** {tarjeta.respuesta}",
                ]
            )

        lineas.extend(["", "## Examen", ""])
        letras_opciones = ("a", "b", "c", "d")

        for indice, pregunta in enumerate(self.examen, start=1):
            lineas.append(f"{indice}. {pregunta.enunciado}")
            for indice_opcion, opcion in enumerate(pregunta.opciones):
                marca_correcta = " ✓ **(respuesta correcta)**" if indice_opcion == pregunta.correcta else ""
                lineas.append(f"   {letras_opciones[indice_opcion]}) {opcion}{marca_correcta}")
            lineas.append("")

        return "\n".join(lineas).rstrip()
