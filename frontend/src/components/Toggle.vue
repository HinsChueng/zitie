<script setup>
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  label: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  hint: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue'])

function toggle() {
  if (props.disabled) return
  emit('update:modelValue', !props.modelValue)
}
</script>

<template>
  <div
    class="switch"
    :class="{ on: modelValue, off: disabled }"
    :title="disabled ? hint : ''"
    @click="toggle"
  >
    <span>{{ label }}</span>
    <i />
  </div>
</template>
