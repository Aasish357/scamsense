# ScamSense Architecture Overview

## Components

- **Frontend**: Next.js application handling the user interface.
- **Backend**: Python FastAPI for handling API requests and logic.
- **Database**: PostgreSQL via Supabase for storing analyses and user data.
- **AI Integration**: OpenAI for providing insights and risk assessments.
- **Security**: Focused mechanisms for data privacy and security.

## Data Flow

1. User submits data (text, URL, screenshot).
2. Frontend sends data to the backend via API.
3. Backend processes the data for analysis and stores results.
4. Results are sent back to the frontend for user display.