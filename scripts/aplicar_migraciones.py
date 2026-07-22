"""Aplica las migraciones SQL versionadas y los seeds.

Uso:
    python scripts/aplicar_migraciones.py

- Las migraciones (`supabase/migrations/*.sql`) se aplican una sola vez y se
  registran en la tabla `_migraciones_aplicadas`. Reejecutar el script no las
  vuelve a aplicar.
- Los seeds (`supabase/seeds/*.sql`) son idempotentes (ON CONFLICT DO NOTHING)
  y se ejecutan en cada corrida.

Falla ruidosamente: si una migración da error, aborta y lo muestra.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg

RAIZ = Path(__file__).resolve().parent.parent
DIR_MIGRACIONES = RAIZ / "supabase" / "migrations"
DIR_SEEDS = RAIZ / "supabase" / "seeds"

# Import perezoso de la config del backend.
sys.path.insert(0, str(RAIZ))
from backend.nucleo.config import obtener_config  # noqa: E402

SQL_TABLA_CONTROL = """
CREATE TABLE IF NOT EXISTS _migraciones_aplicadas (
    archivo     TEXT PRIMARY KEY,
    aplicada_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


async def _aplicar_migraciones(con: asyncpg.Connection) -> None:
    await con.execute(SQL_TABLA_CONTROL)
    aplicadas = {
        r["archivo"]
        for r in await con.fetch("SELECT archivo FROM _migraciones_aplicadas")
    }
    for archivo in sorted(DIR_MIGRACIONES.glob("*.sql")):
        if archivo.name in aplicadas:
            print(f"  = {archivo.name} (ya aplicada)")
            continue
        sql = archivo.read_text(encoding="utf-8")
        async with con.transaction():
            await con.execute(sql)
            await con.execute(
                "INSERT INTO _migraciones_aplicadas (archivo) VALUES ($1)",
                archivo.name,
            )
        print(f"  + {archivo.name} aplicada")


async def _aplicar_seeds(con: asyncpg.Connection) -> None:
    for archivo in sorted(DIR_SEEDS.glob("*.sql")):
        sql = archivo.read_text(encoding="utf-8")
        await con.execute(sql)
        print(f"  ~ {archivo.name} sembrada")


async def main() -> None:
    cfg = obtener_config()
    print(f"Conectando a la base de datos…")
    con = await asyncpg.connect(dsn=cfg.database_url)
    try:
        print("Migraciones:")
        await _aplicar_migraciones(con)
        print("Seeds:")
        await _aplicar_seeds(con)
        print("Listo: esquema y seeds al día.")
    finally:
        await con.close()


if __name__ == "__main__":
    asyncio.run(main())
