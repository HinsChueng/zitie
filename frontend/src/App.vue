<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from './api'
import Seg from './components/Seg.vue'
import Toggle from './components/Toggle.vue'
import GridIcon from './components/GridIcon.vue'
import CharPicker from './components/CharPicker.vue'
import FontPicker from './components/FontPicker.vue'

const meta = ref({ fonts: [], charsets: [], grids: [], page_sizes: [], defaults: {}, capabilities: {} })
const params = reactive({})
const state = reactive({
  image: '',
  pages: 1,
  chars: 0,
  warnings: [],
  page: 0,
  busy: false,
  exporting: false,
  scanning: false,
  error: ''
})

const pickerOpen = ref(false)
const splitSize = ref(100)
const fileInput = ref(null)
const fontInput = ref(null)

const MODES = [
  { value: 'demo', label: '全示范' },
  { value: 'trace', label: '全描红' },
  { value: 'mixed', label: '行内三段' },
  { value: 'rotate', label: '三行循环' }
]
const TRACES = [
  { value: 'gray', label: '浅灰' },
  { value: 'outline', label: '空心' },
  { value: 'dot', label: '点阵' }
]

const isMixed = computed(() => params.mode === 'mixed')
const isRotate = computed(() => params.mode === 'rotate')
const textLen = computed(() => (params.text || '').replace(/\s/g, '').length)
const currentFont = computed(() => meta.value.fonts.find(f => f.id === params.font_id) || null)
// 后端没装 zhconv 时「转繁体」点了不会有任何变化，不如直接置灰并说明原因
const canTraditional = computed(() => meta.value.capabilities?.traditional !== false)

/* ---------------- 预览 ---------------- */
let timer = null
let seq = 0

async function refresh() {
  if (!params.text && !params.title) {
    state.image = ''
    state.pages = 1
    state.warnings = []
    return
  }
  const mine = ++seq
  state.busy = true
  state.error = ''
  try {
    const data = await api.preview({ ...params }, state.page)
    if (mine !== seq) return          // 丢弃过期响应，避免快速拖动时闪回
    state.image = data.image
    state.pages = data.pages
    state.chars = data.char_count
    state.warnings = data.warnings || []
    if (state.page > data.pages - 1) state.page = data.pages - 1
  } catch (e) {
    if (mine === seq) state.error = e.message
  } finally {
    if (mine === seq) state.busy = false
  }
}

function schedule() {
  clearTimeout(timer)
  timer = setTimeout(refresh, 260)
}

watch(params, schedule, { deep: true })
watch(() => state.page, refresh)

/* ---------------- 动作 ---------------- */
function fillFromCharset(chars) {
  params.text = (params.text || '') + chars
  state.page = 0
}

async function onFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    const data = await api.parseFile(file)
    params.text = data.text
    state.page = 0
  } catch (err) {
    state.error = err.message
  } finally {
    e.target.value = ''
  }
}

async function onFont(e) {
  const file = e.target.files?.[0]
  if (!file) return
  state.error = ''
  state.scanning = true
  try {
    const data = await api.uploadFont(file)
    const list = await api.fonts(true)
    meta.value = { ...meta.value, fonts: list.fonts }
    if (data.font?.id) params.font_id = data.font.id
  } catch (err) {
    state.error = err.message
  } finally {
    state.scanning = false
    e.target.value = ''
  }
}

async function rescanFonts() {
  state.scanning = true
  state.error = ''
  try {
    const list = await api.fonts(true)
    meta.value = { ...meta.value, fonts: list.fonts }
    if (!list.fonts.some(f => f.id === params.font_id) && list.fonts.length) {
      params.font_id = list.fonts[0].id
    }
  } catch (err) {
    state.error = err.message
  } finally {
    state.scanning = false
  }
}

function download(blob, name) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

async function exportSheet(split = false) {
  if (!params.text) return
  state.exporting = true
  state.error = ''
  try {
    const { blob, name } = await api.exportSheet({ ...params }, split ? splitSize.value : 0)
    download(blob, name)
  } catch (e) {
    state.error = e.message
  } finally {
    state.exporting = false
  }
}

async function printPage() {
  if (!params.text) return
  state.busy = true
  try {
    const data = await api.preview({ ...params }, state.page, true)
    const win = window.open('', '_blank')
    if (!win) throw new Error('浏览器拦截了新窗口，请允许弹窗')
    win.document.write(
      `<title>打印字帖</title><style>@page{margin:0}body{margin:0}img{width:100%;display:block}</style>` +
      `<img src="${data.image}" onload="window.focus();window.print()">`
    )
    win.document.close()
  } catch (e) {
    state.error = e.message
  } finally {
    state.busy = false
  }
}

onMounted(async () => {
  try {
    const data = await api.meta()
    meta.value = data
    Object.assign(params, data.defaults)
    if (!params.text) {
      params.title = '静夜思'
      params.text = '床前明月光，疑是地上霜。举头望明月，低头思故乡。'
    }
    await refresh()
  } catch (e) {
    state.error = `无法连接后端：${e.message}`
  }
})
</script>

<template>
  <header class="topbar">
    <div class="brand">
      <strong>字帖工坊</strong>
      <span>硬笔字帖生成 · 版式引擎</span>
    </div>

    <div class="actions">
      <button class="btn ghost" @click="pickerOpen = true">字表</button>
      <button class="btn ghost" :disabled="!params.text" @click="printPage">打印</button>
      <button class="btn primary" :disabled="!params.text || state.exporting" @click="exportSheet(false)">
        {{ state.exporting ? '生成中…' : '导出 PDF' }}
      </button>
      <input v-model.number="splitSize" class="split-input" type="number" min="20" max="2000" step="10" title="每册字数" />
      <button class="btn" :disabled="!params.text || state.exporting" @click="exportSheet(true)">分册</button>
    </div>
  </header>

  <div class="layout">
    <!-- ---------------- 控制面板 ---------------- -->
    <aside class="panel">
      <div class="section">
        <div class="section-head">
          <h3>内容</h3>
          <span class="hint">{{ textLen }} 字</span>
        </div>
        <div class="field">
          <label>标题</label>
          <input v-model="params.title" type="text" placeholder="例如：静夜思（留空不显示）" />
        </div>
        <div class="field">
          <label>正文</label>
          <textarea v-model="params.text" placeholder="粘贴任意中文内容，标点、换行都会按规则处理"></textarea>
        </div>
        <div class="row">
          <button class="btn ghost" @click="fileInput?.click()">导入 txt</button>
          <button class="btn ghost" @click="pickerOpen = true">从字表选字</button>
          <button class="btn ghost" @click="params.text = ''">清空</button>
        </div>
        <input ref="fileInput" type="file" accept=".txt,.md,.csv" hidden @change="onFile" />
      </div>

      <div class="section">
        <div class="section-head">
          <h3>字库</h3>
          <span class="hint">{{ meta.fonts.length }} 款可用</span>
        </div>
        <FontPicker v-model="params.font_id" :fonts="meta.fonts" />
        <p class="font-meta">
          <template v-if="currentFont">
            {{ currentFont.name }} ·
            {{ currentFont.source === 'bundled' ? '内置' : '系统已装' }} ·
            常用字 {{ currentFont.coverage }}%
            <template v-if="currentFont.glyphs"> · {{ currentFont.glyphs }} 字形</template>
          </template>
          <template v-else>当前字体不可用，已自动回退</template>
        </p>
        <Toggle v-model="params.font_fallback" label="缺字自动借用其他字体" />
        <div class="row" style="margin-top:8px">
          <button class="btn ghost" :disabled="state.scanning" @click="fontInput?.click()">上传字体</button>
          <button class="btn ghost" :disabled="state.scanning" @click="rescanFonts">
            {{ state.scanning ? '扫描中…' : '重新扫描' }}
          </button>
        </div>
        <input ref="fontInput" type="file" accept=".ttf,.otf,.ttc" hidden @change="onFont" />
      </div>

      <div class="section">
        <div class="section-head"><h3>练习模式</h3></div>
        <Seg v-model="params.mode" :options="MODES" />

        <div v-if="isMixed" style="margin-top:12px">
          <div class="row">
            <div class="field">
              <label>示范格数</label>
              <input v-model.number="params.demo_cells" type="number" min="0" max="10" />
            </div>
            <div class="field">
              <label>描红格数</label>
              <input v-model.number="params.trace_cells" type="number" min="0" max="10" />
            </div>
          </div>
          <Toggle v-model="params.repeat" label="单字重复整行（一行练一个字）" />
        </div>

        <div v-if="isRotate" style="margin-top:12px">
          <div class="row">
            <div class="field">
              <label>示范行</label>
              <input v-model.number="params.cycle_demo" type="number" min="1" max="4" />
            </div>
            <div class="field">
              <label>描红行</label>
              <input v-model.number="params.cycle_trace" type="number" min="1" max="4" />
            </div>
            <div class="field">
              <label>空白行</label>
              <input v-model.number="params.cycle_blank" type="number" min="0" max="6" />
            </div>
          </div>
        </div>

        <p class="hint" style="margin:10px 0 0">
          <template v-if="isMixed">每行先看示范，再描，剩下空格自己写。</template>
          <template v-else-if="isRotate">一行示范一行描红，隔几行空白，最适合整篇临写。</template>
          <template v-else-if="params.mode === 'demo'">整页实心范字，用于对临。</template>
          <template v-else>整页描红，直接下笔。</template>
        </p>
      </div>

      <div class="section">
        <div class="section-head"><h3>描红样式</h3></div>
        <Seg v-model="params.trace_style" :options="TRACES" />
        <div v-if="params.trace_style === 'gray'" class="field" style="margin-top:12px">
          <label>浓度 <b>{{ Math.round(params.trace_opacity * 100) }}%</b></label>
          <input v-model.number="params.trace_opacity" type="range" min="0.05" max="0.8" step="0.01" />
        </div>
      </div>

      <div class="section">
        <div class="section-head"><h3>版式</h3></div>

        <div class="field">
          <label>格型</label>
          <div class="grid-picker">
            <button
              v-for="g in meta.grids"
              :key="g.id"
              type="button"
              :class="{ on: params.grid === g.id }"
              @click="params.grid = g.id"
            >
              <GridIcon :kind="g.id" />
              {{ g.name }}
            </button>
          </div>
        </div>

        <div class="row">
          <div class="field">
            <label>纸张</label>
            <select v-model="params.page_size">
              <option v-for="p in meta.page_sizes" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="field">
            <label>每行字数</label>
            <input v-model.number="params.columns" type="number" min="1" max="20" />
          </div>
        </div>

        <div class="field">
          <label>格子边长 <b>{{ Number(params.cell_mm).toFixed(1) }} mm</b></label>
          <input v-model.number="params.cell_mm" type="range" min="8" max="30" step="0.5" />
        </div>

        <div class="row">
          <div class="field">
            <label>字号 / 格 比 <b>{{ Math.round((params.font_ratio || 0) * 100) }}%</b></label>
            <input v-model.number="params.font_ratio" type="range" min="0.5" max="1" step="0.02" />
          </div>
          <div class="field">
            <label>页边距 <b>{{ params.margin_mm }} mm</b></label>
            <input v-model.number="params.margin_mm" type="range" min="5" max="40" step="1" />
          </div>
        </div>

        <Toggle v-model="params.auto_rows" label="自动铺满整页" />
        <div v-if="!params.auto_rows" class="field" style="margin-top:8px">
          <label>每页行数</label>
          <input v-model.number="params.rows" type="number" min="1" max="26" />
        </div>
      </div>

      <div class="section">
        <div class="section-head"><h3>外观</h3></div>
        <div class="row" style="align-items:center">
          <div style="display:flex; align-items:center; gap:8px">
            <input v-model="params.grid_color" type="color" />
            <span class="hint">格线</span>
          </div>
          <div style="display:flex; align-items:center; gap:8px">
            <input v-model="params.font_color" type="color" />
            <span class="hint">字色</span>
          </div>
        </div>
        <Toggle v-model="params.show_header" label="显示标题与页码" />
      </div>

      <div class="section">
        <div class="section-head"><h3>文本处理</h3></div>
        <Toggle v-model="params.keep_punct" label="保留标点" />
        <Toggle v-model="params.break_at_punct" label="按标点断句（诗句更整齐）" />
        <Toggle
          v-model="params.traditional"
          label="转繁体（标题一起转）"
          :disabled="!canTraditional"
          hint="后端未安装 zhconv，转繁体不可用：pip install zhconv"
        />
        <Toggle v-model="params.line_break_rule" label="避头尾禁则" />
        <p v-if="!canTraditional" class="hint" style="margin:6px 0 0">
          转繁体需要后端安装 zhconv（pip install zhconv），当前已禁用。
        </p>
      </div>
    </aside>

    <!-- ---------------- 预览 ---------------- -->
    <section class="stage">
      <div class="stage-bar">
        <div>
          <template v-if="state.image">
            共 <b>{{ state.pages }}</b> 页 · 正文 <b>{{ state.chars }}</b> 格
            <span v-if="state.busy" style="margin-left:8px">渲染中…</span>
          </template>
          <span v-else>左侧输入正文，右侧即时预览</span>
        </div>
        <div v-if="state.pages > 1" class="pager">
          <button :disabled="state.page <= 0" @click="state.page--">‹</button>
          <b>{{ state.page + 1 }} / {{ state.pages }}</b>
          <button :disabled="state.page >= state.pages - 1" @click="state.page++">›</button>
        </div>
      </div>

      <div v-if="state.error" class="warnings" style="background:#fdecea;border-color:#f3c2bd;color:#a02a1c">
        {{ state.error }}
      </div>
      <div v-if="state.warnings.length" class="warnings">
        <div v-for="(w, i) in state.warnings" :key="i">{{ w }}</div>
      </div>

      <div class="canvas">
        <div v-if="state.image" class="page">
          <img :src="state.image" alt="字帖预览" />
        </div>
        <div v-else class="empty">
          还没有内容<br />
          粘贴一段诗文，或点「字表」挑几百个常用字试试
        </div>
      </div>
    </section>
  </div>

  <CharPicker
    :open="pickerOpen"
    :charsets="meta.charsets"
    @close="pickerOpen = false"
    @pick="fillFromCharset"
  />
</template>
