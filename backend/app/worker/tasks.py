"""Background task functions (Phase B-3).

Three async coroutines registered with the ARQ worker:

* :func:`optimise_image_task` — reads the local-disk source file,
  runs the existing ``optimize_image`` pipeline, and updates the
  ``MediaAsset.variants`` JSON column when complete.

* :func:`send_email_task` — wraps ``EmailService.send_simple`` so a
  caller can fire-and-forget the SMTP send instead of paying the
  1-3s round-trip on the request path.

* :func:`generate_ai_review_task` — wraps the existing
  ``candidate_auto_review.run_auto_review`` so the public Apply
  endpoint can return 201 immediately and let the AI scoring
  happen in the worker.

All three open their own ``SessionLocal`` per call. ARQ runs them
in a separate process — they can't share the API request's
session. Failures are logged and swallowed inside the task so a
poisoned job doesn't break the worker (ARQ marks the job failed
and moves on).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.core.logging_config import get_logger


logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 1. Image optimisation
# ---------------------------------------------------------------------------


async def optimise_image_task(
    ctx: dict[str, Any],
    file_path: str,
    media_asset_id: int,
    public_base_url: str = "/api/v1/uploads/cms",
    mime_type: Optional[str] = None,
) -> dict[str, Any]:
    """Generate WebP + JPEG variants for a freshly-uploaded image.

    Updates the ``MediaAsset.variants`` JSON column when complete so
    the public site can render the resized + WebP-converted variants
    instead of the original. Returns a small summary dict that ARQ
    parks in Redis under ``arq:result:<job_id>`` for ``keep_result``
    seconds so an admin status-poll endpoint can confirm the run.

    ``ctx`` is the per-worker dict ARQ supplies (Redis pool, job id,
    etc.); not used here but part of the ARQ task signature contract.
    """
    from app.core.database import SessionLocal
    from app.models.cms import MediaAsset
    from app.services.image_optimization import optimize_image

    logger.info(
        "Worker: optimise_image_task started",
        media_asset_id=media_asset_id,
        file_path=file_path,
    )

    source = Path(file_path)
    variant_set = optimize_image(
        source,
        public_base_url=public_base_url,
        mime_type=mime_type,
    )
    if variant_set is None:
        logger.warning(
            "Worker: optimise_image_task produced no variants",
            media_asset_id=media_asset_id,
        )
        return {"media_asset_id": media_asset_id, "variants": None}

    payload = variant_set.as_dict()
    with SessionLocal() as db:
        row = db.get(MediaAsset, media_asset_id)
        if row is None:
            logger.warning(
                "Worker: media asset disappeared mid-optimisation",
                media_asset_id=media_asset_id,
            )
            return {"media_asset_id": media_asset_id, "variants": payload}
        row.variants = payload
        db.commit()

    logger.info(
        "Worker: optimise_image_task complete",
        media_asset_id=media_asset_id,
        variant_count=sum(len(v) for v in payload.values()),
    )
    return {"media_asset_id": media_asset_id, "variants": payload}


# ---------------------------------------------------------------------------
# 2. Email
# ---------------------------------------------------------------------------


async def send_email_task(
    ctx: dict[str, Any],
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> dict[str, Any]:
    """Send a plain branded email via SMTP.

    Wraps ``EmailService.send_simple`` so the caller can return 200
    immediately. The result dict gets stashed in Redis by ARQ —
    callers that need to know "did it actually go out?" can read
    the job result.
    """
    from app.core.database import SessionLocal
    from app.services.email import EmailService

    logger.info(
        "Worker: send_email_task started",
        to=to_email,
        subject=subject[:80],
    )
    with SessionLocal() as db:
        result = EmailService.send_simple(
            db,
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            reply_to=reply_to,
        )
    if result.success:
        logger.info("Worker: send_email_task sent", to=to_email)
    else:
        logger.warning(
            "Worker: send_email_task failed",
            to=to_email,
            error=result.message,
        )
    return {
        "success": result.success,
        "message": result.message,
        "sent_at": result.sent_at.isoformat() if result.sent_at else None,
    }


# ---------------------------------------------------------------------------
# 3. AI review
# ---------------------------------------------------------------------------


async def generate_ai_review_task(
    ctx: dict[str, Any],
    candidate_id: int,
    application_id: int,
) -> dict[str, Any]:
    """Run the AI / rule-based candidate auto-review.

    Wraps ``candidate_auto_review.run_auto_review`` against the
    application identified by ``application_id``. Returns the
    review's id when one was created, else ``None``.

    Failures are logged and swallowed so a single failing job
    can't poison the worker — ARQ marks the result accordingly
    and the caller can re-enqueue.
    """
    from app.core.database import SessionLocal
    from app.models.hr_ats import CandidateJobApplication
    from app.services.candidate_auto_review import run_auto_review

    logger.info(
        "Worker: generate_ai_review_task started",
        candidate_id=candidate_id,
        application_id=application_id,
    )
    review_id: Optional[int] = None
    try:
        with SessionLocal() as db:
            app_row = db.get(CandidateJobApplication, application_id)
            if app_row is None:
                logger.warning(
                    "Worker: application disappeared before AI review",
                    application_id=application_id,
                )
                return {
                    "application_id": application_id,
                    "review_id": None,
                    "skipped": "application missing",
                }
            review = run_auto_review(db, application=app_row)
            db.commit()
            review_id = getattr(review, "id", None)
    except Exception as exc:  # noqa: BLE001 — never poison the worker
        logger.exception(
            "Worker: generate_ai_review_task crashed",
            application_id=application_id,
        )
        return {
            "application_id": application_id,
            "review_id": None,
            "error": str(exc)[:300],
        }

    logger.info(
        "Worker: generate_ai_review_task complete",
        application_id=application_id,
        review_id=review_id,
    )
    return {"application_id": application_id, "review_id": review_id}


__all__ = [
    "generate_ai_review_task",
    "optimise_image_task",
    "send_email_task",
]
