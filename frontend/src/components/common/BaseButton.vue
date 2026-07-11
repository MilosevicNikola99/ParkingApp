<template>
  <button
    class="base-button"
    :class="[variantClass, sizeClass]"
    :disabled="disabled || loading"
    :type="type"
  >
    <span v-if="loading" class="base-button__spinner" aria-hidden="true"></span>
    <span><slot /></span>
  </button>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  type: {
    type: String,
    default: "button",
  },
  variant: {
    type: String,
    default: "primary",
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  size: {
    type: String,
    default: "regular",
  },
});

const variantClass = computed(() => `base-button--${props.variant}`);
const sizeClass = computed(() => `base-button--${props.size}`);
</script>
