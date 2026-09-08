<template>
  <label class="base-input">
    <span :id="`${name}-label`" class="base-input__label">{{ label }}</span>
    <textarea
      class="base-input__control base-input__control--textarea"
      :aria-describedby="hint ? `${name}-hint` : undefined"
      :aria-labelledby="`${name}-label`"
      :maxlength="maxlength"
      :name="name"
      :placeholder="placeholder"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
    ></textarea>
    <span v-if="hint" :id="`${name}-hint`" class="form-helper">{{ hint }}</span>
  </label>
</template>

<script setup>
defineProps({
  hint: { type: String, default: "" },
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
