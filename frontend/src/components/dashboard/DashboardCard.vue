<template>
  <component :is="componentType" class="dashboard-card" :to="to || undefined">
    <div class="dashboard-card__header">
      <h2>{{ title }}</h2>
      <span v-if="status" class="dashboard-card__status">{{ status }}</span>
    </div>
    <p class="dashboard-card__metric">{{ metric }}</p>
    <p class="dashboard-card__label">{{ label }}</p>
  </component>
</template>

<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  metric: {
    type: String,
    default: "-",
  },
  label: {
    type: String,
    default: "",
  },
  status: {
    type: String,
    default: "",
  },
  to: {
    type: String,
    default: "",
  },
});

const componentType = computed(() => (props.to ? RouterLink : "section"));
</script>
