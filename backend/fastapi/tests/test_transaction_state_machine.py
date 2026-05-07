from app.core.payments.transaction_state_machine import InvalidStateTransitionError, TransactionState, TransactionStateMachine


def test_valid_transition_pending_to_processing():
    TransactionStateMachine.validate_transition(TransactionState.PENDING, TransactionState.PROCESSING)


def test_invalid_transition_success_to_pending():
    try:
        TransactionStateMachine.validate_transition(TransactionState.SUCCESS, TransactionState.PENDING)
        assert False, "expected InvalidStateTransitionError"
    except InvalidStateTransitionError:
        assert True
