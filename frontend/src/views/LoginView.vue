<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-panel__header">
        <p class="login-panel__eyebrow">Company Parking</p>
        <h1>Sign in</h1>
      </div>

      <form class="login-form" @submit.prevent="submitLogin">
        <BaseInput
          v-model="identifier"
          autocomplete="username"
          label="Username or email"
          name="identifier"
          placeholder="name@example.com"
        />
        <BaseInput
          v-model="password"
          autocomplete="current-password"
          label="Password"
          name="password"
          type="password"
        />
        <AlertMessage :message="errorMessage" />
        <BaseButton :loading="isSubmitting" type="submit">Sign in</BaseButton>
      </form>
    </section>
  </main>
</template>

<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import AlertMessage from "@/components/common/AlertMessage.vue";
import BaseButton from "@/components/common/BaseButton.vue";
import BaseInput from "@/components/common/BaseInput.vue";
import { fetchCurrentUser, login } from "@/services/authService";

const router = useRouter();
const route = useRoute();

const identifier = ref("");
const password = ref("");
const errorMessage = ref("");
const isSubmitting = ref(false);

async function submitLogin() {
  errorMessage.value = "";

  const trimmedIdentifier = identifier.value.trim();
  if (!trimmedIdentifier || !password.value) {
    errorMessage.value = "Enter your username or email and password.";
    return;
  }

  isSubmitting.value = true;
  try {
    await login(trimmedIdentifier, password.value);
    await fetchCurrentUser();

    const redirectPath = typeof route.query.redirect === "string" ? route.query.redirect : "/dashboard";
    await router.push(redirectPath);
  } catch {
    errorMessage.value = "Invalid credentials.";
  } finally {
    isSubmitting.value = false;
  }
}
</script>
