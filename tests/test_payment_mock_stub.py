import pytest
from unittest.mock import Mock
from services.payment_service import PaymentGateway
from services.library_services import pay_late_fees, refund_late_fee_payment


# ============================
# Tests for pay_late_fees()
# Stub DB functions to avoid real database state.
# Mock PaymentGateway to verify interaction (assert_called, assert_not_called).
# Each test covers one required branch: success, decline, invalid patron ID,
# ============================

def test_pay_late_fees_success(mocker):
    """Successful late fee payment."""
    
    # Stub DB helpers
    mocker.patch("services.library_services.get_book_by_id",
                 return_value={"id": 42, "title": "Book X"})
    mocker.patch("services.library_services.calculate_late_fee_for_book",
                 return_value={"fee_amount": 7.50})

    # Mock external gateway
    gateway = Mock(spec=PaymentGateway)
    gateway.process_payment.return_value = (True, "txn_123", "OK")

    ok, msg, txn = pay_late_fees("123456", 42, gateway)

    gateway.process_payment.assert_called_once_with(
        patron_id="123456",
        amount=7.50,
        description="Late fees for 'Book X'"
    )

    assert ok is True
    assert txn == "txn_123"


def test_pay_late_fees_declined(mocker):
    """Gateway declines payment."""
    
    mocker.patch("services.library_services.get_book_by_id",
                 return_value={"id": 5, "title": "Y"})
    mocker.patch("services.library_services.calculate_late_fee_for_book",
                 return_value={"fee_amount": 10.0})

    gateway = Mock(spec=PaymentGateway)
    gateway.process_payment.return_value = (False, "", "declined")

    ok, msg, txn = pay_late_fees("123456", 5, gateway)

    gateway.process_payment.assert_called_once()
    assert ok is False
    assert txn is None


def test_pay_late_fees_invalid_patron_id(mocker):
    """Invalid patron ID → mock NOT called."""
    
    mocker.patch("services.library_services.get_book_by_id",
                 return_value={"id": 1, "title": "A"})
    mocker.patch("services.library_services.calculate_late_fee_for_book",
                 return_value={"fee_amount": 5.0})

    gateway = Mock(spec=PaymentGateway)

    ok, msg, txn = pay_late_fees("12", 1, gateway)

    gateway.process_payment.assert_not_called()
    assert ok is False


def test_pay_late_fees_book_not_found(mocker):
    """Book missing → gateway not called."""
    
    mocker.patch("services.library_services.get_book_by_id",
                 return_value=None)
    mocker.patch("services.library_services.calculate_late_fee_for_book",
                 return_value={"fee_amount": 5.0})

    gateway = Mock(spec=PaymentGateway)

    ok, msg, txn = pay_late_fees("123456", 1, gateway)

    gateway.process_payment.assert_not_called()
    assert ok is False


def test_pay_late_fees_zero_fee(mocker):
    """Zero fee → skip gateway."""
    
    mocker.patch("services.library_services.get_book_by_id",
                 return_value={"id": 7, "title": "Z"})
    mocker.patch("services.library_services.calculate_late_fee_for_book",
                 return_value={"fee_amount": 0.0})

    gateway = Mock(spec=PaymentGateway)

    ok, msg, txn = pay_late_fees("123456", 7, gateway)

    gateway.process_payment.assert_not_called()
    assert ok is False
    assert txn is None


def test_pay_late_fees_gateway_exception(mocker):
    """Gateway error → caught by try/except."""
    
    mocker.patch("services.library_services.get_book_by_id",
                 return_value={"id": 77, "title": "Exc"})
    mocker.patch("services.library_services.calculate_late_fee_for_book",
                 return_value={"fee_amount": 6.0})

    gateway = Mock(spec=PaymentGateway)
    gateway.process_payment.side_effect = Exception("Network down")

    ok, msg, txn = pay_late_fees("123456", 77, gateway)

    gateway.process_payment.assert_called_once()
    assert ok is False
    assert "Network down" in msg


# ============================
# Tests for refund_late_fee_payment()
# No DB stubs needed because the function does not touch the database.
# Mock PaymentGateway.refund_payment to verify correct parameters and ensure no call is made when inputs are invalid.
# Covers all required branches: success, invalid tx, zero amount,
# negative amount, >$15 amount, gateway-decline, and exception.
# ============================

def test_refund_success():
    """Successful refund."""
    
    gateway = Mock(spec=PaymentGateway)
    gateway.refund_payment.return_value = (True, "Refund OK")

    ok, msg = refund_late_fee_payment("txn_1", 5.0, gateway)

    gateway.refund_payment.assert_called_once_with("txn_1", 5.0)
    assert ok is True


def test_refund_invalid_tx():
    """Reject invalid transaction ID."""
    
    gateway = Mock(spec=PaymentGateway)

    ok, msg = refund_late_fee_payment("", 5.0, gateway)

    gateway.refund_payment.assert_not_called()
    assert ok is False


def test_refund_amount_zero():
    """Refund amount cannot be 0."""
    
    gateway = Mock(spec=PaymentGateway)

    ok, msg = refund_late_fee_payment("txn_1", 0, gateway)

    gateway.refund_payment.assert_not_called()
    assert ok is False


def test_refund_amount_negative():
    """Refund cannot be negative."""
    
    gateway = Mock(spec=PaymentGateway)

    ok, msg = refund_late_fee_payment("txn_1", -5, gateway)

    gateway.refund_payment.assert_not_called()
    assert ok is False


def test_refund_amount_exceeds_cap():
    """Refund cannot exceed $15."""
    
    gateway = Mock(spec=PaymentGateway)

    ok, msg = refund_late_fee_payment("txn_1", 20.0, gateway)

    gateway.refund_payment.assert_not_called()
    assert ok is False


def test_refund_gateway_declined():
    """Gateway rejects refund."""
    
    gateway = Mock(spec=PaymentGateway)
    gateway.refund_payment.return_value = (False, "declined")

    ok, msg = refund_late_fee_payment("txn_1", 5.0, gateway)

    gateway.refund_payment.assert_called_once()
    assert ok is False


def test_refund_gateway_exception():
    """Gateway exception handled."""
    
    gateway = Mock(spec=PaymentGateway)
    gateway.refund_payment.side_effect = Exception("Timeout")

    ok, msg = refund_late_fee_payment("txn_1", 5.0, gateway)

    gateway.refund_payment.assert_called_once()
    assert ok is False
    assert "Timeout" in msg

# ============================
# Additional coverage tests for PaymentGateway
# ============================
"""
Note: I added a small set of direct unit tests for PaymentGateway to increase overall project coverage. 
The assignment requires achieving at least 80% statement and branch coverage across the entire services folder, 
not just the two new functions we mocked. Since PaymentGateway contains several validation branches that are not 
executed when it is mocked (as required for pay_late_fees and refund_late_fee_payment), I wrote lightweight 
coverage tests to test those internal branches. This follows the instructions to use the HTML report to 
identify uncovered lines and “iteratively write tests targeting uncovered code until reaching 80%+ overall 
project coverage.”
"""

from services.payment_service import PaymentGateway
import time


def test_process_payment_success(mocker):
    """Valid payment should succeed."""
    mocker.patch("time.sleep", return_value=None)  # skip delay
    gateway = PaymentGateway()

    ok, txn, msg = gateway.process_payment("123456", 20.0, "Test")

    assert ok is True
    assert "txn_123456" in txn
    assert "processed successfully" in msg


def test_process_payment_invalid_amount(mocker):
    """Amount <= 0 should fail."""
    mocker.patch("time.sleep", return_value=None)
    gateway = PaymentGateway()

    ok, txn, msg = gateway.process_payment("123456", 0, "Bad")

    assert ok is False
    assert txn == ""
    assert "Invalid amount" in msg


def test_process_payment_amount_too_high(mocker):
    """Amount > 1000 should decline."""
    mocker.patch("time.sleep", return_value=None)
    gateway = PaymentGateway()

    ok, txn, msg = gateway.process_payment("123456", 1500, "Huge")

    assert ok is False
    assert txn == ""
    assert "exceeds limit" in msg


def test_process_payment_invalid_patron_id(mocker):
    """Invalid patron ID format."""
    mocker.patch("time.sleep", return_value=None)
    gateway = PaymentGateway()

    ok, txn, msg = gateway.process_payment("12", 10.0, "Test")

    assert ok is False
    assert txn == ""
    assert "Invalid patron ID" in msg


def test_refund_payment_success(mocker):
    """Successful refund."""
    mocker.patch("time.sleep", return_value=None)
    gateway = PaymentGateway()

    ok, msg = gateway.refund_payment("txn_123456_99999", 5.0)

    assert ok is True
    assert "Refund of $5.00 processed successfully" in msg


def test_refund_payment_invalid_tx(mocker):
    """Refund fails for invalid transaction ID."""
    mocker.patch("time.sleep", return_value=None)
    gateway = PaymentGateway()

    ok, msg = gateway.refund_payment("bad", 5.0)

    assert ok is False
    assert "Invalid transaction ID" in msg


def test_refund_payment_invalid_amount(mocker):
    """Refund amount <= 0 fails."""
    mocker.patch("time.sleep", return_value=None)
    gateway = PaymentGateway()

    ok, msg = gateway.refund_payment("txn_abc", -1)

    assert ok is False
    assert "Invalid refund amount" in msg


def test_verify_payment_status_success(mocker):
    """verify_payment_status returns completed."""
    mocker.patch("time.sleep", return_value=None)
    gateway = PaymentGateway()

    result = gateway.verify_payment_status("txn_001122")

    assert result["status"] == "completed"
    assert result["transaction_id"] == "txn_001122"


def test_verify_payment_status_invalid(mocker):
    """Invalid transaction ID should return not_found."""
    mocker.patch("time.sleep", return_value=None)
    gateway = PaymentGateway()

    result = gateway.verify_payment_status("bad")

    assert result["status"] == "not_found"

