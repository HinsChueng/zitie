<script setup>
import { computed } from 'vue'

const props = defineProps({ kind: { type: String, required: true } })

const s = 22
const dashed = 'stroke-dasharray="2 2"'
const solid = ''

const parts = computed(() => {
  const k = props.kind
  const box = `<rect x="1" y="1" width="${s - 2}" height="${s - 2}" fill="none"/>`
  const mid = s / 2
  const cross =
    `<line x1="${mid}" y1="1" x2="${mid}" y2="${s - 1}" ${dashed}/>` +
    `<line x1="1" y1="${mid}" x2="${s - 1}" y2="${mid}" ${dashed}/>`
  const diag =
    `<line x1="1" y1="1" x2="${s - 1}" y2="${s - 1}" ${dashed}/>` +
    `<line x1="${s - 1}" y1="1" x2="1" y2="${s - 1}" ${dashed}/>`

  switch (k) {
    case 'tian': return box + cross
    case 'mi': return box + cross + diag
    case 'jiugong': {
      const a = s / 3, b = (s / 3) * 2
      return box +
        `<line x1="${a}" y1="1" x2="${a}" y2="${s - 1}" ${dashed}/>` +
        `<line x1="${b}" y1="1" x2="${b}" y2="${s - 1}" ${dashed}/>` +
        `<line x1="1" y1="${a}" x2="${s - 1}" y2="${a}" ${dashed}/>` +
        `<line x1="1" y1="${b}" x2="${s - 1}" y2="${b}" ${dashed}/>`
    }
    case 'huigong':
      return box + `<rect x="5.5" y="5.5" width="${s - 11}" height="${s - 11}" fill="none"/>`
    case 'blank': return box
    case 'vertical':
      return `<line x1="1" y1="1" x2="1" y2="${s - 1}"/>` +
        `<line x1="${s / 2}" y1="1" x2="${s / 2}" y2="${s - 1}" ${dashed}/>` +
        `<line x1="${s - 1}" y1="1" x2="${s - 1}" y2="${s - 1}"/>`
    case 'line':
      return `<line x1="1" y1="${s / 2}" x2="${s - 1}" y2="${s / 2}"/>` +
        `<line x1="1" y1="${s - 1}" x2="${s - 1}" y2="${s - 1}"/>`
    case 'pinyin4':
      return box +
        `<line x1="1" y1="${s / 3}" x2="${s - 1}" y2="${s / 3}" ${dashed}/>` +
        `<line x1="1" y1="${2 * s / 3}" x2="${s - 1}" y2="${2 * s / 3}" ${dashed}/>`
    case 'composition':
      return box + `<circle cx="${mid}" cy="${mid}" r="1" fill="currentColor" stroke="none"/>`
    case 'control':
      return box +
        `<path d="M2 ${mid} Q5 3 8 ${mid} T14 ${mid} Q17 ${s - 3} 20 ${mid}" fill="none"/>`
    default: return box
  }
})
</script>

<template>
  <svg :width="s" :height="s" viewBox="0 0 22 22" stroke="currentColor" stroke-width="1"
       v-html="parts" />
</template>
