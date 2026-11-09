<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api, engineMode } from './api'
import { encodeConfig, decodeConfig, parseHash } from './share'
import Seg from './components/Seg.vue'
import Toggle from './components/Toggle.vue'
import GridIcon from './components/GridIcon.vue'
import CharPicker from './components/CharPicker.vue'
import FontPicker from './components/FontPicker.vue'
import LibraryPicker from './components/LibraryPicker.vue'
import TemplateDrawer from './components/TemplateDrawer.vue'

const LS_PARAMS = 'zitie.params.v2'
const LS_TPL = 'zitie.templates.v2'
const LS_THEME = 'zitie.theme.v2'
const LS_PAGESPEC = 'zitie.pagespec.v2'
const PAGE_MM = { A4: [210, 297], A5: [148, 210], B5: [176, 250] }

const meta = ref({ fonts: [], charsets: [], library: [], grids: [], page_sizes: [], defaults: {}, capabilities: {} })
const params = reactive({})
const state = reactive({
  image: '', pages: 1, chars: 0, warnings: [], page: 0,
  busy: false, exporting: false, scanning: false, error: '',
  thumbs: [], thumbsTotal: 0, thumbsTruncated: false, thumbsLoading: false
})
const ui = reactive({ theme: 'light', zoom: 1, toast: '', tab: 'content', engine: 'server' })

const analysis = ref(null)
const panelEl = ref(null)
const pickerOpen = ref(false)
const libraryOpen = ref(false)
const templateOpen = ref(false)
const templateTab = ref('templates')
const shareUrl = ref('')
const templates = ref([])
const splitSize = ref(100)
const exportFormat = ref('pdf')
const pageRange = ref('')
const pageHistory = ref([])
const fileInput = ref(null)
const fontInput = ref(null)
const canvasEl = ref(null)
const box = reactive({ w: 900, h: 700 })

const TABS = [
  { id: 'content', label: '内容', hint: '写什么' },
  { id: 'glyph', label: '字形', hint: '怎么练' },
  { id: 'layout', label: '版式', hint: '怎么排' },
  { id: 'output', label: '输出', hint: '怎么导出' }
]
const DIRECTIONS = [
  { value: 'horizontal', label: '横排' },
  { value: 'vertical', label: '竖排' }
]
const MODES = [
  { value: 'demo', label: '全示范' },
  { value: 'trace', label: '全描红' },
  { value: 'mixed', label: '行内三段' },
  { value: 'rotate', label: '三行循环' },
  { value: 'copy', label: '对临' },
  { value: 'fade', label: '渐隐' },
  { value: 'card', label: '生字卡' }
]
const TRACES = [
  { value: 'gray', label: '浅灰' },
  { value: 'outline', label: '空心' },
  { value: 'dot', label: '点阵' }
]
const FORMATS = [
  { value: 'pdf', label: 'PDF' },
  { value: 'png', label: 'PNG 图片' }
]
const PRESETS = [
  { id: 'normal', name: '朱砂', paper: '#FFFFFF', grid: '#d94a4a', font: '#1f1f1f' },
  { id: 'green', name: '竹青', paper: '#FFFFFF', grid: '#4a7c59', font: '#1f1f1f' },
  { id: 'ink', name: '墨黑', paper: '#FFFFFF', grid: '#333333', font: '#1f1f1f' },
  { id: 'stele', name: '碑帖', paper: '#1B1A18', grid: '#8C8577', font: '#F2EDE3' }
]

const isMixed = computed(() => params.mode === 'mixed')
const isRotate = computed(() => params.mode === 'rotate')
const isCopy = computed(() => params.mode === 'copy')
const isFade = computed(() => params.mode === 'fade')
const isCard = computed(() => params.mode === 'card')
const isVertical = computed(() => params.direction === 'vertical')
const textLen = computed(() => (params.text || '').replace(/\s/g, '').length)
const currentFont = computed(() => meta.value.fonts.find(f => f.id === params.font_id) || null)
const canTraditional = computed(() => meta.value.capabilities?.traditional !== false)
const aspect = computed(() => {
  const [w, h] = PAGE_MM[params.page_size] || PAGE_MM.A4
  return w / h
})
// 以预览区实际可用空间为基准，超宽屏也把 A4 页铺满高度，而不是挤成中间一条窄列
const baseWidth = computed(() => Math.max(240, Math.min(box.w - 56, (box.h - 44) * aspect.value)))
const displayWidth = computed(() => Math.round(baseWidth.value * ui.zoom))

let ready = false
let timer = null
let saveTimer = null
let thumbTimer = null
let toastTimer = null
let analyzeTimer = null
let seq = 0
let thumbSeq = 0
let observer = null

/* ---------------- 预览 ---------------- */
async function refresh() {
  if (!params.text && !params.title) {
    state.image = ''
    state.pages = 1
    state.warnings = []
    state.thumbs = []
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
    scheduleThumbs()
  } catch (e) {
    if (mine === seq) state.error = e.message
  } finally {
    if (mine === seq) state.busy = false
  }
}

async function loadThumbs() {
  if (!params.text) return
  const mine = ++thumbSeq
  state.thumbsLoading = true
  try {
    const data = await api.thumbnails({ ...params }, 150, 40)
    if (mine !== thumbSeq) return
    state.thumbs = data.thumbs || []
    state.thumbsTotal = data.total || 0
    state.thumbsTruncated = !!data.truncated
  } catch (_) {
    // 缩略图只是导航辅助，失败不打断主预览
  } finally {
    if (mine === thumbSeq) state.thumbsLoading = false
  }
}

function schedule() {
  clearTimeout(timer)
  timer = setTimeout(refresh, 260)
}
function scheduleThumbs() {
  clearTimeout(thumbTimer)
  thumbTimer = setTimeout(loadThumbs, 600)
}
function scheduleSave() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    try { localStorage.setItem(LS_PARAMS, JSON.stringify({ ...params })) } catch (_) { /* 存储不可用则忽略 */ }
  }, 400)
}

/* ---------------- 难度与推荐（离线计算，失败不影响主流程） ---------------- */
async function runAnalysis() {
  if (!params.text) { analysis.value = null; return }
  try {
    analysis.value = await api.analyze(params.text, params.title || '', params.keep_punct)
  } catch (_) {
    analysis.value = null
  }
}
function scheduleAnalyze() {
  clearTimeout(analyzeTimer)
  analyzeTimer = setTimeout(runAnalysis, 700)
}
function useRecommend(item) {
  params.title = item.title + (item.author ? ` · ${item.author}` : '')
  params.text = item.text
  state.page = 0
  toast(`已换成“${item.title}”`)
}
function setTab(id) {
  ui.tab = id
  if (panelEl.value) panelEl.value.scrollTop = 0
}

watch(params, () => {
  if (!ready) return
  schedule()
  scheduleSave()
}, { deep: true })
watch([() => params.text, () => params.title, () => params.keep_punct], scheduleAnalyze)
watch(() => state.page, () => { if (ready) refresh() })
watch(() => ui.theme, (v) => {
  document.documentElement.dataset.theme = v
  try { localStorage.setItem(LS_THEME, v) } catch (_) { /* 忽略 */ }
})

/* ---------------- 小工具 ---------------- */
function toast(msg) {
  ui.toast = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { ui.toast = '' }, 2200)
}

function download(blob, name) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

function measure() {
  const el = canvasEl.value
  if (!el) return
  box.w = el.clientWidth
  box.h = el.clientHeight
}

function onKey(e) {
  const tag = (e.target?.tagName || '').toLowerCase()
  if (['input', 'textarea', 'select'].includes(tag)) return
  if (e.key === 'ArrowLeft') state.page = Math.max(0, state.page - 1)
  else if (e.key === 'ArrowRight') state.page = Math.min(state.pages - 1, state.page + 1)
  else if (e.key === '+' || e.key === '=') ui.zoom = Math.min(2.5, +(ui.zoom + 0.1).toFixed(2))
  else if (e.key === '-') ui.zoom = Math.max(0.4, +(ui.zoom - 0.1).toFixed(2))
  else return
  e.preventDefault()
}

/* ---------------- 内容 ---------------- */
function fillFromCharset(chars) {
  params.text = (params.text || '') + chars
  state.page = 0
}

function pickPassage({ item, mode }) {
  if (mode === 'append') {
    params.text = (params.text || '') + item.text
  } else {
    params.title = item.title + (item.author ? ` · ${item.author}` : '')
    params.text = item.text
  }
  state.page = 0
  libraryOpen.value = false
  toast(mode === 'append' ? '已追加到正文' : `已载入“${item.title}”`)
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

/* ---------------- 字库 ---------------- */
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

/* ---------------- 外观 ---------------- */
function applyPreset(p) {
  params.paper_color = p.paper
  params.grid_color = p.grid
  params.font_color = p.font
}

/* ---------------- 模板与分享 ---------------- */
function loadTemplates() {
  try {
    const list = JSON.parse(localStorage.getItem(LS_TPL) || '[]')
    templates.value = Array.isArray(list) ? list : []
  } catch (_) { templates.value = [] }
}
function persistTemplates() {
  try { localStorage.setItem(LS_TPL, JSON.stringify(templates.value)) } catch (_) { /* 忽略 */ }
}
function saveTemplate(name) {
  templates.value.unshift({
    id: `t${Date.now()}`, name, params: { ...params },
    at: new Date().toLocaleString('zh-CN')
  })
  persistTemplates()
  toast(`已保存“${name}”`)
}
function applyTemplate(id) {
  const t = templates.value.find(x => x.id === id)
  if (!t) return
  Object.assign(params, t.params)
  state.page = 0
  templateOpen.value = false
  toast(`已套用“${t.name}”`)
}
function removeTemplate(id) {
  templates.value = templates.value.filter(x => x.id !== id)
  persistTemplates()
}

async function makeShare() {
  try {
    const code = await encodeConfig({ ...params })
    // file:// 下 location.origin 是 "null"，拼出来的链接别人打不开；
    // 此时只给配置码，由使用者贴回同一页面的地址栏。
    const local = location.protocol === 'file:'
    const base = local ? location.href.split('#')[0] : `${location.origin}${location.pathname}`
    shareUrl.value = `${base}#cfg=${code}`
    try { await navigator.clipboard.writeText(local ? `#cfg=${code}` : shareUrl.value) } catch (_) { /* 手动复制兜底 */ }
    // 不改写地址栏：否则点过“分享”后刷新页面会拿旧链接覆盖本机正在编辑的配置
    toast(local ? '已复制配置码；请贴到同一页面地址栏的 # 后使用' : '链接已生成并复制')
  } catch (e) {
    state.error = `生成分享链接失败：${e.message}`
  }
}

/* ---------------- 出口 ---------------- */
function rememberPageRange() {
  const value = pageRange.value.trim()
  if (!value) return
  pageHistory.value = [value, ...pageHistory.value.filter(x => x !== value)].slice(0, 5)
  try { localStorage.setItem(LS_PAGESPEC, JSON.stringify(pageHistory.value)) } catch (_) { /* 忽略 */ }
}

async function exportSheet(split = false) {
  if (!params.text) return
  state.exporting = true
  state.error = ''
  try {
    const { blob, name } = await api.exportSheet({ ...params }, {
      splitSize: split ? splitSize.value : 0,
      format: exportFormat.value,
      pageRange: pageRange.value
    })
    download(blob, name)
    rememberPageRange()
    toast(`已生成 ${name}`)
  } catch (e) {
    state.error = e.message
  } finally {
    state.exporting = false
  }
}

async function printAll() {
  if (!params.text) return
  state.busy = true
  state.error = ''
  try {
    const data = await api.printPages({ ...params }, pageRange.value, 30)
    const win = window.open('', '_blank')
    if (!win) throw new Error('浏览器拦截了新窗口，请允许弹窗')
    const imgs = data.pages.map(src => `<img src="${src}">`).join('')
    win.document.write(
      `<!doctype html><title>打印字帖</title>` +
      `<style>@page{size:${params.page_size || 'A4'};margin:0}html,body{margin:0;background:#fff}` +
      `img{width:100%;display:block;page-break-after:always;break-after:page}` +
      `img:last-child{page-break-after:auto;break-after:auto}</style>${imgs}` +
      `<script>window.addEventListener('load',function(){window.focus();window.print()})<\/script>`
    )
    win.document.close()
    rememberPageRange()
  } catch (e) {
    state.error = e.message
  } finally {
    state.busy = false
  }
}

/* ---------------- 启动 ---------------- */
onMounted(async () => {
  document.documentElement.dataset.theme = ui.theme
  try {
    ui.theme = localStorage.getItem(LS_THEME) === 'dark' ? 'dark' : 'light'
    document.documentElement.dataset.theme = ui.theme
  } catch (_) { /* 忽略 */ }
  loadTemplates()
  try {
    const list = JSON.parse(localStorage.getItem(LS_PAGESPEC) || '[]')
    if (Array.isArray(list)) pageHistory.value = list
  } catch (_) { /* 忽略 */ }

  if (canvasEl.value) {
    measure()
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(measure)
      observer.observe(canvasEl.value)
    }
  }
  window.addEventListener('resize', measure)
  window.addEventListener('keydown', onKey)

  try {
    ui.engine = await engineMode()
    const data = await api.meta()
    meta.value = data
    let initial = { ...data.defaults }

    // 分享链接优先级高于本机存档：别人发来的链接要能直接还原
    const code = parseHash(location.hash)
    if (code) {
      try {
        const cfg = await decodeConfig(code)
        initial = { ...initial, ...cfg }
        toast('已从分享链接还原配置')
      } catch (e) {
        state.error = `分享链接无法还原：${e.message}`
      }
    } else {
      try {
        const saved = JSON.parse(localStorage.getItem(LS_PARAMS) || 'null')
        if (saved && typeof saved === 'object') initial = { ...initial, ...saved }
      } catch (_) { /* 存档损坏就用默认值 */ }
    }

    Object.assign(params, initial)
    if (!params.text) {
      params.title = '静夜思'
      params.text = '床前明月光，疑是地上霜。举头望明月，低头思故乡。'
    }
    ready = true
    await refresh()
    runAnalysis()
    measure()
  } catch (e) {
    ready = true
    state.error = `无法连接后端：${e.message}`
  }
})

onBeforeUnmount(() => {
  clearTimeout(timer)
  clearTimeout(saveTimer)
  clearTimeout(thumbTimer)
  clearTimeout(toastTimer)
  clearTimeout(analyzeTimer)
  observer?.disconnect()
  window.removeEventListener('resize', measure)
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <header class="topbar">
    <div class="brand">
      <strong>字帖工坊</strong>
      <span>硬笔字帖生成 · 版式引擎</span>
      <span v-if="ui.engine === 'browser'" class="engine-badge" title="没有服务端，全部渲染在浏览器内完成">
        离线版 · 浏览器渲染
      </span>
      <span v-else class="engine-badge ok" title="已连接 Python 服务，使用完整字体与高精度导出">桌面版</span>
    </div>

    <div class="actions">
      <button class="btn ghost" @click="libraryOpen = true">文库</button>
      <button class="btn ghost" @click="pickerOpen = true">字表</button>
      <button class="btn ghost" @click="templateTab = 'templates'; templateOpen = true">模板</button>
      <button class="btn ghost" @click="templateTab = 'share'; templateOpen = true; makeShare()">分享</button>
      <button class="btn ghost" :title="'切换界面主题'" @click="ui.theme = ui.theme === 'dark' ? 'light' : 'dark'">
        {{ ui.theme === 'dark' ? '日间' : '夜间' }}
      </button>
      <button class="btn ghost" :disabled="!params.text || state.busy" @click="printAll">打印</button>
      <button class="btn primary" :disabled="!params.text || state.exporting" @click="exportSheet(false)">
        {{ state.exporting ? '生成中…' : `导出 ${exportFormat === 'png' ? 'PNG' : 'PDF'}` }}
      </button>
    </div>
  </header>

  <div class="layout">
    <!-- ---------------- 控制面板 ---------------- -->
    <aside ref="panelEl" class="panel">
      <div class="panel-tabs">
        <button
          v-for="t in TABS"
          :key="t.id"
          :class="{ on: ui.tab === t.id }"
          :title="t.hint"
          @click="setTab(t.id)"
        >{{ t.label }}</button>
      </div>

      <div v-if="ui.tab === 'content'" class="section">
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
          <button class="btn ghost" @click="libraryOpen = true">选篇目</button>
          <button class="btn ghost" @click="params.text = ''">清空</button>
        </div>
        <input ref="fileInput" type="file" accept=".txt,.md,.csv" hidden @change="onFile" />
      </div>

      <div v-if="ui.tab === 'content'" class="section">
        <div class="section-head">
          <h3>练习难度</h3>
          <span class="hint">离线评估 · 无需联网</span>
        </div>
        <div v-if="analysis" class="diff-card">
          <div class="diff-top">
            <span class="diff-stars">★{{ '★'.repeat(analysis.level - 1) }}<i>{{ '★'.repeat(5 - analysis.level) }}</i></span>
            <b>{{ analysis.label }}</b>
            <span class="hint">{{ analysis.chars }} 字</span>
          </div>
          <p v-for="(r, i) in analysis.reasons" :key="i" class="diff-reason">{{ r }}</p>
          <div class="diff-rec">
            <div class="hint" style="margin-bottom:6px">接着练这些</div>
            <button v-for="r in analysis.recommend" :key="r.id" class="rec-item" @click="useRecommend(r)">
              <b>{{ r.title }}</b>
              <span>{{ '★'.repeat(r.level) }} · {{ r.reason }}</span>
            </button>
          </div>
        </div>
        <p v-else class="hint">输入正文后自动评估难度并推荐相近篇目</p>
      </div>

      <div v-if="ui.tab === 'glyph'" class="section">
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

      <div v-if="ui.tab === 'glyph'" class="section">
        <div class="section-head"><h3>练习模式</h3></div>
        <div class="seg-wrap"><Seg v-model="params.mode" :options="MODES" /></div>

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

        <div v-if="isCopy" class="field" style="margin-top:12px">
          <label>每句下方空白行 <b>{{ params.copy_blank }}</b></label>
          <input v-model.number="params.copy_blank" type="range" min="0" max="4" step="1" />
        </div>

        <div v-if="isCard" class="row" style="margin-top:12px">
          <div class="field">
            <label>每字占格</label>
            <input v-model.number="params.card_cells" type="number" min="3" max="10" />
          </div>
          <div class="field">
            <label>其中描红格</label>
            <input v-model.number="params.card_trace" type="number" min="0" max="5" />
          </div>
        </div>

        <p class="hint" style="margin:10px 0 0">
          <template v-if="isMixed">每行先看示范，再描，剩下空格自己写。</template>
          <template v-else-if="isRotate">一行示范一行描红，隔几行空白，最适合整篇临写。</template>
          <template v-else-if="isCopy">上行原帖、下行空格，照着写，不挤占列数。</template>
          <template v-else-if="isFade">
            每行首字实心，其后逐格变淡，写到末尾基本脱手。
            <span v-if="params.trace_style !== 'gray'" style="color:var(--accent)">渐隐需把描红样式切成浅灰。</span>
          </template>
          <template v-else-if="isCard">一字一块：范字 → 描红 → 空白，适合生字表按字过关。</template>
          <template v-else-if="params.mode === 'demo'">整页实心范字，用于对临。</template>
          <template v-else>整页描红，直接下笔。</template>
        </p>
      </div>

      <div v-if="ui.tab === 'glyph'" class="section">
        <div class="section-head"><h3>描红样式</h3></div>
        <Seg v-model="params.trace_style" :options="TRACES" />
        <div v-if="params.trace_style === 'gray'" class="field" style="margin-top:12px">
          <label>浓度 <b>{{ Math.round(params.trace_opacity * 100) }}%</b></label>
          <input v-model.number="params.trace_opacity" type="range" min="0.05" max="0.8" step="0.01" />
        </div>
      </div>

      <div v-if="ui.tab === 'layout'" class="section">
        <div class="section-head"><h3>版式</h3></div>

        <div class="field">
          <label>文字方向</label>
          <Seg v-model="params.direction" :options="DIRECTIONS" />
          <p v-if="isVertical" class="hint" style="margin:6px 0 0">
            竖排自右向左换列、自上而下写字，“每行字数”即每列字数；正式临帖建议关闭“保留标点”。
          </p>
        </div>

        <div class="field">
          <label>格型</label>
          <div class="grid-picker">
            <button
              v-for="g in meta.grids"
              :key="g.id"
              type="button"
              :class="{ on: params.grid === g.id }"
              :title="g.name"
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
            <label>{{ isVertical ? '每列字数' : '每行字数' }}</label>
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
          <label>{{ isVertical ? '每页列数' : '每页行数' }}</label>
          <input v-model.number="params.rows" type="number" min="1" max="26" />
        </div>
      </div>

      <div v-if="ui.tab === 'layout'" class="section">
        <div class="section-head"><h3>外观</h3></div>
        <div class="preset-row">
          <button v-for="p in PRESETS" :key="p.id" class="btn ghost" @click="applyPreset(p)">{{ p.name }}</button>
        </div>
        <div class="row" style="align-items:center;margin-top:10px">
          <div style="display:flex; align-items:center; gap:8px">
            <input v-model="params.grid_color" type="color" />
            <span class="hint">格线</span>
          </div>
          <div style="display:flex; align-items:center; gap:8px">
            <input v-model="params.font_color" type="color" />
            <span class="hint">字色</span>
          </div>
          <div style="display:flex; align-items:center; gap:8px">
            <input v-model="params.paper_color" type="color" />
            <span class="hint">纸色</span>
          </div>
        </div>
        <Toggle v-model="params.show_header" label="显示标题与页码" />
      </div>

      <div v-if="ui.tab === 'content'" class="section">
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

      <div v-if="ui.tab === 'output'" class="section">
        <div class="section-head"><h3>导出设置</h3><span class="hint">文件名带日期</span></div>
        <Seg v-model="exportFormat" :options="FORMATS" />
        <div class="field" style="margin-top:12px">
          <label>页码范围 <b>留空 = 全部</b></label>
          <input v-model="pageRange" list="page-history" type="text" placeholder="例如：1-2,4" />
          <datalist id="page-history">
            <option v-for="h in pageHistory" :key="h" :value="h" />
          </datalist>
          <p class="hint" style="margin:6px 0 0">PDF / PNG / 打印共用这一范围；PNG 多页自动打包 zip。</p>
        </div>
        <div class="row">
          <input v-model.number="splitSize" class="split-input" type="number" min="20" max="2000" step="10" title="每册字数" />
          <button class="btn" :disabled="!params.text || state.exporting" @click="exportSheet(true)">
            按每册字数分册
          </button>
        </div>
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
        <div class="stage-tools">
          <div class="pager" v-if="state.pages > 1">
            <button :disabled="state.page <= 0" @click="state.page--">‹</button>
            <input class="page-jump" type="number" min="1" :max="state.pages" :value="state.page + 1"
                   title="跳到第几页（页码从 1 开始）"
                   @change="state.page = Math.max(0, Math.min(state.pages - 1, (Number($event.target.value) || 1) - 1)); $event.target.value = state.page + 1" />
            <b>/ {{ state.pages }}</b>
            <button :disabled="state.page >= state.pages - 1" @click="state.page++">›</button>
          </div>
          <div class="zoom">
            <button @click="ui.zoom = Math.max(0.4, +(ui.zoom - 0.1).toFixed(2))">−</button>
            <span>{{ Math.round(ui.zoom * 100) }}%</span>
            <button @click="ui.zoom = Math.min(2.5, +(ui.zoom + 0.1).toFixed(2))">＋</button>
            <button class="btn ghost" style="height:26px;padding:0 8px" @click="ui.zoom = 1">适应</button>
          </div>
        </div>
      </div>

      <div v-if="state.error" class="warnings error-box">
        {{ state.error }}
      </div>
      <div v-if="state.warnings.length" class="warnings">
        <div v-for="(w, i) in state.warnings" :key="i">{{ w }}</div>
      </div>

      <div ref="canvasEl" class="canvas">
        <div v-if="state.image" class="page" :style="{ background: params.paper_color || '#fff' }">
          <img :src="state.image" :style="{ width: displayWidth + 'px' }" alt="字帖预览" />
        </div>
        <div v-else class="empty">
          还没有内容<br />
          点“文库”挑一篇古诗，或粘贴一段自己的文字
        </div>
      </div>

      <div v-if="state.thumbs.length > 1" class="thumbs">
        <button
          v-for="(t, i) in state.thumbs"
          :key="i"
          :class="{ on: state.page === i }"
          :title="`第 ${i + 1} 页`"
          @click="state.page = i"
        >
          <img :src="t" :alt="`第 ${i + 1} 页`" />
          <span>{{ i + 1 }}</span>
        </button>
        <span v-if="state.thumbsTruncated" class="hint">仅显示前 {{ state.thumbs.length }} / {{ state.thumbsTotal }} 页缩略图</span>
        <span v-if="state.thumbsLoading" class="hint">缩略图生成中…</span>
      </div>
    </section>
  </div>

  <CharPicker
    :open="pickerOpen"
    :charsets="meta.charsets"
    @close="pickerOpen = false"
    @pick="fillFromCharset"
  />
  <LibraryPicker
    :open="libraryOpen"
    :groups="meta.library"
    @close="libraryOpen = false"
    @pick="pickPassage"
  />
  <TemplateDrawer
    v-model:tab="templateTab"
    :open="templateOpen"
    :templates="templates"
    :share-url="shareUrl"
    @close="templateOpen = false"
    @save="saveTemplate"
    @apply="applyTemplate"
    @remove="removeTemplate"
    @share="makeShare"
    @share-copied="toast('链接已复制')"
  />

  <div v-if="ui.toast" class="toast">{{ ui.toast }}</div>
</template>
