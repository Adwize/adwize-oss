import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import check_api_key
from api.database import get_db
from api.models.rule import Rule, RuleType
from api.schemas.rule import (
    FieldValidationConfig,
    RuleCreate,
    RuleResponse,
    RuleUpdate,
    ThresholdConfig,
    VolumeConfig,
)

router = APIRouter()


@router.post("/", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_data: RuleCreate,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    rule = Rule(
        id=uuid.uuid4(),
        name=rule_data.name,
        rule_type=rule_data.rule_type,
        is_active=rule_data.is_active,
        config=rule_data.config,
        tag=rule_data.tag,
        category=rule_data.category,
    )

    db.add(rule)

    try:
        await db.commit()
        await db.refresh(rule)
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rule creation failed: {str(e)}",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create rule: {str(e)}",
        )

    return RuleResponse.model_validate(rule)


@router.get("/", response_model=list[RuleResponse])
async def list_rules(
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
    active_only: bool = False,
    tag: str | None = Query(None, max_length=20),
    category: str | None = Query(None, max_length=20),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[RuleResponse]:
    query = select(Rule)

    if active_only:
        query = query.where(Rule.is_active == True)  # noqa: E712

    if tag:
        query = query.where(Rule.tag == tag)
    if category:
        query = query.where(Rule.category == category)

    query = query.order_by(Rule.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    rules = result.scalars().all()

    return [RuleResponse.model_validate(rule) for rule in rules]


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: uuid.UUID,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule_id} not found",
        )

    return RuleResponse.model_validate(rule)


@router.patch("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: uuid.UUID,
    rule_update: RuleUpdate,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule_id} not found",
        )

    if rule_update.name is not None:
        rule.name = rule_update.name

    if rule_update.config is not None:
        try:
            if rule.rule_type == RuleType.THRESHOLD:
                ThresholdConfig(**rule_update.config)
            elif rule.rule_type == RuleType.FIELD_VALIDATION:
                FieldValidationConfig(**rule_update.config)
            elif rule.rule_type == RuleType.VOLUME:
                VolumeConfig(**rule_update.config)
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid config for {rule.rule_type} rule: {e.errors()}",
            )
        rule.config = rule_update.config

    if rule_update.is_active is not None:
        rule.is_active = rule_update.is_active

    if rule_update.tag is not None:
        rule.tag = rule_update.tag if rule_update.tag else None

    if rule_update.category is not None:
        rule.category = rule_update.category if rule_update.category else None

    try:
        await db.commit()
        await db.refresh(rule)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update rule: {str(e)}",
        )

    return RuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule_id} not found",
        )

    await db.delete(rule)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete rule: {str(e)}",
        )
