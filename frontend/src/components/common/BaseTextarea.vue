<template>
  <label class="base-input">
    <span class="base-input__label">{{ label }}</span>
    <textarea
      class="base-input__control base-input__control--textarea"
      :maxlength="maxlength"
      :name="name"
      :placeholder="placeholder"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
    ></textarea>
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
  placeholder: {
    type: String,
    default: "",
  },
  maxlength: {
    type: Number,
    default: 1000,
  },
});

defineEmits(["update:modelValue"]);
</script>
