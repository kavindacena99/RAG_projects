import json
import logging

from django.http import StreamingHttpResponse

from core.exceptions import GenerationError
from rag.services.generation_service import generate_answer_stream

logger = logging.getLogger("chat")


def _format_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def build_streaming_response(
    *,
    prompt: str,
    response_schema: dict | None = None,
    output_mode: str = "standard",
    metadata: dict,
    on_complete,
    on_error=None,
) -> StreamingHttpResponse:
    def event_stream():
        full_chunks = []
        yield _format_sse({"type": "metadata", **metadata})

        try:
            for chunk in generate_answer_stream(
                prompt,
                response_schema=response_schema,
                output_mode=output_mode,
            ):
                if not chunk:
                    continue
                full_chunks.append(chunk)
                yield _format_sse({"type": "token", "content": chunk})

            final_text = "".join(full_chunks).strip()
            if not final_text:
                raise GenerationError("Assistant response was empty.")

            completion_payload = on_complete(final_text) or {}
            yield _format_sse(
                {
                    "type": "done",
                    "content": final_text,
                    **completion_payload,
                }
            )
        except Exception as exc:
            logger.exception("streaming response failed")
            if on_error:
                on_error(exc)
            yield _format_sse({"type": "error", "detail": str(exc)})

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
