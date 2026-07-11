const ACCESS_TOKEN_KEY = "parking_app_access_token";
const CURRENT_USER_KEY = "parking_app_current_user";

export function getAccessToken() {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export function hasAccessToken() {
  return Boolean(getAccessToken());
}

export function getStoredCurrentUser() {
  const rawUser = window.localStorage.getItem(CURRENT_USER_KEY);
  if (!rawUser) {
    return null;
  }

  try {
    return JSON.parse(rawUser);
  } catch {
    clearStoredCurrentUser();
    return null;
  }
}

export function setStoredCurrentUser(user) {
  window.localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(user));
}

export function clearStoredCurrentUser() {
  window.localStorage.removeItem(CURRENT_USER_KEY);
}

export function clearAuthStorage() {
  clearAccessToken();
  clearStoredCurrentUser();
}
