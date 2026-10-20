const API_URL = '/api';

function buildUrl(endpoint, params) {
  const query = params ? new URLSearchParams(params).toString() : '';
  return query ? `${API_URL}${endpoint}?${query}` : `${API_URL}${endpoint}`;
}

export async function fetchWrapper(endpoint, options = {}) {
  const { params, responseType, ...requestOptions } = options;
  const response = await fetch(buildUrl(endpoint, params), requestOptions);

  if (!response.ok) {
    let message = 'Request failed';
    try {
      const errorData = await response.json();
      message = errorData.detail || errorData.message || message;
    } catch {
      // Keep the generic message when the response body is not JSON.
    }
    throw new Error(message);
  }

  if (responseType === 'blob') {
    return response.blob();
  }

  const contentType = response.headers.get('content-type');
  if (contentType?.includes('application/json')) {
    return response.json();
  }
  return response.blob();
}

export const conversionApi = {
  getFormats: () => fetchWrapper('/conversions/formats/'),

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

  getStatus: (jobId) => fetchWrapper(`/jobs/${jobId}`),

  listJobs: (params) => fetchWrapper('/jobs/', { params }),

  downloadResult: (jobId) =>
    fetchWrapper(`/jobs/${jobId}/download/`, { responseType: 'blob' }),

  cancelJob: (jobId) =>
    fetchWrapper(`/jobs/${jobId}/cancel`, { method: 'POST' }),
};

export const processingApi = {
  uploadFile: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return fetchWrapper('/processing/upload', {
      method: 'POST',
      body: formData,
    });
  },

  getOperations: (fileType) =>
    fetchWrapper(`/processing/operations/?type=${encodeURIComponent(fileType)}`),

  process: (operation, data) =>
    fetchWrapper(`/processing/${operation}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  getStatus: (jobId) => fetchWrapper(`/processing/jobs/${jobId}`),

  downloadResult: (jobId) =>
    fetchWrapper(`/processing/jobs/${jobId}/download`, {
      responseType: 'blob',
    }),

  processUpload: (operation, formData) =>
    fetchWrapper(`/processing/${operation}/`, {
      method: 'POST',
      body: formData,
    }),

  processPdf: (recipePayload) =>
    fetchWrapper('/processing/pdf/merge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(recipePayload),
    }),
};

export default fetchWrapper;
