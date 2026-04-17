import { ApiError } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

let getAccessToken = () => null;
let onUnauthorized = () => undefined;

function buildUrl(path) {
  return `${API_BASE_URL}${path}`;
}

function isSerializableBody(body) {
  return Boolean(
    body &&
      typeof body === 'object' &&
      !(body instanceof FormData) &&
      !(body instanceof Blob) &&
      !(body instanceof URLSearchParams),
  );
}

function buildHeaders(headers, skipAuth) {
  const nextHeaders = new Headers(headers);

  if (!skipAuth) {
    const token = getAccessToken();
    if (token) {
      nextHeaders.set('Authorization', `Bearer ${token}`);
    }
  }

  return nextHeaders;
}

async function parseErrorData(response) {
  const contentType = response.headers.get('content-type') ?? '';

  if (contentType.includes('application/json')) {
    return await response.json();
  }

  const text = await response.text();
  return text || undefined;
}

async function parseResponse(response) {
  if (response.status === 204) {
    return undefined;
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return await response.json();
  }

  return await response.text();
}

async function performRequest(path, options = {}) {
  const { body, headers, skipAuth = false, ...requestInit } = options;
  const requestHeaders = buildHeaders(headers, skipAuth);

  let requestBody = body;
  if (isSerializableBody(body)) {
    requestHeaders.set('Content-Type', 'application/json');
    requestBody = JSON.stringify(body);
  }

  const response = await fetch(buildUrl(path), {
    ...requestInit,
    body: requestBody,
    headers: requestHeaders,
  });

  if (response.status === 401) {
    onUnauthorized();
  }

  if (!response.ok) {
    const errorData = await parseErrorData(response);
    throw new ApiError(response.statusText || 'Request failed.', response.status, errorData);
  }

  return response;
}

export function configureApiClient(config) {
  getAccessToken = config.getAccessToken ?? (() => null);
  onUnauthorized = config.onUnauthorized ?? (() => undefined);
}

export const apiClient = {
  async delete(path, options) {
    const response = await performRequest(path, {
      ...options,
      method: 'DELETE',
    });

    return parseResponse(response);
  },

  async get(path, options) {
    const response = await performRequest(path, {
      ...options,
      method: 'GET',
    });

    return parseResponse(response);
  },

  async post(path, body, options) {
    const response = await performRequest(path, {
      ...options,
      body: body ?? null,
      method: 'POST',
    });

    return parseResponse(response);
  },

  async stream(path, options) {
    return performRequest(path, {
      ...options,
      headers: {
        Accept: 'text/event-stream, application/json;q=0.9, */*;q=0.8',
        ...options?.headers,
      },
    });
  },
};
