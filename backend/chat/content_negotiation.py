from rest_framework.negotiation import DefaultContentNegotiation


class EventStreamCompatibleContentNegotiation(DefaultContentNegotiation):
    """
    Allow clients to advertise text/event-stream for streaming endpoints
    without triggering DRF's 406 renderer negotiation before the view returns
    a native StreamingHttpResponse.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        accept_header = request.META.get("HTTP_ACCEPT", "")
        if "text/event-stream" in accept_header and renderers:
            return renderers[0], renderers[0].media_type

        return super().select_renderer(request, renderers, format_suffix=format_suffix)
