"""Connector contract for Flo's future least-privilege Google Workspace access.

Scaffold only (see ``.flo/docs/08_GOOGLE_WORKSPACE_INTEGRATION.md``). No OAuth,
no credentials, no network. It fixes the *shape* every real connector must
have so the policy gate, approvals and audit apply uniformly:

* capability-level methods, never a generic "run any Google API call";
* read/search/draft methods take plain arguments;
* side-effecting methods take an :class:`ActionProposal` **and** an
  :class:`Approval` and are only ever invoked through :class:`PolicyGate`;
* raw refresh tokens never cross this interface — a connector is constructed
  by a trusted host component (Electron main / backend broker) that owns them.

The tool names in ``policy._TOOL_CAPABILITIES`` (``flo_email_send`` …) are the
model-facing names a plugin will register for these methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .approvals import Approval
from .gate import ExecutionResult, PolicyGate
from .policy import ActionProposal, classify_tool_call


@dataclass(frozen=True)
class MailRef:
    message_id: str
    thread_id: Optional[str] = None
    subject: str = ""
    sender: str = ""
    received_at: Optional[str] = None
    snippet: str = ""  # untrusted content; never authority


@dataclass(frozen=True)
class FileRef:
    file_id: str
    name: str = ""
    mime_type: str = ""
    modified_at: Optional[str] = None
    web_link: Optional[str] = None


@dataclass(frozen=True)
class DraftProposal:
    to: List[str]
    subject: str
    body: str
    cc: List[str] = field(default_factory=list)
    attachments: List[FileRef] = field(default_factory=list)
    loan_ref: Optional[str] = None


class FloGoogleConnector(Protocol):
    """What a real connector implements. Reads are plain; writes are gated."""

    # -- Stage 1: read + draft (ALLOW) ----------------------------------
    def search_mail(self, query: str, *, max_results: int = 20) -> List[MailRef]: ...
    def read_mail(self, message_id: str) -> Dict[str, Any]: ...
    def create_draft(self, draft: DraftProposal) -> Dict[str, Any]: ...
    def search_drive(self, query: str, *, max_results: int = 20) -> List[FileRef]: ...
    def read_drive_file(self, file_id: str) -> Dict[str, Any]: ...

    # -- Stage 2+: side effects (CONFIRM via PolicyGate) -----------------
    def send_approved_draft(self, proposal: ActionProposal, approval: Approval) -> Dict[str, Any]: ...
    def upload_approved_file(self, proposal: ActionProposal, approval: Approval) -> Dict[str, Any]: ...


class GatedConnectorActions:
    """The only way model-facing code may reach a connector's side effects.

    Builds the proposal from structured arguments, runs it through the gate,
    and hands the connector method the proposal plus the verified approval.
    """

    def __init__(self, connector: FloGoogleConnector, gate: PolicyGate) -> None:
        self.connector = connector
        self.gate = gate

    def propose_send(self, draft: DraftProposal) -> ActionProposal:
        args = {
            "to": list(draft.to),
            "cc": list(draft.cc),
            "subject": draft.subject,
            "body": draft.body,
            "attachments": [a.file_id for a in draft.attachments],
        }
        return classify_tool_call("flo_email_send", args, table=self.gate.table, loan_ref=draft.loan_ref)

    def send(self, proposal: ActionProposal, approval: Optional[Approval] = None, *, session_id: Optional[str] = None) -> ExecutionResult:
        def _execute(p: ActionProposal) -> Any:
            assert approval is not None  # gate only calls executor with a verified approval for CONFIRM
            return self.connector.send_approved_draft(p, approval)

        return self.gate.execute(proposal, _execute, approval=approval, session_id=session_id)

    def propose_upload(self, local_path: str, *, parent_id: Optional[str] = None, loan_ref: Optional[str] = None) -> ActionProposal:
        return classify_tool_call(
            "flo_drive_upload", {"path": local_path, "parent": parent_id}, table=self.gate.table, loan_ref=loan_ref
        )

    def upload(self, proposal: ActionProposal, approval: Optional[Approval] = None, *, session_id: Optional[str] = None) -> ExecutionResult:
        def _execute(p: ActionProposal) -> Any:
            assert approval is not None
            return self.connector.upload_approved_file(p, approval)

        return self.gate.execute(proposal, _execute, approval=approval, session_id=session_id)
