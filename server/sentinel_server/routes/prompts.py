"""Prompt registry: git-like versioning, activation, and rollback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_api_key
from ..db import get_session
from ..models import PromptVersion
from ..schemas import PromptCreate, PromptOut

router = APIRouter(tags=["prompts"], dependencies=[Depends(require_api_key)])


async def _next_version(session: AsyncSession, name: str) -> int:
    current = (
        await session.execute(
            select(func.max(PromptVersion.version)).where(PromptVersion.name == name)
        )
    ).scalar()
    return (current or 0) + 1


async def _set_active(session: AsyncSession, name: str, version: int) -> None:
    await session.execute(
        update(PromptVersion)
        .where(PromptVersion.name == name)
        .values(is_active=False)
    )
    await session.execute(
        update(PromptVersion)
        .where(PromptVersion.name == name, PromptVersion.version == version)
        .values(is_active=True)
    )


@router.post("/api/prompts", response_model=PromptOut, status_code=201)
async def create_prompt(
    payload: PromptCreate, session: AsyncSession = Depends(get_session)
) -> PromptVersion:
    version = await _next_version(session, payload.name)
    prompt = PromptVersion(
        name=payload.name,
        version=version,
        template=payload.template,
        description=payload.description,
        variables=payload.variables,
        meta=payload.meta,
        is_active=False,
    )
    session.add(prompt)
    await session.flush()
    if payload.activate:
        await _set_active(session, payload.name, version)
        prompt.is_active = True
    await session.commit()
    await session.refresh(prompt)
    return prompt


@router.get("/api/prompts", response_model=list[PromptOut])
async def list_prompt_names(session: AsyncSession = Depends(get_session)) -> list[PromptVersion]:
    """Return the active (or latest) version of every named prompt."""
    subq = (
        select(PromptVersion.name, func.max(PromptVersion.version).label("v"))
        .group_by(PromptVersion.name)
        .subquery()
    )
    stmt = select(PromptVersion).join(
        subq,
        (PromptVersion.name == subq.c.name) & (PromptVersion.version == subq.c.v),
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/api/prompts/{name}/versions", response_model=list[PromptOut])
async def list_versions(
    name: str, session: AsyncSession = Depends(get_session)
) -> list[PromptVersion]:
    stmt = (
        select(PromptVersion)
        .where(PromptVersion.name == name)
        .order_by(PromptVersion.version.desc())
    )
    rows = list((await session.execute(stmt)).scalars().all())
    if not rows:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return rows


@router.get("/api/prompts/{name}/active", response_model=PromptOut)
async def get_active(
    name: str, session: AsyncSession = Depends(get_session)
) -> PromptVersion:
    stmt = select(PromptVersion).where(
        PromptVersion.name == name, PromptVersion.is_active.is_(True)
    )
    prompt = (await session.execute(stmt)).scalars().first()
    if prompt is None:
        raise HTTPException(status_code=404, detail="No active version for this prompt")
    return prompt


@router.post("/api/prompts/{name}/rollback/{version}", response_model=PromptOut)
async def rollback(
    name: str, version: int, session: AsyncSession = Depends(get_session)
) -> PromptVersion:
    stmt = select(PromptVersion).where(
        PromptVersion.name == name, PromptVersion.version == version
    )
    target = (await session.execute(stmt)).scalars().first()
    if target is None:
        raise HTTPException(status_code=404, detail="Version not found")
    await _set_active(session, name, version)
    await session.commit()
    await session.refresh(target)
    return target
