<script setup>
/**
 * 字库选择：每款字体用自身字样渲染一个小样，直接看效果再选。
 * 图标走 /api/fonts/{id}/sample，由后端用该字体画「永字」两个字。
 */
import { nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  fonts: { type: Array, default: () => [] },
  sample: { type: String, default: '永字' }
})
const emit = defineEmits(['update:modelValue'])

const grid = ref(null)

function src(font) {
  return `/api/fonts/${encodeURIComponent(font.id)}/sample?text=${encodeURIComponent(props.sample)}&size=64`
}

function pick(font) {
  emit('update:modelValue', font.id)
}

// 选中项可能滚动在视野外，切换字体后把它带进来（只动这一层，不牵动整页）
function revealSelection() {
  const box = grid.value
  const card = box?.querySelector('.font-card.on')
  if (!box || !card) return
  const top = card.offsetTop
  const bottom = top + card.offsetHeight
  if (top < box.scrollTop) box.scrollTop = Math.max(0, top - 4)
  else if (bottom > box.scrollTop + box.clientHeight) box.scrollTop = bottom - box.clientHeight + 4
}

onMounted(() => nextTick(revealSelection))
watch(() => props.modelValue, () => nextTick(revealSelection))
</script>

<template>
  <div ref="grid" class="font-grid">
    <button
      v-for="f in fonts"
      :key="f.id"
      type="button"
      class="font-card"
      :class="{ on: modelValue === f.id }"
      :title="`${f.name} · ${f.source === 'bundled' ? '内置' : '系统'} · 常用字 ${f.coverage}%`"
      @click="pick(f)"
    >
      <img class="font-sample" :src="src(f)" :alt="f.name" loading="lazy" />
      <span class="font-name">{{ f.name }}</span>
      <span class="font-badge" v-if="f.style">{{ f.style }}</span>
      <span class="font-badge sys" v-if="f.source === 'system'">系统</span>
    </button>
    <p v-if="!fonts.length" class="hint" style="grid-column: 1 / -1">
      没有找到可用字体，请往 backend/fonts 放一个 ttf，或点下面的「重新扫描」。
    </p>
  </div>
</template>

<style scoped>
.font-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  max-height: 224px;
  overflow-y: auto;
  padding-right: 2px;
  position: relative;
}
.font-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  height: 76px;
  padding: 8px 4px 5px;
  border: 1px solid var(--line-strong);
  border-radius: 9px;
  background: #fff;
  cursor: pointer;
  transition: .14s;
  overflow: hidden;
}
.font-card:hover { border-color: var(--muted); }
.font-card.on {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.font-sample {
  flex: 1;
  min-height: 0;
  width: auto;
  max-width: 100%;
  object-fit: contain;
  opacity: .82;
}
.font-card.on .font-sample { opacity: 1; }
.font-name {
  font-size: 11px;
  color: var(--text);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.font-badge {
  position: absolute;
  top: 3px;
  left: 4px;
  font-size: 10px;
  line-height: 1.4;
  padding: 0 4px;
  border-radius: 4px;
  background: #f0eee8;
  color: var(--muted);
}
.font-card.on .font-badge { background: #fff; color: var(--accent); }
.font-badge.sys { left: auto; right: 4px; background: transparent; padding: 0; }
</style>
