<template>
  <p v-if="message" class="alert-message" :class="variantClass" role="alert">
    {{ message }}
  </p>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  message: {
    type: String,
    default: "",
  },
  variant: {
    type: String,
    default: "error",
  },
});

const variantClass = computed(() => `alert-message--${props.variant}`);
</script>
