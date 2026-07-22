"""Endpoints de perfiles de inversor."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..repositorios import perfiles as repo
from ..repositorios import scores as repo_scores

router = APIRouter(prefix="/api/perfiles", tags=["perfiles"])


@router.get("")
async def listar():
    return await repo.listar()


@router.get("/{perfil_id}")
async def obtener(perfil_id: UUID):
    perfil = await repo.obtener(perfil_id)
    if perfil is None:
        raise HTTPException(404, "Perfil no encontrado")
    return perfil


@router.post("")
async def crear(body: dict):
    return await repo.crear(
        nombre=body["nombre"],
        descripcion=body.get("descripcion"),
        pesos=body.get("pesos", {}),
        supuestos=body.get("supuestos", {}),
        es_predeterminado=body.get("es_predeterminado", False),
        activo=body.get("activo", True),
    )


@router.put("/{perfil_id}")
async def actualizar(perfil_id: UUID, body: dict):
    perfil = await repo.actualizar(perfil_id, body)
    if perfil is None:
        raise HTTPException(404, "Perfil no encontrado")
    # Si cambiaron los pesos, los scores del perfil quedan obsoletos (§9).
    obsoletos = 0
    if "pesos" in body:
        obsoletos = await repo_scores.marcar_obsoletos_de_perfil(perfil_id)
    return {"perfil": perfil, "scores_marcados_obsoletos": obsoletos}


@router.delete("/{perfil_id}")
async def eliminar(perfil_id: UUID):
    ok = await repo.eliminar(perfil_id)
    if not ok:
        raise HTTPException(404, "Perfil no encontrado")
    return {"eliminado": True}
