"""Test anti-hardcode (protege el Principio 2).

Decisión 6A: acotado. Escanea SOLO los literales numéricos a NIVEL DE MÓDULO en
`backend/dominio/` que estén fuera de una allowlist estructural. Los números
dentro de funciones (índices, factores de escala como 12 meses/año) no se marcan:
esa fue la decisión explícita para evitar falsos positivos.

Un peso, umbral o coste de negocio hardcodeado aparecería como una asignación a
nivel de módulo con un literal numérico (p.ej. `PESO_RENTABILIDAD = 0.40`) y este
test FALLARÍA. Los `Decimal(0)` / `Decimal(12)` no se marcan: su valor es una
llamada, no un literal numérico suelto.
"""

import ast
from pathlib import Path

DIR_DOMINIO = Path(__file__).resolve().parents[2] / "backend" / "dominio"

# Números estructurales permitidos a nivel de módulo (no son criterios de negocio).
ALLOWLIST = {0, 1}


def _literales_numericos_de_modulo(arbol: ast.Module) -> list[tuple[str, object]]:
    """Devuelve (nombre, valor) de asignaciones de nivel de módulo cuyo valor sea
    un literal numérico (int/float), incluyendo negativos, fuera de la allowlist."""
    hallazgos = []

    def valor_numerico(nodo):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)) \
                and not isinstance(nodo.value, bool):
            return nodo.value
        if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, ast.USub):
            base = valor_numerico(nodo.operand)
            return -base if base is not None else None
        return None

    for nodo in arbol.body:  # SOLO nivel de módulo
        objetivos = []
        if isinstance(nodo, ast.Assign):
            objetivos = [t.id for t in nodo.targets if isinstance(t, ast.Name)]
            valor = valor_numerico(nodo.value)
        elif isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
            objetivos = [nodo.target.id]
            valor = valor_numerico(nodo.value) if nodo.value else None
        else:
            continue
        if valor is not None and valor not in ALLOWLIST:
            for nombre in objetivos:
                hallazgos.append((nombre, valor))
    return hallazgos


def test_dominio_sin_constantes_de_negocio_a_nivel_de_modulo():
    archivos = list(DIR_DOMINIO.glob("*.py"))
    assert archivos, "no se encontraron módulos en backend/dominio"
    infracciones = []
    for archivo in archivos:
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        for nombre, valor in _literales_numericos_de_modulo(arbol):
            infracciones.append(f"{archivo.name}: {nombre} = {valor}")
    assert not infracciones, (
        "Constantes numéricas de negocio a nivel de módulo en backend/dominio "
        "(deben vivir en BD, Principio 2):\n" + "\n".join(infracciones)
    )


def test_el_test_detecta_una_infraccion_real():
    """El propio test debe cazar un hardcode. Verificación del verificador."""
    codigo = "PESO_RENTABILIDAD = 0.40\nUMBRAL = 5\nOK = 1\n"
    arbol = ast.parse(codigo)
    hallazgos = _literales_numericos_de_modulo(arbol)
    nombres = {n for n, _ in hallazgos}
    assert "PESO_RENTABILIDAD" in nombres
    assert "UMBRAL" in nombres
    assert "OK" not in nombres  # 1 está en la allowlist
