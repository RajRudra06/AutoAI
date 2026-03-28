# AutoAI Frontend (Vehicle-First UX)

This app is the AutoAI user-facing frontend with Clerk authentication and a vehicle-first flow:
- Sign in
- Welcome screen with your vehicles
- Issue window for bad vehicles
- Per-vehicle simple live summary, issues, lifecycle, and Crew AI summary

## Run Locally

1. Install dependencies:

```bash
npm install
```

2. Configure environment variables (`.env.local`):

```bash
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000/api
NEXT_PUBLIC_BACKEND_WS=ws://127.0.0.1:8000/api
NEXT_PUBLIC_AGENT_ID=agent_001
NEXT_PUBLIC_API_KEY=secret_key_001
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<your_clerk_publishable_key>
CLERK_SECRET_KEY=<your_clerk_secret_key>
```

3. Start the app:

```bash
npm run dev
```

4. Open:
- Home (auth-gated): http://localhost:3000
- Welcome screen: http://localhost:3000/welcome
- Vehicle details: http://localhost:3000/vehicle/<vehicle_id>

## Quality Checks

```bash
npm run lint
npm run build
```

## Backend Contracts Used

- `GET /api/activity/events`
- `GET /api/activity/metrics/overview`
- `GET /api/activity/metrics/health`
- `GET /api/vehicles/state`
- `GET /api/activity/vehicle/{vehicle_id}`
- `GET /api/activity/summary/{vehicle_id}`
- `POST /api/activity/summary/{vehicle_id}`
- `WS /api/activity/ws`

## Notes

- Your account vehicles can be scoped via Clerk public metadata:

```json
{
	"vehicleIds": ["V_001", "V_014", "V_900"]
}
```

- If `vehicleIds` is not set, the welcome page currently shows all vehicles from backend state.
