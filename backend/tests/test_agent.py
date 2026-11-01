"""Tests for agent output schema validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.schemas import ActionType, AgentOutput


class TestAgentOutputSchema:
    def test_valid_output_parses(self):
        data = {
            "diagnosis": "Payment failed due to insufficient funds",
            "reasoning": "The last 3 payments all failed with status FAILED",
            "action_type": "RETRY_PAYMENT",
            "params": {"note": "Retry from Salvage AI"},
            "customer_message": "We noticed an issue with your payment. Please update your payment method.",
            "confidence": 0.87,
        }
        output = AgentOutput.model_validate(data)
        assert output.action_type == ActionType.RETRY_PAYMENT
        assert output.confidence == 0.87

    def test_all_action_types_accepted(self):
        valid_types = [
            "RETRY_PAYMENT",
            "REACTIVATE_SUBSCRIPTION",
            "SUSPEND_SUBSCRIPTION",
            "CANCEL_SUBSCRIPTION",
            "SEND_DUNNING_MESSAGE",
            "WIN_BACK_OFFER",
            "REVIEW_DUPLICATE_FOR_REFUND",
            "NO_ACTION",
        ]
        for action_type in valid_types:
            data = {
                "diagnosis": "Test",
                "reasoning": "Test reasoning",
                "action_type": action_type,
                "params": {},
                "customer_message": "",
                "confidence": 0.5,
            }
            output = AgentOutput.model_validate(data)
            assert output.action_type.value == action_type

    def test_invalid_action_type_rejected(self):
        data = {
            "diagnosis": "Test",
            "reasoning": "Test reasoning",
            "action_type": "DELETE_ACCOUNT",  # Not allowed
            "params": {},
            "customer_message": "",
            "confidence": 0.5,
        }
        with pytest.raises(ValidationError):
            AgentOutput.model_validate(data)

    def test_confidence_out_of_range_rejected(self):
        data = {
            "diagnosis": "Test",
            "reasoning": "Test reasoning",
            "action_type": "NO_ACTION",
            "params": {},
            "customer_message": "",
            "confidence": 1.5,  # > 1.0
        }
        with pytest.raises(ValidationError):
            AgentOutput.model_validate(data)

    def test_negative_confidence_rejected(self):
        data = {
            "diagnosis": "Test",
            "reasoning": "Test reasoning",
            "action_type": "NO_ACTION",
            "params": {},
            "customer_message": "",
            "confidence": -0.1,
        }
        with pytest.raises(ValidationError):
            AgentOutput.model_validate(data)

    def test_empty_diagnosis_rejected(self):
        data = {
            "diagnosis": "",
            "reasoning": "Test reasoning",
            "action_type": "NO_ACTION",
            "params": {},
            "customer_message": "",
            "confidence": 0.5,
        }
        with pytest.raises(ValidationError):
            AgentOutput.model_validate(data)

    def test_missing_required_fields_rejected(self):
        data = {
            "diagnosis": "Test",
            # missing reasoning, action_type, confidence
        }
        with pytest.raises(ValidationError):
            AgentOutput.model_validate(data)

    def test_whitespace_stripped_from_diagnosis(self):
        data = {
            "diagnosis": "  Payment failed  ",
            "reasoning": "  Evidence shows failure  ",
            "action_type": "RETRY_PAYMENT",
            "params": {},
            "customer_message": "  Please update your payment method  ",
            "confidence": 0.9,
        }
        output = AgentOutput.model_validate(data)
        assert output.diagnosis == "Payment failed"
        assert output.reasoning == "Evidence shows failure"
        assert output.customer_message == "Please update your payment method"

    def test_params_can_be_empty_dict(self):
        data = {
            "diagnosis": "At-risk subscriber",
            "reasoning": "Churn score is 0.85",
            "action_type": "WIN_BACK_OFFER",
            "params": {},
            "customer_message": "We miss you!",
            "confidence": 0.75,
        }
        output = AgentOutput.model_validate(data)
        assert output.params == {}

    def test_params_can_have_arbitrary_data(self):
        data = {
            "diagnosis": "Duplicate charge",
            "reasoning": "Two identical transactions found",
            "action_type": "REVIEW_DUPLICATE_FOR_REFUND",
            "params": {"txn_ids": ["TXN-A", "TXN-B"], "amount": "29.99"},
            "customer_message": "We are reviewing the duplicate charge",
            "confidence": 0.95,
        }
        output = AgentOutput.model_validate(data)
        assert output.params["txn_ids"] == ["TXN-A", "TXN-B"]

    def test_confidence_boundary_values(self):
        for conf in [0.0, 1.0]:
            data = {
                "diagnosis": "Test",
                "reasoning": "Test",
                "action_type": "NO_ACTION",
                "params": {},
                "customer_message": "",
                "confidence": conf,
            }
            output = AgentOutput.model_validate(data)
            assert output.confidence == conf

