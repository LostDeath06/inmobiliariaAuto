"""Modelo base Pydantic v2 con validación estricta."""

from pydantic import BaseModel, ConfigDict


class ModeloBase(BaseModel):
    """Base de todos los modelos.

    `extra="forbid"`: cualquier campo no declarado es un error. Esto protege la
    ingesta (§5.2): si OpenClaw o Claude mandan un campo inesperado, se rechaza
    en lugar de tragárselo en silencio.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
