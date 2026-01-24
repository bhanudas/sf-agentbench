# SF-AgentBench Web Interface

Modern web interface for SF-AgentBench that enables users to review benchmark runs, inspect performance metrics, launch new benchmarks, and monitor progress in real-time.

## Quick Start

### Backend

Start the FastAPI backend server:

```bash
# From the project root
sf-agentbench serve

# Or with options
sf-agentbench serve -p 8000 -r  # Port 8000 with hot reload
sf-agentbench serve -o           # Open browser automatically
```

### Frontend

Start the React development server:

```bash
# From the web directory
cd web
npm install
npm run dev
```

The frontend will be available at http://localhost:5173 and will proxy API requests to the backend.

## Features

### Dashboard (/)
- Summary cards: Total runs, Success rate, Average score, Active agents
- Agent performance chart
- Run status distribution
- Recent runs with quick access

### Run Browser (/runs)
- Filterable/sortable table of all runs
- Filter by task, agent, status
- Quick score breakdown view

### Run Detail (/runs/:id)
- 5-layer score breakdown with radar chart
- Deployment, tests, static analysis, metadata, rubric details
- Agent output viewer
- Raw JSON viewer

### Live Monitor (/runs/:id/live)
- Real-time WebSocket event stream
- Progress indicators
- Pause/Resume/Cancel controls

### Run Launcher (/launch)
- Task selector grouped by tier
- Agent selector with availability status
- Model and timeout configuration

### Q&A Tests (/qa)
- Q&A run browser
- Model comparison charts
- Domain performance analysis

### Comparison (/compare)
- Multi-dimensional radar chart
- Score comparison bar charts
- Detailed comparison table

## Tech Stack

**Backend:**
- FastAPI (async Python web framework)
- WebSocket for real-time updates
- SQLite for data storage

**Frontend:**
- React 18 with TypeScript
- TanStack Query (data fetching/caching)
- Tailwind CSS (styling)
- Radix UI primitives
- Recharts (visualizations)
- React Router v6

## API Endpoints

```
GET  /api/runs                    # List benchmark runs
GET  /api/runs/:id                # Get run details
POST /api/runs                    # Start new benchmark
GET  /api/runs/summary            # Get summary statistics
GET  /api/runs/comparison         # Get agent comparison

GET  /api/qa/runs                 # List Q&A runs
GET  /api/qa/runs/:id             # Get Q&A run details
GET  /api/qa/comparison           # Model comparison
GET  /api/qa/domains              # Domain analysis
GET  /api/qa/banks                # List test banks

GET  /api/tasks                   # List available tasks
GET  /api/tasks/:id               # Get task details
GET  /api/models                  # List AI models
GET  /api/agents                  # List CLI agents
GET  /api/config                  # Get configuration

WS   /api/ws/runs/:id             # Run-specific events
WS   /api/ws/global               # Global events
```

## Development

### Backend Changes

The backend code is in `src/sf_agentbench/web/`:
- `app.py` - FastAPI application
- `schemas.py` - Pydantic models
- `routes/` - API route handlers

### Frontend Changes

The frontend code is in `web/src/`:
- `pages/` - Page components
- `components/` - Reusable components
- `hooks/` - Custom React hooks
- `lib/` - Utilities and API client
- `types/` - TypeScript types

### Building for Production

```bash
cd web
npm run build
```

The build output will be in `web/dist/` and can be served by the FastAPI backend.
