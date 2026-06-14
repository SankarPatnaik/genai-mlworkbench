export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_KEY = import.meta.env.VITE_WORKBENCH_API_KEY || '';

export function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

export function apiHeaders(extraHeaders = {}) {
  return {
    ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
    ...extraHeaders,
  };
}

export async function parseApiError(response, fallbackMessage) {
  try {
    const body = await response.json();
    return body.detail || fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}
