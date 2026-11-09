<script setup>
/** 内容库：选一篇诗文即可开练，标题自动带上，支持搜索与“替换 / 追加”两种用法。 */
import { computed, ref, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  groups: { type: Array, default: () => [] }
})
const emit = defineEmits(['close', 'pick'])

const era = ref('全部')
const active = ref('全部')
const keyword = ref('')

const ERAS = ['全部', '古代', '现代']

// 组与篇目都带 era；老版本后端没这个字段时按“古代”兜底，不至于整库消失
const flat = computed(() => props.groups.flatMap(g =>
  (g.items || []).map(it => ({ ...it, category: g.name, era: it.era || g.era || '古代' }))
))
const erasPresent = computed(() => new Set(flat.value.map(it => it.era)))

const eraTabs = computed(() => [
  { name: '全部', count: flat.value.length },
  { name: '古代', count: flat.value.filter(it => it.era === '古代').length },
  { name: '现代', count: flat.value.filter(it => it.era === '现代').length }
].filter(t => t.name === '全部' || erasPresent.value.has(t.name)))

const visibleGroups = computed(() =>
  era.value === '全部' ? props.groups : props.groups.filter(g => (g.era || '古代') === era.value)
)

const categories = computed(() => [
  { name: '全部', count: visibleGroups.value.reduce((n, g) => n + (g.items || []).length, 0) },
  ...visibleGroups.value.map(g => ({ name: g.name, count: (g.items || []).length }))
])

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return flat.value.filter(it => {
    if (era.value !== '全部' && it.era !== era.value) return false
    if (active.value !== '全部' && it.category !== active.value) return false
    if (!kw) return true
    return (it.title + it.author + it.text + it.note + it.category).toLowerCase().includes(kw)
  })
})

// 切时代后，左侧细分类若已不在新列表里，回到“全部”，避免出现空白列表
watch(era, () => {
  if (!categories.value.some(c => c.name === active.value)) active.value = '全部'
})

function use(item, mode) {
  emit('pick', { item, mode })
}
</script>

<template>
  <div v-if="open" class="mask" @click.self="emit('close')">
    <div class="modal">
      <div class="modal-side">
        <div class="side-title">内容库</div>
        <button
          v-for="c in categories"
          :key="c.name"
          :class="{ on: active === c.name }"
          @click="active = c.name"
        >
          <b>{{ c.name }}</b>
          <small>{{ c.count }} 篇</small>
        </button>
      </div>

      <div class="modal-main">
        <div class="era-bar">
          <span class="era-label">时代</span>
          <button v-for="t in eraTabs" :key="t.name" :class="{ on: era === t.name }"
                  @click="era = t.name">
            {{ t.name }}<small>{{ t.count }} 篇</small>
          </button>
          <span class="hint era-tip">{{ era === '全部' ? '古今兼练' : (era === '古代' ? '典籍、史传与诗文' : '白话散文与新诗') }}</span>
        </div>
        <header>
          <div style="display:flex;align-items:center;gap:8px;flex:1;min-width:0">
            <input v-model="keyword" class="lib-search" type="search" placeholder="搜标题、作者或正文…" />
            <span class="hint">{{ filtered.length }} 篇</span>
          </div>
          <button class="btn" @click="emit('close')">关闭</button>
        </header>

        <div class="passage-list">
          <div v-for="it in filtered" :key="it.id" class="passage-card">
            <div class="passage-head">
              <strong>{{ it.title }}</strong>
              <span v-if="it.author" class="hint">{{ it.author }}</span>
            </div>
            <div class="passage-meta">
              <span class="era-tag" :class="it.era === '现代' ? 'modern' : 'ancient'">{{ it.era }}</span>
              {{ it.category }} · {{ it.count }} 字 · {{ it.note }}
              <span v-if="it.level" class="level-tag" :title="`难度 ${it.level} 星`">{{ '★'.repeat(it.level) }}</span>
            </div>
            <p class="passage-text">{{ it.text }}</p>
            <div class="passage-actions">
              <button class="btn primary" @click="use(it, 'replace')">用这篇</button>
              <button class="btn ghost" @click="use(it, 'append')">追加</button>
            </div>
          </div>
          <p v-if="!filtered.length" class="hint" style="padding:20px">没有匹配的篇目，换个词试试</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.era-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap;
}
.era-label { font-size: 12px; letter-spacing: .08em; color: var(--muted); margin-right: 2px; }
.era-bar button {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  height: 30px;
  padding: 0 13px;
  border: 1px solid var(--line-strong);
  border-radius: 20px;
  background: var(--panel);
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
  transition: .15s;
}
.era-bar button:hover { border-color: var(--accent); }
.era-bar button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.era-bar button small { color: var(--muted); font-size: 11px; }
.era-bar button.on small { color: rgba(255, 255, 255, .78); }
.era-tip { margin-left: 4px; }
.era-tag {
  display: inline-block;
  margin-right: 5px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10.5px;
  border: 1px solid #d9b26a;
  color: #8a6023;
  background: #fdf5e4;
}
.era-tag.modern { border-color: #7ba7c4; color: #2b6187; background: #eaf4fa; }
[data-theme="dark"] .era-tag { background: #3a3020; border-color: #6b5732; color: #e3c58c; }
[data-theme="dark"] .era-tag.modern { background: #20323c; border-color: #3c6a85; color: #a9d2e8; }
.side-title {
  padding: 4px 10px 10px;
  font-size: 12px;
  letter-spacing: .08em;
  color: var(--muted);
}
.lib-search {
  max-width: 320px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: var(--panel);
  color: var(--text);
  outline: none;
}
.lib-search:focus { border-color: var(--accent); }
.passage-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 14px 18px 22px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 10px;
  align-content: start;
}
.passage-card {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 12px;
  background: var(--panel);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.passage-card:hover { border-color: var(--accent); }
.passage-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.passage-head strong { font-size: 14px; font-weight: 600; }
.passage-meta { color: var(--muted); font-size: 11.5px; }
.level-tag { color: var(--accent); margin-left: 6px; letter-spacing: 1px; }
.passage-text {
  margin: 2px 0 6px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--text);
  opacity: .82;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.passage-actions { display: flex; gap: 6px; margin-top: auto; }
.passage-actions .btn { height: 28px; flex: 1; padding: 0 8px; font-size: 12px; }
</style>
