/**
 * resumeApi.js — API client for the resume generator backend.
 */
import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
 * Generate a resume for the given category.
 * @param {string} category - The job category (e.g., "INFORMATION-TECHNOLOGY")
 * @returns {Promise<Object>} Generated resume data
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
