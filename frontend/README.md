# Frontend — AI Resume Generator

React + Vite frontend for the Resume Generation RAG application.

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at → **http://localhost:5173**  
Requires backend at → **http://localhost:8000**

## Features
- Category dropdown (loads from backend)
- Generate Resume button with loading state
- Live resume preview with section formatting
- PDF download button
- Premium dark glassmorphism UI

## Environment

Create `.env.local` to override the API URL:
```
VITE_API_URL=http://localhost:8000
```

## Build for Production

```bash
npm run build
npm run preview
```
