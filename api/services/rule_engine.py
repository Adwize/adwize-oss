import ast
import operator as op
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.alert import Alert, AlertSeverity
from api.models.event import Event
from api.models.rule import Rule

_SAFE_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod,
    ast.USub: op.neg,
}


def _safe_eval_expression(expression: str, variables: dict[str, float]) -> float:
    """Safely evaluate a simple arithmetic expression using AST parsing."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {e}") from e

    def _eval_node(node: ast.expr) -> float:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise ValueError(f"Unknown variable '{node.id}'")
            return float(variables[node.id])
        if isinstance(node, ast.BinOp):
            op_func = _SAFE_OPERATORS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            return op_func(left, right)
        if isinstance(node, ast.UnaryOp):
            op_func = _SAFE_OPERATORS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op_func(_eval_node(node.operand))
        raise ValueError(f"Disallowed expression element: {type(node).__name__}")

    return _eval_node(tree)


def _evaluate_numeric_validation(validation: dict, event_data: dict) -> tuple[bool, str | None]:
    """Evaluate a single numeric validation."""
    try:
        comparison_operator = validation["operator"]

        if validation.get("expression"):
            allowed_names = {k: v for k, v in event_data.items() if isinstance(v, (int, float))}
            try:
                left_value = _safe_eval_expression(validation["expression"], allowed_names)
            except (ValueError, ZeroDivisionError) as e:
                return (
                    False,
                    f"Failed to evaluate expression '{validation['expression']}': {str(e)}",
                )
        else:
            field_name = validation["left_field"]
            if field_name not in event_data:
                return False, f"Field '{field_name}' not found"
            left_value = event_data[field_name]

        if validation.get("threshold") is not None:
            right_value = validation["threshold"]
        else:
            field_name = validation["right_field"]
            if field_name not in event_data:
                return False, f"Field '{field_name}' not found"
            right_value = event_data[field_name]

        try:
            left_value = float(left_value)
            right_value = float(right_value)
        except (TypeError, ValueError):
            return (
                False,
                f"Non-numeric values: {left_value} {comparison_operator} {right_value}",
            )

        comparison_result = False
        if comparison_operator == "<":
            comparison_result = left_value < right_value
        elif comparison_operator == "<=":
            comparison_result = left_value <= right_value
        elif comparison_operator == ">":
            comparison_result = left_value > right_value
        elif comparison_operator == ">=":
            comparison_result = left_value >= right_value
        elif comparison_operator == "==":
            comparison_result = left_value == right_value
        elif comparison_operator == "!=":
            comparison_result = left_value != right_value

        if not comparison_result:
            desc = validation.get("description", "")
            if validation.get("expression"):
                error = f"{validation['expression']} ({left_value}) {comparison_operator} {right_value} failed"
            elif validation.get("right_field"):
                error = f"{validation['left_field']} ({left_value}) {comparison_operator} {validation['right_field']} ({right_value}) failed"
            else:
                error = f"{validation['left_field']} ({left_value}) {comparison_operator} {right_value} failed"
            if desc:
                error = f"{error} - {desc}"
            return False, error

        return True, None

    except Exception as e:
        return False, f"Validation error: {str(e)}"


async def evaluate_field_validation_rule(
    rule: Rule, event: Event, db: AsyncSession
) -> Alert | None:
    """Evaluate a field validation rule against a single event."""
    config = rule.config

    if config.get("source") and event.source != config["source"]:
        return None
    if config.get("event_type") and event.event_type != config["event_type"]:
        return None

    violations = []

    required_fields = config.get("required_fields", [])
    missing_fields = [
        f for f in required_fields if f not in event.event_data or event.event_data[f] is None
    ]
    if missing_fields:
        violations.append(f"Missing required fields: {', '.join(missing_fields)}")

    allowed_values = config.get("allowed_values", {})
    invalid_values = {}
    for field, allowed_list in allowed_values.items():
        if field in event.event_data:
            actual_value = event.event_data[field]
            if actual_value is not None and str(actual_value) not in [str(v) for v in allowed_list]:
                invalid_values[field] = {"actual": actual_value, "allowed": allowed_list}
                violations.append(
                    f"Field '{field}' has invalid value '{actual_value}' "
                    f"(allowed: {', '.join(map(str, allowed_list))})"
                )

    numeric_validations = config.get("numeric_validations", [])
    for validation in numeric_validations:
        is_valid, error = _evaluate_numeric_validation(validation, event.event_data)
        if not is_valid:
            violations.append(f"Numeric validation failed: {error}")

    if not violations:
        return None

    severity = AlertSeverity(config.get("severity", "warning"))
    message = f"Field validation failed for {event.event_type}: {'; '.join(violations)}"

    return Alert(
        id=uuid.uuid4(),
        rule_id=rule.id,
        source=event.source,
        event_type=event.event_type,
        severity=severity,
        message=message,
        event_count=1,
        context={
            "missing_fields": missing_fields if missing_fields else None,
            "invalid_values": invalid_values if invalid_values else None,
            "event_id": str(event.id),
        },
    )


async def evaluate_threshold_rule(rule: Rule, db: AsyncSession) -> Alert | None:
    """Evaluate a threshold rule. Counts events in a time window."""
    config = rule.config
    window_minutes = config.get("window_minutes", 5)
    min_events = config.get("min_events", 1)
    threshold_value = config["value"]
    comparison_operator = config["operator"]

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window_start = now - timedelta(minutes=window_minutes)

    query = select(func.count(Event.id)).where(Event.received_at >= window_start)

    if config.get("source"):
        query = query.where(Event.source == config["source"])
    if config.get("event_type"):
        query = query.where(Event.event_type == config["event_type"])

    result = await db.execute(query)
    event_count = result.scalar_one()

    if comparison_operator not in ("<", "<=") and event_count < min_events:
        return None

    threshold_exceeded = False
    if comparison_operator == ">":
        threshold_exceeded = event_count > threshold_value
    elif comparison_operator == "<":
        threshold_exceeded = event_count < threshold_value
    elif comparison_operator == ">=":
        threshold_exceeded = event_count >= threshold_value
    elif comparison_operator == "<=":
        threshold_exceeded = event_count <= threshold_value
    elif comparison_operator == "==":
        threshold_exceeded = event_count == threshold_value

    if not threshold_exceeded:
        return None

    severity = AlertSeverity(config.get("severity", "warning"))

    return Alert(
        id=uuid.uuid4(),
        rule_id=rule.id,
        source=config.get("source"),
        event_type=config.get("event_type"),
        severity=severity,
        message=f"Threshold exceeded: {event_count} events {comparison_operator} {threshold_value} in {window_minutes} minutes",
        event_count=event_count,
        context={
            "threshold": threshold_value,
            "actual_count": event_count,
            "operator": comparison_operator,
            "window_minutes": window_minutes,
        },
    )


async def evaluate_volume_rule(rule: Rule, db: AsyncSession) -> Alert | None:
    """Evaluate a volume rule. Compares current volume to baseline."""
    config = rule.config
    current_window_minutes = config.get("current_window_minutes", 60)
    comparison_window_hours = config.get("comparison_window_hours", 24)
    threshold_percent = config["threshold_percent"]
    min_baseline_events = config.get("min_baseline_events", 10)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    current_start = now - timedelta(minutes=current_window_minutes)
    baseline_end = now - timedelta(hours=comparison_window_hours)
    baseline_start = baseline_end - timedelta(minutes=current_window_minutes)

    base_query = select(func.count(Event.id))

    if config.get("source"):
        base_query = base_query.where(Event.source == config["source"])
    if config.get("event_type"):
        base_query = base_query.where(Event.event_type == config["event_type"])

    current_query = base_query.where(Event.received_at >= current_start)
    current_result = await db.execute(current_query)
    current_count = current_result.scalar_one()

    baseline_query = base_query.where(
        Event.received_at >= baseline_start, Event.received_at < baseline_end
    )
    baseline_result = await db.execute(baseline_query)
    baseline_count = baseline_result.scalar_one()

    if baseline_count < min_baseline_events:
        return None
    if baseline_count == 0:
        return None

    percent_change = ((current_count - baseline_count) / baseline_count) * 100

    if threshold_percent < 0:
        threshold_exceeded = percent_change <= threshold_percent
    else:
        threshold_exceeded = percent_change >= threshold_percent

    if not threshold_exceeded:
        return None

    severity = AlertSeverity(config.get("severity", "critical"))
    change_direction = "dropped" if percent_change < 0 else "increased"

    return Alert(
        id=uuid.uuid4(),
        rule_id=rule.id,
        source=config.get("source"),
        event_type=config.get("event_type"),
        severity=severity,
        message=f"Volume {change_direction} by {abs(percent_change):.1f}%: {current_count} events (baseline: {baseline_count})",
        event_count=current_count,
        context={
            "current_count": current_count,
            "baseline_count": baseline_count,
            "percent_change": round(percent_change, 2),
            "threshold_percent": threshold_percent,
        },
    )


async def check_should_create_alert(
    rule_id: uuid.UUID,
    source: str | None,
    event_type: str | None,
    db: AsyncSession,
) -> bool:
    """Check if we should create a new alert (debouncing).
    Prevents duplicate alerts for the same (rule, source, event_type) within 60 minutes.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    recent_threshold = now - timedelta(minutes=60)

    query = select(Alert).where(
        Alert.rule_id == rule_id,
        Alert.triggered_at >= recent_threshold,
    )

    if source is not None:
        query = query.where(Alert.source == source)
    else:
        query = query.where(Alert.source.is_(None))

    if event_type is not None:
        query = query.where(Alert.event_type == event_type)
    else:
        query = query.where(Alert.event_type.is_(None))

    query = query.order_by(Alert.triggered_at.desc()).limit(1)

    result = await db.execute(query)
    existing_alert = result.scalar_one_or_none()

    return existing_alert is None
