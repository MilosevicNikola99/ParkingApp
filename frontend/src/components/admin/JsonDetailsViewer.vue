<template>
  <details class="json-details">
    <summary>{{ summary }}</summary>
    <pre>{{ formattedValue }}</pre>
  </details>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  value: {
    type: [Array, Object],
    required: true,
  },
  summary: {
    type: String,
    default: "View details",
  },
});

const formattedValue = computed(() => JSON.stringify(props.value, null, 2));
</script>
