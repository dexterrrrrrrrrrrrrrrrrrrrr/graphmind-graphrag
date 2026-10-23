"""Cap multipart request bytes before a parser can spool an unlimited upload."""

from starlette.responses import JSONResponse


class RequestTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app, max_upload_bytes):
        self.app = app
        self.max_upload_bytes = max_upload_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = (
            self.max_upload_bytes + 1024 * 1024 if scope["path"] == "/api/documents/upload" else 1024 * 1024
        )
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = limit + 1
        if declared > limit:
            return await JSONResponse(
                {"error": {"code": "too_large", "message": "Request body exceeds limit"}}, status_code=413
            )(scope, receive, send)
        count = 0
        started = False

        async def bounded_receive():
            nonlocal count
            message = await receive()
            if message["type"] == "http.request":
                count += len(message.get("body", b""))
                if count > limit:
                    raise RequestTooLarge()
            return message

        async def track_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, bounded_receive, track_send)
        except RequestTooLarge:
            if not started:
                await JSONResponse(
                    {"error": {"code": "too_large", "message": "Request body exceeds limit"}}, status_code=413
                )(scope, receive, send)
