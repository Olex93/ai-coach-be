from fastapi import Request
from datetime import datetime, timedelta


class SessionTimeoutMiddleware:
    def __init__(self, app, timeout: int = 30):
        self.app = app
        self.timeout = timeout  # timeout in minutes
        self.sessions = {}

    async def __call__(self, request: Request, call_next):
        user_id = request.headers.get("user-id")
        if user_id:
            now = datetime.utcnow()
            last_active = self.sessions.get(user_id)
            if last_active and now - last_active > timedelta(minutes=self.timeout):
                # End session due to inactivity
                del self.sessions[user_id]
                request.state.session_expired = True
            else:
                self.sessions[user_id] = now
                request.state.session_expired = False
        else:
            request.state.session_expired = False

        response = await call_next(request)
        return response
