/**
 * api.js — Single source of truth for all backend API calls (DRY).
 *
 * In dev mode, Vite proxies /api → http://refiner:8000.
 * In prod mode (Nginx), requests go directly to the backend.
 */

const API_BASE = import.meta.env.DEV ? '/api' : 'http://localhost:8000';
const DATA_BASE = import.meta.env.DEV ? '/data' : 'http://localhost:8000/data';

async function fetchJSON(url, opts = {}) {
  const res = await fetch(`${API_BASE}${url}`, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function postJSON(url, body = {}) {
  return fetchJSON(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function putJSON(url, body = {}) {
  return fetchJSON(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function deleteResource(url) {
  return fetchJSON(url, { method: 'DELETE' });
}

async function uploadFiles(url, files) {
  const formData = new FormData();
  for (const f of files) formData.append('files', f);
  const res = await fetch(`${API_BASE}${url}`, { method: 'POST', body: formData });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || 'Upload failed');
  }
  return res.json();
}

export function dataUrl(path) {
  return `${DATA_BASE}/${path}`;
}

// ── Jobs ───────────────────────────────────────────────────────────────
export const createJob = (name) => postJSON('/jobs', { name });
export const listJobs = () => fetchJSON('/jobs');
export const getJob = (id) => fetchJSON(`/jobs/${id}`);
export const renameJob = (id, newName) => putJSON(`/jobs/${id}/rename`, { name: newName });
export const deleteJob = (id) => deleteResource(`/jobs/${id}`);
export const startJob = (id) => postJSON(`/jobs/${id}/start`);
export const assignDataset = (jobId, datasetId) => putJSON(`/jobs/${jobId}/dataset`, { dataset_id: datasetId });

// ── Datasets ───────────────────────────────────────────────────────────
export const createDataset = (name) => postJSON('/datasets', { name });
export const listDatasets = () => fetchJSON('/datasets');
export const listDatasetImages = (id) => fetchJSON(`/datasets/${id}/images`);
export const uploadToDataset = (id, files) => uploadFiles(`/datasets/${id}/upload`, files);
export const renameDataset = (id, newName) => putJSON(`/datasets/${id}/rename`, { name: newName });
export const deleteDataset = (id) => deleteResource(`/datasets/${id}`);
export const deleteDatasetImage = (id, name) => deleteResource(`/datasets/${id}/images/${name}`);

// ── Job Clusters ───────────────────────────────────────────────────────
export const getJobClusters = (id) => fetchJSON(`/jobs/${id}/clusters`);
export const renameCluster = (jid, cid, name) => putJSON(`/jobs/${jid}/clusters/${cid}/name`, { name });
export const deleteCluster = (jid, cid) => deleteResource(`/jobs/${jid}/clusters/${cid}`);

// ── Job Removed ────────────────────────────────────────────────────────
export const getJobRemoved = (id) => fetchJSON(`/jobs/${id}/removed`);

// ── Legacy ─────────────────────────────────────────────────────────────
export const getStatus = () => fetchJSON('/status');
