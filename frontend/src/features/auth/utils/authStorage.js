const AUTH_STORAGE_KEY = 'rag_frontend_auth';

export function loadStoredAuth() {
  const storedValue = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!storedValue) {
    return null;
  }

  try {
    return JSON.parse(storedValue);
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

export function saveStoredAuth(auth) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
}

export function clearStoredAuth() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}
