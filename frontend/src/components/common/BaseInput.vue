<template>
  <label class="base-input">
    <span class="base-input__label">{{ label }}</span>
    <input
      class="base-input__control"
      :autocomplete="autocomplete"
      :min="min"
      :name="name"
      :placeholder="placeholder"
      :required="required"
      :step="step"
      :type="type"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
    />
  </label>
</template>

<script setup>
defineProps({
  modelValue: {
    type: String,
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
  type: {
    type: String,
    default: "text",
  },
  autocomplete: {
    type: String,
    default: "off",
  },
  placeholder: {
    type: String,
    default: "",
  },
  min: {
    type: String,
    default: undefined,
  },
  step: {
    type: String,
    default: undefined,
  },
  required: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["update:modelValue"]);
</script>
