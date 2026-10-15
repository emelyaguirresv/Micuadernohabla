from io import BytesIO

from gtts import gTTS


def decir(texto: str, idioma: str = "es") -> bytes | None:
    try:
        if not texto or not texto.strip():
            return None

        audio = BytesIO()
        sintesis = gTTS(text=texto[:1500], lang=idioma)
        sintesis.write_to_fp(audio)
        return audio.getvalue()
    except Exception:
        return None
