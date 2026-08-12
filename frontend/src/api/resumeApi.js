/**
 * resumeApi.js — API client for the resume generator backend.
 */
import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? "" : "http://localhost:8000");

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120000, // 2 minutes — LLM generation can take time
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * Fetch all available resume categories from the backend.
 * @returns {Promise<string[]>} List of category names
 */
export async function getCategories() {
  const response = await api.get("/categories");
  return response.data.categories;
}

/**
 * Generate a resume for the given category (Streamed).
 * @param {string} category - The job category
 * @param {function} onChunk - Callback when new text chunk arrives
 * @param {function} onComplete - Callback with final metadata (pdf_url, etc)
 * @param {function} onError - Callback on error
 */
export async function streamResume(category, onChunk, onComplete, onError) {
  try {
    const response = await fetch(`${BASE_URL}/generate-resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || "Request failed");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let done = false;
    let buffer = "";

    while (!done) {
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      if (value) {
        buffer += decoder.decode(value, { stream: true });
        
        // Process SSE lines
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || ""; // Keep the incomplete part

        for (const line of lines) {
          if (line.startsWith("event: error")) {
            const dataLine = line.split("\n").find(l => l.startsWith("data: "));
            if (dataLine) {
              const data = JSON.parse(dataLine.replace("data: ", ""));
              onError(new Error(data.detail));
              return;
            }
          } else if (line.startsWith("event: complete")) {
            const dataLine = line.split("\n").find(l => l.startsWith("data: "));
            if (dataLine) {
              const data = JSON.parse(dataLine.replace("data: ", ""));
              onComplete(data);
            }
          } else if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.replace("data: ", ""));
              if (data.text) {
                onChunk(data.text);
              }
            } catch (e) {
              // ignore parse errors for partial json if any
            }
          }
        }
      }
    }
  } catch (err) {
    onError(err);
  }
}

/**
 * Generate a resume for the given category (Legacy - non-streaming fallback if needed).
 */
export async function generateResume(category) {
  const response = await api.post("/generate-resume", { category });
  return response.data;
}

/**
 * Get the full download URL for a generated PDF.
 * @param {string} filename - PDF filename from the generate response
 * @returns {string} Full download URL
 */
export function getDownloadUrl(filename) {
  if (!filename) return "";
  const path = filename.startsWith("/") ? filename : `/${filename}`;
  return `${BASE_URL}${path}`;
}

/**
 * Check backend health.
 * @returns {Promise<Object>} Health status
 */
export async function checkHealth() {
  const response = await api.get("/health");
  return response.data;
}

/**
 * Trigger ingestion pipeline via API.
 * @returns {Promise<Object>} Ingest response
 */
export async function triggerIngestion() {
  const response = await api.post("/ingest");
  return response.data;
}

/**
 * Evaluate accuracy for one category.
 * @param {string} category
 * @param {boolean} regenerate - force new LLM generation
 */
export async function evaluateCategory(
  category,
  regenerate = false,
  forceRefresh = false
) {
  const response = await api.get(`/evaluate/${encodeURIComponent(category)}`, {
    params: { regenerate, force_refresh: forceRefresh },
    timeout: 300000,
  });
  return response.data;
}

/**
 * Evaluate all categories (uses cache unless forceRefresh is true).
 * @param {boolean} forceRefresh - ignore cache and recompute
 */
export async function evaluateAll(forceRefresh = false) {
  const response = await api.get("/evaluate/all", {
    params: { regenerate: false, force_refresh: forceRefresh },
    timeout: forceRefresh ? 600000 : 30000,
  });
  return response.data;
}

/**
 * Fetch cached all-categories report instantly (no re-evaluation).
 */
export async function getCachedAllAccuracyReport() {
  const response = await api.get("/accuracy/report/all", { timeout: 15000 });
  return response.data;
}

/**
 * Check if cached all-categories report exists.
 */
export async function getAccuracyCacheStatus() {
  const response = await api.get("/accuracy/cache/status", { timeout: 10000 });
  return response.data;
}

/**
 * Fetch the latest single-category saved accuracy report.
 */
export async function getAccuracyReport() {
  const response = await api.get("/accuracy/report");
  return response.data;
}

export default api;
