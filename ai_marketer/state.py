from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class UserState:
    stage: str = "idle"
    diagnostic_step: int = 0
    answers: Dict[str, Any] = field(default_factory=dict)
    competitors: List[str] = field(default_factory=list)
    sales_df_summary: Optional[str] = None
    last_report_text: Optional[str] = None
    last_report_sections: Dict[str, str] = field(default_factory=dict)
    chat_mode: bool = False
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    pending_payment_service: Optional[str] = None


STATE: Dict[int, UserState] = {}


def get_state(user_id: int) -> UserState:
    if user_id not in STATE:
        STATE[user_id] = UserState()
    return STATE[user_id]


def reset_state(user_id: int):
    STATE[user_id] = UserState()
