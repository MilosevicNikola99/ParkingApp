<template>
  <label class="base-input">
    <span class="base-input__label">{{ label }}</span>
    <select
      class="base-input__control"
      :disabled="disabled"
      :name="name"
      :required="required"
      :value="modelValue"
      @change="$emit('update:modelValue', $event.target.value)"
    >
      <option v-if="placeholder" value="">{{ placeholder }}</option>
      <option v-for="option in options" :key="String(option.value)" :value="option.value">
        {{ option.label }}
      </option>
    </select>
  </label>
</template>

<script setup>
defineProps({
  modelValue: {
    type: [String, Number, Boolean],
    default: "",
  },
  label: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  options: {
    type: Array,
    required: true,
  },
  placeholder: {
    type: String,
    default: "",
  },
  required: {
    type: Boolean,
    default: false,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["update:modelValue"]);
</script>
