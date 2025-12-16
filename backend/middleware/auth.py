from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# later db call to check agent id and corresponding api key after salting
VALID_AGENTS = {
    "agent_001": "secret_key_001",
    "agent_002": "secret_key_002",
}

class AgentAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        # Allow health checks without auth
        if request.url.path == "/health":
            return await call_next(request)

        agent_id = request.headers.get("X-AGENT-ID")
        api_key = request.headers.get("X-API-KEY")

        if not agent_id or not api_key:
            print("[AUTH] ❌ Missing agent credentials")
            raise HTTPException(401, "Missing agent credentials")

        expected_key = VALID_AGENTS.get(agent_id)
        if expected_key != api_key:
            print(f"[AUTH] ❌ Invalid credentials for agent_id={agent_id}")
            raise HTTPException(403, "Invalid agent credentials")

        # ✅ Agent authenticated
        print(f"[AUTH] ✅ Agent authenticated: {agent_id}")

        # Attach identity for later use
        request.state.agent_id = agent_id

        return await call_next(request)
