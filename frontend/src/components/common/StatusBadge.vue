<template>
  <span class="status-badge" :class="statusClass">{{ label }}</span>
</template>

<script setup>
import { computed } from "vue";

import { getStatusLabel } from "@/utils/display";

const props = defineProps({
  status: {
    type: String,
    required: true,
  },
});

const normalizedStatus = computed(() => props.status.toLowerCase().replaceAll("_", "-"));
const statusClass = computed(() => `status-badge--${normalizedStatus.value}`);
const label = computed(() => getStatusLabel(props.status));
</script>
