<template>
  <div class="page-toolbar">
    <div>
      <p class="page-toolbar__eyebrow">{{ eyebrow }}</p>
      <h2>{{ title }}</h2>
      <p v-if="description" class="page-toolbar__description">{{ description }}</p>
    </div>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  eyebrow: {
    type: String,
    default: "Administration",
  },
  description: {
    type: String,
    default: "",
  },
});
</script>