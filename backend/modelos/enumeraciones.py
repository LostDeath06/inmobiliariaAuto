"""Enumeraciones del dominio, espejo de los ENUM de PostgreSQL.

Son categorías estructurales cerradas. Los valores de negocio (pesos, umbrales,
costes) NO son enums: viven en base de datos como datos editables. El catálogo de
riesgos/oportunidades tampoco es un enum rígido: vive en BD y es por país.
"""

from enum import Enum


class NivelReforma(str, Enum):
    NINGUNA = "NINGUNA"
    COSMETICA = "COSMETICA"
    MEDIA = "MEDIA"
    INTEGRAL = "INTEGRAL"
    DESCONOCIDO = "DESCONOCIDO"


class EstadoJob(str, Enum):
    PENDIENTE = "PENDIENTE"
    ENVIADO = "ENVIADO"
    EN_PROGRESO = "EN_PROGRESO"
    COMPLETADO = "COMPLETADO"
    PARCIAL = "PARCIAL"
    FALLIDO = "FALLIDO"
    CANCELADO = "CANCELADO"


class TipoGastoAdquisicion(str, Enum):
    PORCENTAJE = "PORCENTAJE"
    FIJO = "FIJO"


class EstadoConservacion(str, Enum):
    OBRA_NUEVA = "OBRA_NUEVA"
    REFORMADO = "REFORMADO"
    BUEN_ESTADO = "BUEN_ESTADO"
    A_REFORMAR = "A_REFORMAR"
    RUINA = "RUINA"
    DESCONOCIDO = "DESCONOCIDO"


class Tipologia(str, Enum):
    PISO = "PISO"
    ATICO = "ATICO"
    BAJO = "BAJO"
    DUPLEX = "DUPLEX"
    CASA = "CASA"
    CHALET = "CHALET"
    LOCAL = "LOCAL"
    SOLAR = "SOLAR"
    OTRO = "OTRO"


class AptoTernario(str, Enum):
    SI = "SI"
    NO = "NO"
    DUDOSO = "DUDOSO"


class CalidadDescripcion(str, Enum):
    DETALLADA = "DETALLADA"
    ESTANDAR = "ESTANDAR"
    POBRE = "POBRE"
    ENGANOSA = "ENGANOSA"


class CoherenciaPrecio(str, Enum):
    COHERENTE = "COHERENTE"
    SOSPECHOSAMENTE_BAJO = "SOSPECHOSAMENTE_BAJO"
    SOBREVALORADO = "SOBREVALORADO"
    NO_EVALUABLE = "NO_EVALUABLE"


class NivelConfianza(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class TipoAnunciante(str, Enum):
    PARTICULAR = "PARTICULAR"
    AGENCIA = "AGENCIA"
    PROMOTOR = "PROMOTOR"
    DESCONOCIDO = "DESCONOCIDO"


class CalidadDato(str, Enum):
    COMPLETO = "COMPLETO"
    PARCIAL = "PARCIAL"
    NO_CALCULABLE = "NO_CALCULABLE"
    DESCARTADO_RIESGO = "DESCARTADO_RIESGO"  # excluido del ranking, sin ponderar


class EstadoParametro(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    VALIDADO = "VALIDADO"


class ClaseSenal(str, Enum):
    RIESGO = "RIESGO"
    OPORTUNIDAD = "OPORTUNIDAD"


class PerfilZona(str, Enum):
    """Cómo se explota una zona. TURISTICA = plusvalía / alquiler de corta estancia:
    el score de cashflow (larga estancia, apalancado) NO es representativo ahí."""

    ESTANDAR = "ESTANDAR"
    TURISTICA = "TURISTICA"
