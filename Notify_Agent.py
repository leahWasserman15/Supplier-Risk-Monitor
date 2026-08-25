"""Notify agent for supplier risk change alerts."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from agents import Agent, Runner
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from Notify_Utils import build_changes
from Supplier_Database_Utils import CompanyBook
import llm_config  # noqa: F401 — configures LiteLLM when USE_LITELLM=True

load_dotenv(override=True)

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))

NOTIFY_AGENT_INSTRUCTIONS = """
You write supplier risk alerts.

You will be given a markdown report where each vendor block includes:
- Status: NEW RISK or CLEARED
- Transition: old -> new
- Risk level
- Reason
- Source
- Research summary

Return structured output with two fields:
- header: a single summary line, e.g. "1 new risks, 1 cleared"
- body: the vendor detail lines only (no header line)

Body format — one line per vendor:
NEW RISK - <vendor>: Level <risk level>. <one concise sentence summarizing why>
CLEARED - <vendor>: Level <risk level>. <one concise sentence summarizing why>

Rules:
- Use only provided fields. Do not infer from missing context.
- Prefer the Reason field; use the Research summary only to compress and clarify it.
- Do not search. Do not add facts, advice, or recommendations.
- Keep each vendor line in body to one sentence.
- List NEW RISK rows first, then CLEARED rows in body.
- Put the counts summary in header only, not in body.
"""


class NotifyAlert(BaseModel):
    header: str = Field(
        description='Summary counts line, e.g. "1 new risks, 1 cleared".'
    )
    body: str = Field(
        description=(
            "Vendor detail lines only, one per line. "
            "NEW RISK rows first, then CLEARED rows."
        )
    )

    @property
    def full_text(self) -> str:
        """Header and body combined for display or plain-text email."""
        if self.body.strip():
            return f"{self.header}\n\n{self.body}"
        return self.header


notify_agent = Agent(
    name="notify_agent",
    instructions=NOTIFY_AGENT_INSTRUCTIONS,
    model="gpt-5.6-terra",
    output_type=NotifyAlert,
)


def send_email(subject: str, text_body: str) -> None:
    """Send a plain-text alert email using SMTP settings from .env."""
    if not EMAIL_ADDRESS or not EMAIL_SMTP_SERVER or not EMAIL_APP_PASSWORD:
        raise ValueError(
            "Email not configured. Set EMAIL_ADDRESS, EMAIL_SMTP_SERVER, "
            "and EMAIL_APP_PASSWORD in .env."
        )

    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS
    msg["Subject"] = subject
    msg.set_content(text_body)

    with smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.send_message(msg)


async def notify_changes(changes: str) -> NotifyAlert:
    """Return structured supplier risk alert from change payload."""
    result = await Runner.run(notify_agent, changes)
    return result.final_output


async def notify_from_run_start(
    run_start: str,
    book: CompanyBook | None = None,
    *,
    send: bool = True,
) -> NotifyAlert:
    """Build change payload from run_start, optionally email, return alert."""
    active_book = book or CompanyBook()
    flagged = active_book.get_risk_changes(run_start)
    if flagged.empty:
        print("No notification — no risk changes to notify.")
        return NotifyAlert(header="No risk changes to notify.", body="")

    alert = await notify_changes(build_changes(flagged))
    print(f"Notification created: {alert.header}")
    if send:
        send_email(alert.header, alert.body)
        print(f"Email sent to {EMAIL_ADDRESS}")
    return alert
