import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.logger import get_logger  # noqa: E402
from api.models.alert import Alert  # noqa: E402
from api.models.event import Event  # noqa: E402
from api.models.rule import Rule, RuleType  # noqa: E402
from api.services.alert_dispatcher import dispatch_webhook  # noqa: E402
from api.services.rule_engine import (  # noqa: E402
    check_should_create_alert,
    evaluate_field_validation_rule,
    evaluate_threshold_rule,
    evaluate_volume_rule,
)

logger = get_logger(__name__)


def _build_database_url() -> str:
    user = os.getenv("DATABASE_USER", "postgres")
    password = os.getenv("DATABASE_PASSWORD", "postgres")
    host = os.getenv("DATABASE_HOST", "localhost")
    port = os.getenv("DATABASE_PORT", "5432")
    name = os.getenv("DATABASE_NAME", "adwize")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


async def _check_snoozed(rule_id: uuid.UUID, session: AsyncSession) -> bool:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await session.execute(
        select(Alert)
        .where(
            Alert.rule_id == rule_id,
            Alert.snoozed_until.is_not(None),
            Alert.snoozed_until > now,
            Alert.resolved_at.is_(None),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def evaluate_all_rules():
    """Evaluate all active rules and dispatch webhook notifications."""
    engine = create_async_engine(_build_database_url(), echo=False)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    webhook_url = os.getenv("WEBHOOK_URL", "")

    try:
        async with async_session_factory() as session:
            result = await session.execute(select(Rule).where(Rule.is_active == True))  # noqa: E712
            rules = result.scalars().all()

            if not rules:
                logger.info("No active rules found.")
                return

            logger.info(f"Evaluating {len(rules)} rules...")

            window_start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=15)
            new_alerts: list[Alert] = []

            for rule in rules:
                try:
                    if await _check_snoozed(rule.id, session):
                        logger.debug(f"Skipping snoozed rule: {rule.name}")
                        continue

                    alert = None

                    if rule.rule_type == RuleType.FIELD_VALIDATION:
                        event_type_filter = rule.config.get("event_type")
                        source_filter = rule.config.get("source")

                        query = select(Event).where(Event.received_at >= window_start)
                        if event_type_filter:
                            query = query.where(Event.event_type == event_type_filter)
                        if source_filter:
                            query = query.where(Event.source == source_filter)
                        query = query.limit(100)

                        events_result = await session.execute(query)
                        events = events_result.scalars().all()

                        for event in events:
                            alert = await evaluate_field_validation_rule(rule, event, session)
                            if alert:
                                break

                    elif rule.rule_type == RuleType.THRESHOLD:
                        alert = await evaluate_threshold_rule(rule, session)

                    elif rule.rule_type == RuleType.VOLUME:
                        alert = await evaluate_volume_rule(rule, session)

                    if alert:
                        should_create = await check_should_create_alert(
                            rule.id,
                            alert.source,
                            alert.event_type,
                            session,
                        )
                        if not should_create:
                            logger.debug(f"Skipping {rule.name} (recent alert exists)")
                            continue

                        session.add(alert)
                        await session.commit()
                        await session.refresh(alert)
                        new_alerts.append(alert)

                        logger.info(f"Alert created for rule: {rule.name}")

                        if webhook_url:
                            try:
                                await dispatch_webhook(
                                    alert=alert,
                                    webhook_url=webhook_url,
                                    db=session,
                                    event_type="triggered",
                                    rule_name=rule.name,
                                )
                            except Exception as e:
                                logger.error(f"Failed to send webhook for {rule.name}: {e}")
                    else:
                        logger.debug(f"No alert for rule: {rule.name}")

                except Exception as e:
                    await session.rollback()
                    logger.error(f"Error evaluating rule {rule.name}: {e}")

            logger.info(f"Evaluation complete. Created {len(new_alerts)} alerts.")
    finally:
        await engine.dispose()


async def run_loop(interval_minutes: int = 5):
    logger.info(f"Starting rule evaluator (interval: {interval_minutes} minutes)")
    while True:
        try:
            logger.info("Running evaluation...")
            await evaluate_all_rules()
            logger.info(f"Waiting {interval_minutes} minutes until next run...")
            await asyncio.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in loop: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    if "--once" in sys.argv:
        logger.info("Running single evaluation (--once mode)")
        asyncio.run(evaluate_all_rules())
    else:
        interval = 5
        if len(sys.argv) > 1:
            try:
                interval = int(sys.argv[1])
            except ValueError:
                pass
        asyncio.run(run_loop(interval))
