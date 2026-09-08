<template>
  <span class="person-cell">
    <strong class="person-cell__name">{{ primaryLabel }}</strong>
    <span v-if="secondaryEmail" class="person-cell__email">{{ secondaryEmail }}</span>
    <span v-if="showUsername && user?.username" class="person-cell__username">@{{ user.username }}</span>
    <small v-if="showReference && fallbackId" class="person-cell__reference">User #{{ fallbackId }}</small>
  </span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  user: {
    type: Object,
    default: null,
  },
  fallbackId: {
    type: [Number, String],
    default: null,
  },
  showReference: {
    type: Boolean,
    default: false,
  },
  showUsername: {
    type: Boolean,
    default: false,
  },
});

const primaryLabel = computed(() => {
  const fullName = `${props.user?.first_name || ""} ${props.user?.last_name || ""}`.trim();
  return fullName || props.user?.username || props.user?.email || (props.fallbackId ? `User #${props.fallbackId}` : "Unknown user");
});

const secondaryEmail = computed(() => (
  props.user?.email && props.user.email !== primaryLabel.value ? props.user.email : ""
));
</script>
