import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { clearAuthStorage, getStoredCurrentUser } from "@/services/authStorage";
import { fetchCurrentUser, logout as logoutFromService } from "@/services/authService";

export function useAuthenticatedPage() {
  const router = useRouter();
  const currentUser = ref(getStoredCurrentUser());
  const sessionError = ref("");

  async function loadCurrentUser() {
    try {
      currentUser.value = await fetchCurrentUser();
    } catch {
      clearAuthStorage();
      sessionError.value = "Your session has expired.";
      await router.push({ name: "login" });
    }
  }

  async function handleLogout() {
    logoutFromService();
    await router.push({ name: "login" });
  }

  onMounted(loadCurrentUser);

  return {
    currentUser,
    handleLogout,
    sessionError,
  };
}
