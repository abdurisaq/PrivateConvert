import { useAuthStore } from '../utils/authStore';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

function getAuthHeaders() {
  const { access } = useAuthStore.getState();
  return access ? { Authorization: `Bearer ${access}` } : {};
}

async function handleResponse(response) {
  if (response.status === 401) {
    useAuthStore.getState().logout();
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || errorData.message || 'Request failed';
    return Promise.reject(new Error(message));
  }

  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/octet-stream')) {
    return response.blob();
  }

  return response.json();
}

function buildUrl(endpoint, params) {
  if (!params) return API_URL + endpoint;
  const query = new URLSearchParams(params).toString();
  return query ? `${API_URL}${endpoint}?${query}` : API_URL + endpoint;
}

export async function fetchWrapper(endpoint, options = {}) {
  const authHeaders = getAuthHeaders();

  // Merge headers
  options.headers = {
    ...authHeaders,
    ...options.headers,
  };

  const responseType = options.responseType;
  delete options.responseType;

  const url = buildUrl(endpoint, options.params);
  delete options.params;

  console.log('Request URL:', url);
  console.log('Request options:', options);

  const response = await fetch(url, options);

  console.log('Response status:', response.status);
  console.log('Response headers:', Array.from(response.headers.entries()));

  const contentType = response.headers.get('content-type');

  if (!response.ok) {
    let errorMessage = 'Request failed';
    if (contentType && contentType.includes('application/json')) {
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch {
        const text = await response.text().catch(() => '');
        errorMessage = `Request failed (invalid JSON): ${text}`;
      }
    }
    throw new Error(errorMessage);
  }

  if (responseType === 'blob') {
    return response.blob();
  }

  if (contentType && contentType.includes('application/octet-stream')) {
    return response.blob();
  }

  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }
  return response.blob();
}




export const authApi = {
  login: (email, password) =>
    fetchWrapper('/auth/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),

  register: (email, password) =>
    fetchWrapper('/auth/register/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, password2: password }),
    }),

  me: () => fetchWrapper('/auth/me/'),
};

export const conversionApi = {
  getFormats: () =>
    fetchWrapper('/conversions/formats/'),

  upload: (file, inputFormat, outputFormat) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('input_format', inputFormat);
    formData.append('output_format', outputFormat);

    return fetchWrapper('/conversions/upload/', {
      method: 'POST',
      body: formData,
    });
  },

  getStatus: (jobId) =>
    fetchWrapper(`/jobs/${jobId}/`),

  listJobs: (params) =>
    fetchWrapper('/jobs/', { params }),

  downloadResult: (jobId) =>
    fetchWrapper(`/jobs/${jobId}/download/`, {
      responseType: 'blob',
    }),

  cancelJob: (jobId) =>
    fetchWrapper(`/jobs/${jobId}/cancel/`, {
      method: 'POST',
    }),
};

export const processingApi = {
  /** Upload a file for processing and let backend auto-detect type */
  uploadFile: (file) => {
    const formData = new FormData();
    formData.append('file', file);

    return fetchWrapper('/processing/upload', {
      method: 'POST',
      body: formData,
    });
  },

  /** Ask backend: what operations are available for this file type?  
      e.g. pdf → ["split", "merge", "compress", "rotate"] */
  getOperations: (fileType) =>
    fetchWrapper(`/processing/operations/?type=${encodeURIComponent(fileType)}`),

  /** Generic operation trigger  
      operation = "split" | "merge" | "compress" | etc. */
  process: (operation, data) =>
    fetchWrapper(`/processing/${operation}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  /** Poll processing job status */
  getStatus: (jobId) =>
    fetchWrapper(`/processing/jobs/${jobId}/`),

  /** Download final processed file */
  downloadResult: (jobId) =>
    fetchWrapper(`/processing/jobs/${jobId}/download`, {
      responseType: 'blob',
    }),

  processUpload: (operation, formData) =>
    fetchWrapper(`/processing/${operation}/`, {
      method: 'POST',
      body: formData,
    }),

    processPdf: (recipePayload) => {
        return fetchWrapper('/processing/pdf/merge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(recipePayload),
        });
    },
};


export default fetchWrapper;
