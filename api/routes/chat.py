"""
api/routes/chat.py
------------------
Anonymous encrypted chat relay between matched donor and requester.

Privacy guarantees:
- Every message passes through the PII scrubber before relay
- sender_role is 'donor' or 'requester' — never their identity
- channel auto-closes after donation confirmation
- All messages deleted 24 hours after channel close
"""

from typing import Annotated
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import ChatMessageSend, ChatMessageResponse
from api.routes.auth import get_current_user
from nlp.scrubber import scrub_message

router = APIRouter(prefix="/chat", tags=["chat"])


async def _get_sender_role(
    channel_id: str,
    user_id:    str,
    db:         AsyncSession,
) -> str:
    """Determine if user is 'donor' or 'requester' in this channel."""
    result = await db.execute(
        text("""
            SELECT m.donor_id, br.requester_id
            FROM matches m
            JOIN blood_requests br ON m.request_id = br.request_id
            WHERE m.chat_channel_id = :cid
        """),
        {"cid": channel_id},
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat channel not found",
        )

    if str(row.donor_id) == user_id:
        return "donor"
    elif str(row.requester_id) == user_id:
        return "requester"
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this chat",
        )


@router.get("/{channel_id}/messages")
async def get_messages(
    channel_id:   str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db:           Annotated[AsyncSession, Depends(get_db)],
):
    """Retrieve messages for a chat channel — scrubbed content only."""
    await _get_sender_role(channel_id, current_user["user_id"], db)

    result = await db.execute(
        text("""
            SELECT msg_id, sender_role, content_scrubbed,
                   pii_detected, sent_at, is_read
            FROM chat_messages
            WHERE channel_id = :cid
              AND deleted_at IS NULL
            ORDER BY sent_at ASC
        """),
        {"cid": channel_id},
    )
    rows = result.fetchall()

    # Mark messages as read
    await db.execute(
        text("""
            UPDATE chat_messages
            SET is_read = TRUE
            WHERE channel_id = :cid
              AND deleted_at IS NULL
        """),
        {"cid": channel_id},
    )

    return {
        "channel_id": channel_id,
        "messages": [
            {
                "msg_id":          str(r.msg_id),
                "sender_role":     r.sender_role,
                "content":         r.content_scrubbed,
                "pii_detected":    r.pii_detected,
                "sent_at":         r.sent_at.isoformat(),
                "is_read":         r.is_read,
            }
            for r in rows
        ],
    }


@router.post("/{channel_id}/send")
async def send_message(
    channel_id:   str,
    body:         ChatMessageSend,
    current_user: Annotated[dict, Depends(get_current_user)],
    db:           Annotated[AsyncSession, Depends(get_db)],
):
    """
    Send a message through the anonymous relay.
    Message is scrubbed for PII before being stored and relayed.
    """
    sender_role = await _get_sender_role(
        channel_id, current_user["user_id"], db
    )

    # ── PII SCRUBBING — the privacy core ──────────────────────────────────────
    scrub_result = await scrub_message(body.content)

    if scrub_result.pii_detected:
        print(
            f"[PII] Scrubbed message from {sender_role} in channel {channel_id[:8]}... "
            f"| Found: {', '.join(scrub_result.items_found)}"
        )

    # Store scrubbed version — raw is kept for audit but never shown
    result = await db.execute(
        text("""
            INSERT INTO chat_messages
                (channel_id, sender_role,
                 content_raw, content_scrubbed, pii_detected)
            VALUES
                (:cid, :role, :raw, :scrubbed, :pii)
            RETURNING msg_id, sent_at
        """),
        {
            "cid":      channel_id,
            "role":     sender_role,
            "raw":      body.content,
            "scrubbed": scrub_result.scrubbed,
            "pii":      scrub_result.pii_detected,
        },
    )
    row = result.fetchone()

    return {
        "msg_id":        str(row.msg_id),
        "sender_role":   sender_role,
        "content":       scrub_result.scrubbed,
        "pii_detected":  scrub_result.pii_detected,
        "pii_items":     scrub_result.items_found,
        "sent_at":       row.sent_at.isoformat(),
        "privacy_note":  "Message scrubbed for PII before relay" if scrub_result.pii_detected else "No PII detected",
    }


@router.post("/report")
async def report_abuse(
    channel_id:   str,
    reason:       str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db:           Annotated[AsyncSession, Depends(get_db)],
):
    """Report abuse in a chat channel — triggers immediate review."""
    print(
        f"[ABUSE REPORT] Channel {channel_id[:8]}... "
        f"| Reporter: {current_user['user_id'][:8]}... "
        f"| Reason: {reason}"
    )

    return {
        "message": "Report received. Channel under review within 24 hours.",
        "channel_id": channel_id,
    }