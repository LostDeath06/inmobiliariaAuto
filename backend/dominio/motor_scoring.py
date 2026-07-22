"""Motor de scoring agnóstico.

PRINCIPIO 2: no conoce la semántica de ningún componente. Recibe un diccionario de
componentes crudos, un diccionario de pesos y las curvas de normalización, y
devuelve un número. Añadir un componente nuevo = añadir una clave en los dicts.
Cero código.

FUNCIÓN PURA: mismos inputs → mismo output, siempre. Sin I/O, sin configuración,
sin constantes de negocio a nivel de módulo.

Reglas:
- Cada componente se normaliza a 0–100 según su curva.
- Un componente no calculable (valor None) NO se pone a 0: se excluye y su peso se
  redistribuye entre los calculables → el score se marca PARCIAL.
- Si no hay ningún componente calculable → NO_CALCULABLE.
- riesgo_pais entra como multiplicador: score_total = score_bruto × (1 − riesgo_pais).
- El desglose guarda la contribución exacta de cada componente (para ver POR QUÉ 87).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..modelos.enumeraciones import CalidadDato

VERSION_MOTOR_SCORING = "motor-scoring-1.0.0"


@dataclass(frozen=True)
class ResultadoScoring:
    score_bruto: Decimal | None
    score_total: Decimal | None
    estado_calidad: CalidadDato
    desglose: dict = field(default_factory=dict)
    version_motor: str = VERSION_MOTOR_SCORING


def _normalizar(raw: Decimal, curva: dict) -> Decimal:
    """Mapea un valor crudo a 0–100 según la curva (lineal, con dirección)."""
    minimo = Decimal(str(curva.get("min", 0)))
    maximo = Decimal(str(curva.get("max", 1)))
    direccion = curva.get("direccion", "asc")
    cien = Decimal(100)
    if maximo == minimo:
        return Decimal(0)
    t = (raw - minimo) / (maximo - minimo)
    # clamp 0..1
    if t < 0:
        t = Decimal(0)
    elif t > 1:
        t = Decimal(1)
    if direccion == "desc":
        t = Decimal(1) - t
    return t * cien


def calcular_score(
    componentes_crudos: dict[str, Decimal | None],
    pesos: dict[str, float | Decimal],
    normalizacion: dict[str, dict],
    riesgo_pais: Decimal,
) -> ResultadoScoring:
    """Calcula el score agnósticamente. Ver reglas en el docstring del módulo."""
    desglose: dict = {"componentes": {}}
    peso_disponible = Decimal(0)
    calculables: dict[str, tuple[Decimal, Decimal]] = {}  # nombre -> (normalizado, peso)

    for nombre, peso in pesos.items():
        peso_d = Decimal(str(peso))
        raw = componentes_crudos.get(nombre)
        if raw is None:
            desglose["componentes"][nombre] = {
                "calculable": False, "peso": str(peso_d),
                "valor_crudo": None, "valor_normalizado": None, "contribucion": None,
            }
            continue
        curva = normalizacion.get(nombre, {"min": 0, "max": 1, "direccion": "asc"})
        normalizado = _normalizar(Decimal(str(raw)), curva)
        calculables[nombre] = (normalizado, peso_d)
        peso_disponible += peso_d
        desglose["componentes"][nombre] = {
            "calculable": True, "peso": str(peso_d),
            "valor_crudo": str(raw), "valor_normalizado": str(normalizado),
            "contribucion": None,  # se rellena tras redistribuir
        }

    if peso_disponible == 0:
        desglose["motivo"] = "ningún componente calculable"
        return ResultadoScoring(
            score_bruto=None, score_total=None,
            estado_calidad=CalidadDato.NO_CALCULABLE, desglose=desglose,
        )

    # Redistribución del peso de los componentes faltantes entre los disponibles.
    score_bruto = Decimal(0)
    for nombre, (normalizado, peso_d) in calculables.items():
        peso_efectivo = peso_d / peso_disponible
        contribucion = normalizado * peso_efectivo
        score_bruto += contribucion
        d = desglose["componentes"][nombre]
        d["peso_efectivo"] = str(peso_efectivo)
        d["contribucion"] = str(contribucion)

    hubo_redistribucion = len(calculables) < len(pesos)
    estado = CalidadDato.PARCIAL if hubo_redistribucion else CalidadDato.COMPLETO

    riesgo = Decimal(str(riesgo_pais))
    score_total = score_bruto * (Decimal(1) - riesgo)
    if score_total < 0:
        score_total = Decimal(0)

    desglose["score_bruto"] = str(score_bruto)
    desglose["riesgo_pais"] = str(riesgo)
    desglose["score_total"] = str(score_total)
    desglose["peso_disponible"] = str(peso_disponible)
    desglose["hubo_redistribucion"] = hubo_redistribucion

    return ResultadoScoring(
        score_bruto=score_bruto, score_total=score_total,
        estado_calidad=estado, desglose=desglose,
    )
