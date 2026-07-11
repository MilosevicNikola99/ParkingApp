<template>
  <div class="confirm-action">
    <BaseButton
      v-if="!isConfirming"
      :disabled="disabled"
      size="compact"
      variant="danger"
      @click="isConfirming = true"
    >
      {{ actionLabel }}
    </BaseButton>
    <template v-else>
      <span class="confirm-action__prompt">{{ prompt }}</span>
      <BaseButton :loading="loading" size="compact" variant="danger" @click="confirm">
        Confirm
      </BaseButton>
      <BaseButton :disabled="loading" size="compact" variant="secondary" @click="isConfirming = false">
        Cancel
      </BaseButton>
    </template>
  </div>
</template>

<script setup>
import { ref } from "vue";

import BaseButton from "@/components/common/BaseButton.vue";

defineProps({
  actionLabel: {
    type: String,
    default: "Delete",
  },
  prompt: {
    type: String,
    default: "Delete this record?",
  },
  loading: {
    type: Boolean,
    default: false,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["confirm"]);
const isConfirming = ref(false);

function confirm() {
  emit("confirm");
}
</script>
