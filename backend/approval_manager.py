"""Compatibility alias — the approval gate lives in backend/approval.py."""
from backend.approval import *  # noqa: F401,F403
from backend.approval import ApprovalRequired, list_pending, request, require_approved, resolve  # noqa: F401
