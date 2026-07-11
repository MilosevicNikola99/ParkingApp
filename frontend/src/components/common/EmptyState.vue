<template>
  <div class="empty-state">
    <div class="empty-state__icon" aria-hidden="true">{{ icon }}</div>
    <h2>{{ title }}</h2>
    <p v-if="message">{{ message }}</p>
    <RouterLink v-if="actionTo && actionLabel" class="empty-state__action" :to="actionTo">
      {{ actionLabel }}
    </RouterLink>
    <span v-else-if="actionLabel" class="empty-state__hint">{{ actionLabel }}</span>
  </div>
</template>

<script setup>
import { RouterLink } from "vue-router";

defineProps({
  title: {
    type: String,
    required: true,
  },
  message: {
    type: String,
    default: "",
  },
  actionLabel: {
    type: String,
    default: "",
  },
  actionTo: {
    type: String,
    default: "",
  },
  icon: {
    type: String,
    default: "i",
  },
});
</script>