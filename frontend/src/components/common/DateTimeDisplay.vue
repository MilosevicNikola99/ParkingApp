<template>
  <time :datetime="value">{{ formattedValue }}</time>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  value: {
    type: String,
    default: "",
  },
});

const formattedValue = computed(() => {
  if (!props.value) {
    return "Not set";
  }

  const parsedValue = new Date(props.value);
  if (Number.isNaN(parsedValue.getTime())) {
    return "Invalid date";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsedValue);
});
</script>
