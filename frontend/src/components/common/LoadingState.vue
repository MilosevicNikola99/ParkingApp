<template>
  <div class="loading-state" role="status">
    <span class="loading-state__spinner" aria-hidden="true"></span>
    <span>{{ message }}</span>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: String,
    default: "Loading parking data",
  },
});
</script>
