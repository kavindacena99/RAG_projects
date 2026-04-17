export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export function getApiErrorMessage(error, fallback = 'Something went wrong.') {
  if (error instanceof ApiError) {
    if (typeof error.data === 'string' && error.data.trim()) {
      return error.data;
    }

    if (error.data && typeof error.data === 'object') {
      if (typeof error.data.error === 'string' && error.data.error.trim()) {
        return error.data.error;
      }

      if (typeof error.data.detail === 'string' && error.data.detail.trim()) {
        return error.data.detail;
      }

      if (Array.isArray(error.data.non_field_errors) && error.data.non_field_errors.length > 0) {
        return error.data.non_field_errors[0] ?? fallback;
      }
    }

    return error.message || fallback;
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
}
