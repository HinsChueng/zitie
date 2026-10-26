<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, required: true }
})
defineEmits(['update:modelValue'])
</script>

<template>
  <div class="seg">
    <button
      v-for="o in options"
      :key="o.value"
      type="button"
      :class="{ on: modelValue === o.value }"
      @click="$emit('update:modelValue', o.value)"
    >{{ o.label }}</button>
  </div>
</template>
