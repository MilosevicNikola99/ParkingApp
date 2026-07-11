import apiClient from "./apiClient";
import {
  clearAuthStorage,
  setAccessToken,
  setStoredCurrentUser,
} from "./authStorage";

export async function login(identifier, password) {
  const response = await apiClient.post("/auth/login", {
    identifier,
    password,
  });

  setAccessToken(response.data.access_token);
  return response.data;
}

export async function fetchCurrentUser() {
  const response = await apiClient.get("/auth/me");
  setStoredCurrentUser(response.data);
  return response.data;
}

export function logout() {
  clearAuthStorage();
}
