<script setup>
import { ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({
  open: { type: Boolean, default: false },
  charsets: { type: Array, default: () => [] }
})
const emit = defineEmits(['close', 'pick'])

const active = ref('')
const chars = ref('')
const loading = ref(false)
const error = ref('')

async function select(id) {
  if (!id) return
  active.value = id
  loading.value = true
  error.value = ''
  try {
    const data = await api.charset(id)
    chars.value = data.chars || ''
  } catch (e) {
    error.value = e.message
    chars.value = ''
  } finally {
    loading.value = false
  }
}

watch(() => props.open, (v) => {
  if (v && props.charsets.length && !active.value) select(props.charsets[0].id)
})

function pickAll() {
  if (chars.value) emit('pick', chars.value)
}
</script>

<template>
  <div v-if="open" class="mask" @click.self="emit('close')">
    <div class="modal">
      <div class="modal-side">
        <button
          v-for="c in charsets"
          :key="c.id"
          :class="{ on: active === c.id }"
          @click="select(c.id)"
        >
          <b>{{ c.name }}</b>
          <small>{{ c.count }} 字 · {{ c.desc }}</small>
        </button>
      </div>

      <div class="modal-main">
        <header>
          <span class="hint">点任意字追加到正文末尾</span>
          <div style="display:flex; gap:8px; align-items:center">
            <button class="btn ghost" :disabled="!chars" @click="pickAll">整表加入</button>
            <button class="btn" @click="emit('close')">关闭</button>
          </div>
        </header>

        <div class="chars">
          <span v-if="loading" class="hint" style="grid-column: 1/-1">加载中…</span>
          <span v-else-if="error" class="hint" style="grid-column: 1/-1">{{ error }}</span>
          <button
            v-for="(ch, i) in chars"
            :key="i + ch"
            type="button"
            @click="emit('pick', ch)"
          >{{ ch }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
