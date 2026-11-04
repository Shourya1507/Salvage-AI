"""Demo fallback agent: realistic mock AI responses when LLM API is unavailable.

Used automatically in DEMO_MODE when the real Anthropic API key is invalid or
missing.  All responses are clearly labelled with model="demo-fallback" so
they are visually distinguishable from real Claude output.
"""
from __future__ import annotations

import json
import random
from decimal import Decimal

from app.agent.schemas import ActionType, AgentOutput
from app.db.models import Case


def _fmt_money(val: Decimal | float, currency: str = "USD") -> str:
    return f"${float(val):,.2f}"


def _demo_response_for_case(case: Case) -> AgentOutput:
    """Generate a contextual mock AI response based on the case type and evidence."""
    sub = case.subscription
    plan = sub.plan if sub else None
    subscriber = sub.subscriber if sub else None
    evidence = json.loads(case.evidence_json or "{}")

    plan_name = plan.name if plan else "Subscription Plan"
    plan_price = _fmt_money(plan.price) if plan else "$0.00"
    plan_interval = (plan.interval.lower() if plan else "month")
    subscriber_name = subscriber.name if subscriber else "the subscriber"
    mrr = _fmt_money(case.mrr_at_risk)

    if case.type == "FAILED_PAYMENT":
        days = evidence.get("days_since_suspension", 0)
        trigger = evidence.get("trigger", "status_check")
        return AgentOutput(
            diagnosis=(
                f"Subscription renewal for {plan_name} ({plan_price}/{plan_interval}) "
                f"failed. The subscription is currently suspended"
                + (f" for {days:.0f} days" if days else "")
                + ". This is likely a temporary card issue — insufficient funds, "
                "expired card, or a bank-side hold."
            ),
            reasoning=(
                f"1. The subscription was detected via {evidence.get('rule', 'R1')} rule "
                f"with trigger: {trigger}.\n"
                f"2. {subscriber_name} has {mrr}/mo at risk on the {plan_name} plan.\n"
                f"3. PayPal subscription ID: {sub.paypal_subscription_id}.\n"
                f"4. Card-related failures are typically transient — retrying the "
                f"outstanding balance is the lowest-friction recovery path.\n"
                f"5. No prior duplicate charges or disputes detected for this subscriber."
            ),
            action_type=ActionType.RETRY_PAYMENT,
            params={"retry_attempt": 1, "note": "Automated retry via Salvage AI"},
            confidence=round(random.uniform(0.82, 0.95), 2),
            customer_message=(
                f"Hi {subscriber_name},\n\n"
                f"We noticed your latest payment for {plan_name} didn't go through. "
                "This can happen if your card expired or your bank flagged the charge.\n\n"
                "We'll retry the payment shortly — no action needed on your end. "
                "If you'd like to update your payment method, you can do so in your "
                "PayPal account settings.\n\n"
                "Thanks for being a subscriber!\n"
                "— The team"
            ),
        )

    elif case.type == "STALLED_SUSPENSION":
        days_stalled = evidence.get("days_stalled", 7)
        return AgentOutput(
            diagnosis=(
                f"Subscription to {plan_name} has been suspended for {days_stalled:.0f} days "
                f"without resolution. {mrr}/mo is at risk. The subscriber may have "
                "forgotten about the suspension or lost interest."
            ),
            reasoning=(
                f"1. Detected by rule {evidence.get('rule', 'R2')}: subscription suspended "
                f"longer than the configured threshold.\n"
                f"2. Suspended since: {evidence.get('suspended_at', 'unknown')}.\n"
                f"3. Reactivating the subscription restores billing and retains the customer.\n"
                f"4. A proactive outreach message may improve reactivation success.\n"
                f"5. {subscriber_name}'s plan ({plan_name}) at {plan_price}/{plan_interval} "
                f"represents {mrr}/mo in recoverable revenue."
            ),
            action_type=ActionType.REACTIVATE_SUBSCRIPTION,
            params={"reason": "Stalled suspension recovery"},
            confidence=round(random.uniform(0.72, 0.88), 2),
            customer_message=(
                f"Hi {subscriber_name},\n\n"
                f"Your {plan_name} subscription has been paused for a while. "
                "We'd love to have you back!\n\n"
                "We're reactivating your subscription so you don't miss out. "
                "If you'd prefer to keep it paused or cancel, just let us know.\n\n"
                "Best,\n— The team"
            ),
        )

    elif case.type == "DUPLICATE_CHARGE":
        return AgentOutput(
            diagnosis=(
                f"Two charges of the same amount were detected for {subscriber_name} on "
                f"the {plan_name} plan within a short window. This may be a duplicate "
                "billing event that needs manual review for a potential refund."
            ),
            reasoning=(
                f"1. Detected by rule {evidence.get('rule', 'R3')}: same amount, same "
                f"subscriber, different transaction IDs within the duplicate window.\n"
                f"2. Plan: {plan_name} at {plan_price}/{plan_interval}.\n"
                f"3. Automatic refunds are not safe without human verification — flagging "
                f"for manual review is the appropriate action.\n"
                f"4. {mrr}/mo at risk if the subscriber disputes and churns."
            ),
            action_type=ActionType.REVIEW_DUPLICATE_FOR_REFUND,
            params={"review_note": "Potential duplicate charge detected by R3 rule"},
            confidence=round(random.uniform(0.75, 0.90), 2),
            customer_message=(
                f"Hi {subscriber_name},\n\n"
                f"We noticed a potential duplicate charge on your {plan_name} subscription. "
                "Our team is reviewing it now.\n\n"
                "If a duplicate is confirmed, we'll process a refund automatically. "
                "No action needed on your end.\n\n"
                "Thanks for your patience!\n— The team"
            ),
        )

    elif case.type == "PRICE_FALLOUT":
        failure_rate = evidence.get("failure_rate", 0)
        total_subs = evidence.get("total_subs", 0)
        cancelled = evidence.get("cancelled_or_failed", 0)
        return AgentOutput(
            diagnosis=(
                f"After a price change on the {plan_name} plan, {cancelled} of "
                f"{total_subs} subscribers ({failure_rate*100:.0f}%) have cancelled or "
                f"failed to renew. This cohort represents {mrr}/mo in at-risk revenue."
            ),
            reasoning=(
                f"1. Detected by rule {evidence.get('rule', 'R4')}: cohort analysis "
                f"around plan price change.\n"
                f"2. Plan: {plan_name}, current price: {plan_price}/{plan_interval}.\n"
                f"3. Failure rate: {failure_rate*100:.0f}% — above the acceptable threshold.\n"
                f"4. A targeted win-back offer with grandfathered or discounted pricing "
                f"may recover a portion of churned subscribers.\n"
                f"5. This is advisory — no automated PayPal action is taken."
            ),
            action_type=ActionType.WIN_BACK_OFFER,
            params={
                "offer_type": "discount",
                "suggested_discount_pct": 20,
                "cohort_size": total_subs,
            },
            confidence=round(random.uniform(0.65, 0.82), 2),
            customer_message=(
                f"Hi {subscriber_name},\n\n"
                f"We recently updated the pricing for {plan_name}. As a valued subscriber, "
                "we'd like to offer you a special rate to continue your subscription.\n\n"
                "Reply to this message or contact our support team to learn about your "
                "personalized offer.\n\n"
                "We appreciate your loyalty!\n— The team"
            ),
        )

    elif case.type == "AT_RISK":
        churn_score = evidence.get("churn_score", evidence.get("score", 0.8))
        return AgentOutput(
            diagnosis=(
                f"{subscriber_name} on {plan_name} ({plan_price}/{plan_interval}) has a "
                f"high churn risk score of {churn_score:.2f}. Proactive outreach with a "
                f"dunning message may help retain this {mrr}/mo subscriber."
            ),
            reasoning=(
                f"1. Detected by rule {evidence.get('rule', 'R5')}: churn probability "
                f"model scored this subscriber at {churn_score:.2f} (threshold: 0.70).\n"
                f"2. This is an experimental ML-based prediction.\n"
                f"3. A proactive dunning or retention message can reduce churn.\n"
                f"4. No PayPal API mutation is needed — this is an advisory action.\n"
                f"5. Plan: {plan_name} at {plan_price}/{plan_interval}."
            ),
            action_type=ActionType.SEND_DUNNING_MESSAGE,
            params={"message_type": "retention_outreach"},
            confidence=round(random.uniform(0.60, 0.78), 2),
            customer_message=(
                f"Hi {subscriber_name},\n\n"
                f"We just wanted to check in about your {plan_name} subscription. "
                "Is everything working well for you?\n\n"
                "If there's anything we can do to improve your experience, please "
                "don't hesitate to reach out. We value your subscription!\n\n"
                "Best,\n— The team"
            ),
        )

    # Fallback for any unknown case type
    return AgentOutput(
        diagnosis=f"Revenue leak case of type {case.type} detected for {plan_name}. Manual review recommended.",
        reasoning=f"1. Case type: {case.type}.\n2. MRR at risk: {mrr}.\n3. Further investigation needed.",
        action_type=ActionType.NO_ACTION,
        params={},
        confidence=0.50,
        customer_message="",
    )

