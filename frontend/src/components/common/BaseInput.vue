<template>
  <label class="base-input">
    <span :id="`${name}-label`" class="base-input__label">{{ label }}</span>
    <input
      class="base-input__control"
      :autocomplete="autocomplete"
      :aria-describedby="hint ? `${name}-hint` : undefined"
      :aria-labelledby="`${name}-label`"
      :min="min"
      :name="name"
      :placeholder="placeholder"
      :required="required"
      :step="step"
      :type="type"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
    />
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
