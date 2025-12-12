from src.shared.models.enums import OrderStatus

class TripStateMachine:
    ALLOWED_TRANSITIONS = {
        OrderStatus.DRAFT: [OrderStatus.NEW, OrderStatus.CANCELLED],
        OrderStatus.NEW: [OrderStatus.SEARCHING, OrderStatus.CANCELLED],
        OrderStatus.SEARCHING: [OrderStatus.ON_WAY, OrderStatus.CANCELLED],
        OrderStatus.ON_WAY: [OrderStatus.ARRIVED, OrderStatus.CANCELLED],
        OrderStatus.ARRIVED: [OrderStatus.STARTED, OrderStatus.CANCELLED],
        OrderStatus.STARTED: [OrderStatus.COMPLETED, OrderStatus.CANCELLED],
        OrderStatus.COMPLETED: [],
        OrderStatus.CANCELLED: []
    }

    @staticmethod
    def can_transition(current_status: str, new_status: str) -> bool:
        try:
            curr = OrderStatus(current_status)
            new = OrderStatus(new_status)
            return new in TripStateMachine.ALLOWED_TRANSITIONS.get(curr, [])
        except ValueError:
            return False
