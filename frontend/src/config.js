const isProd = import.meta.env.PROD;

// On Render, the backend and frontend will be separate services.
// We can use an environment variable VITE_API_URL if provided, 
// otherwise fallback to localhost for development.
export const API_BASE = import.meta.env.VITE_API_URL || (isProd ? '' : 'http://127.0.0.1:8000');

// Generate WebSocket URL based on the API_BASE
export const WS_URL = API_BASE.replace(/^http/, 'ws') + '/ws/stream';
