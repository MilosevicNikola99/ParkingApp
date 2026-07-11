<template>
  <span class="status-badge" :class="statusClass">{{ label }}</span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  status: {
    type: String,
    required: true,
  },
});

const normalizedStatus = computed(() => props.status.toLowerCase().replaceAll("_", "-"));
const statusClass = computed(() => `status-badge--${normalizedStatus.value}`);
const label = computed(() => props.status.replaceAll("_", " "));
</script>
