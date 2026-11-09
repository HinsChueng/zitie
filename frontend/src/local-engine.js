/**
 * 浏览器端字帖引擎 —— 无服务端时接管 /api/* 的全部能力。
 *
 * 设计原则：
 *  1) 编排规则（normalize / wrap / composeRows / paginate / 版面计算）与
 *     backend/app/layout.py、render.py 一一对应，保证同一份参数两种模式出同样的版；
 *  2) 版面计算是纯数据（Sheet.layoutPage），绘制才碰 Canvas，因此纯逻辑可在 Node 里测；
 *  3) PDF / ZIP 自己写最小实现，不引入 jsPDF / JSZip，保持“单文件、零依赖”。
 *
 * 已知差异：字体来自操作系统 CSS 字体栈（不能枚举全部已装字体），
 * 转繁体需要 zhconv 词表故静态版不提供，导出图片为位图（与后端一致）。
 */
import { STATIC } from './static-data.js'

/* ==========================================================================
 * 一、文本编排 —— 对应 backend/app/layout.py
 * ========================================================================== */
const NO_START = new Set('。，、；：？！）］｝〉》」』】”’…—·％‰℃,.;:?!)]}>')
const NO_END = new Set('（［｛〈《「『【“‘([{<')
const FULL_PUNCT = new Set('，。、；：？！“”‘’（）【】《》〈〉「」『』…—·～％‰')
const HALF_PUNCT = new Set(',.;:?!')
const ALL_PUNCT = new Set([...FULL_PUNCT, ...HALF_PUNCT])
const PUNCT_BREAK = new Set('。！？，、；：')
const CJK = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/

export function normalize(text, keepPunct = true) {
  let s = String(text ?? '').replace(/\r\n?/g, '\n')
  let out = ''
  for (const ch of s) {
    if (ch === '\n') out += ch
    else if (ALL_PUNCT.has(ch)) { if (keepPunct) out += ch }
    else if (CJK.test(ch) || /[0-9A-Za-z]/.test(ch)) out += ch
  }
  return out
}

function splitAfterPunct(text) {
  const segs = []
  let cur = ''
  for (const ch of text) {
    cur += ch
    if (PUNCT_BREAK.has(ch)) { segs.push(cur); cur = '' }
  }
  if (cur) segs.push(cur)
  const merged = []
  for (const seg of segs) {
    if (merged.length && seg.length <= 2) merged[merged.length - 1] += seg
    else merged.push(seg)
  }
  return merged
}

function hardWrap(paragraph, cols, rule = true) {
  const total = paragraph.length
  const lines = []
  let pos = 0
  while (pos < total) {
    let end = Math.min(pos + cols, total)
    if (rule && end < total) {
      while (end - 1 > pos && NO_START.has(paragraph[end])) end--
      while (end - 1 > pos && NO_END.has(paragraph[end - 1])) end--
    }
    if (end <= pos) end = pos + 1
    lines.push(paragraph.slice(pos, end))
    pos = end
  }
  return lines
}

export function wrap(paragraph, cols, rule = true, breakAtPunct = false) {
  if (cols <= 0) throw new Error('每行字数必须为正数')
  if (breakAtPunct) {
    const segs = splitAfterPunct(paragraph)
    if (segs.length && Math.max(...segs.map(s => s.length)) <= cols) {
      return segs.flatMap(seg => hardWrap(seg, cols, rule))
    }
  }
  return hardWrap(paragraph, cols, rule)
}

export function paragraphs(text, cols, rule = true, breakAtPunct = false) {
  const out = []
  for (const para of text.split('\n')) {
    if (para) out.push(...wrap(para, cols, rule, breakAtPunct))
  }
  return out
}

/** Slot: { char, style } —— style 只有 demo / trace，空格用 null */
export function composeRows(p) {
  const lines = paragraphs(normalize(p.text, p.keep_punct), p.columns,
    p.line_break_rule, p.break_at_punct)
  const rows = []
  const cols = p.columns
  const slot = (ch, style) => ({ char: ch, style })

  if (p.mode === 'demo' || p.mode === 'trace') {
    const style = p.mode === 'demo' ? 'demo' : 'trace'
    for (const line of lines) rows.push([...line].map(ch => slot(ch, style)))

  } else if (p.mode === 'mixed') {
    const span = Math.max(1, p.demo_cells + p.trace_cells)
    if (p.repeat) {
      for (const line of lines) {
        for (const ch of line) {
          if (ALL_PUNCT.has(ch)) continue
          const row = []
          for (let i = 0; i < cols; i++) {
            row.push(i < p.demo_cells ? slot(ch, 'demo')
              : i < p.demo_cells + p.trace_cells ? slot(ch, 'trace') : null)
          }
          rows.push(row)
        }
      }
    } else {
      for (const line of lines) {
        for (let start = 0; start < line.length; start += span) {
          const chunk = line.slice(start, start + span)
          const row = []
          for (let i = 0; i < cols; i++) {
            row.push(i < chunk.length ? slot(chunk[i], i < p.demo_cells ? 'demo' : 'trace') : null)
          }
          rows.push(row)
        }
      }
    }

  } else if (p.mode === 'copy') {
    for (const line of lines) {
      rows.push([...line].map(ch => slot(ch, 'demo')))
      for (let i = 0; i < p.copy_blank; i++) rows.push([])
    }

  } else if (p.mode === 'fade') {
    for (const line of lines) {
      rows.push([...line].map((ch, i) => slot(ch, i === 0 ? 'demo' : 'trace')))
    }

  } else if (p.mode === 'card') {
    const span = Math.max(3, p.card_cells)
    const traceN = Math.max(0, Math.min(p.card_trace, span - 2))
    const blankN = span - 1 - traceN
    const perRow = Math.max(1, Math.floor(cols / span))
    const chars = [...normalize(p.text, p.keep_punct)]
      .filter(ch => ch !== '\n' && !ALL_PUNCT.has(ch))
    const blocks = chars.map(ch => [
      slot(ch, 'demo'), ...Array(traceN).fill(0).map(() => slot(ch, 'trace')),
      ...Array(blankN).fill(null)
    ])
    for (let s = 0; s < blocks.length; s += perRow) {
      const row = []
      for (const block of blocks.slice(s, s + perRow)) row.push(...block)
      while (row.length < cols) row.push(null)
      rows.push(row)
    }

  } else { // rotate
    for (const line of lines) {
      const demo = [...line].map(ch => slot(ch, 'demo'))
      const trace = [...line].map(ch => slot(ch, 'trace'))
      for (let i = 0; i < p.cycle_demo; i++) rows.push([...demo])
      for (let i = 0; i < p.cycle_trace; i++) rows.push([...trace])
      for (let i = 0; i < p.cycle_blank; i++) rows.push([])
    }
  }
  return rows
}

export function paginate(rows, perPage) {
  if (!rows.length) return [[]]
  const out = []
  for (let i = 0; i < rows.length; i += perPage) out.push(rows.slice(i, i + perPage))
  return out
}

/** 对应 render.parse_page_range：越界直接报错，不静默截断 */
export function parsePageRange(spec, total) {
  if (!spec || !spec.trim()) return [...Array(total).keys()]
  const picked = []
  const seen = new Set()
  for (const part of spec.trim().split(/[,，;；\s]+/)) {
    if (!part) continue
    const m = /^(\d+)(?:\s*[-–~—]\s*(\d+))?$/.exec(part)
    if (!m) throw new Error(`页码写法无法识别：${part}（示例：1-2,4）`)
    const start = Number(m[1])
    const end = m[2] ? Number(m[2]) : start
    if (start < 1 || end > total || start > end) {
      throw new Error(`页码 ${part} 超出范围（共 ${total} 页）`)
    }
    for (let n = start; n <= end; n++) {
      if (!seen.has(n - 1)) { seen.add(n - 1); picked.push(n - 1) }
    }
  }
  if (!picked.length) throw new Error('没有选中任何页')
  return picked
}

/* ==========================================================================
 * 二、版面计算 —— 对应 render.Sheet._prepare
 * ========================================================================== */
const PAGE_MM = { A4: [210, 297], A5: [148, 210], B5: [176, 250] }
const mm2px = (mm, dpi) => Math.max(1, Math.round(mm / 25.4 * dpi))

export function withDefaults(params) {
  const p = { ...STATIC.defaults, ...(params || {}) }
  // 分享链接可能来自桌面版，字体 id 在静态版里不存在，回退到楷体
  if (!fontById(p.font_id)) p.font_id = 'tk'
  return p
}

export class Sheet {
  constructor(input) {
    let p = withDefaults(input)
    this.warnings = []
    this.p = p
    const vertical = p.direction === 'vertical'
    this.dpi = Math.min(Math.max(150, Number(p.dpi) || 300), 600)
    const [pwMm, phMm] = PAGE_MM[p.page_size] || PAGE_MM.A4
    this.pageW = mm2px(pwMm, this.dpi)
    this.pageH = mm2px(phMm, this.dpi)
    this.paper = hexRgb(p.paper_color)

    const margin = mm2px(p.margin_mm, this.dpi)
    const header = p.show_header ? mm2px(9, this.dpi) : 0
    let cell = mm2px(p.cell_mm, this.dpi)
    const availW = this.pageW - 2 * margin
    const availH = this.pageH - 2 * margin - header
    const perLine = p.columns
    const fixedRoom = vertical ? availH : availW
    const freeRoom = vertical ? availW : availH

    let shrunk = false
    const limit = Math.max(1, Math.floor(fixedRoom / perLine))
    if (cell > limit) { cell = limit; shrunk = true }

    let rowsN = p.rows
    if (p.auto_rows) rowsN = Math.max(1, Math.min(26, Math.floor(freeRoom / cell)))
    if (rowsN * cell > freeRoom) {
      const cap = Math.floor(freeRoom / rowsN)
      if (cap < mm2px(8, this.dpi)) {
        this.warnings.push('格子太多，已超出页面可容纳范围，建议减少行数或列数')
      } else if (!shrunk) {
        this.warnings.push(`${perLine} 字／行 × ${rowsN} 行放不下 ${p.cell_mm}mm 的格子，已自动缩放到${(cap / this.dpi * 25.4).toFixed(1)}mm`)
      }
      cell = Math.max(1, cap)
      shrunk = true
    }
    if (shrunk && !this.warnings.some(w => w.includes('自动缩放'))) {
      this.warnings.push(`格子已自动缩放到 ${(cell / this.dpi * 25.4).toFixed(1)}mm 以适应页面`)
    }

    this.cell = cell
    this.rowsPerPage = rowsN
    this.gridW = cell * (vertical ? rowsN : perLine)
    this.gridH = cell * (vertical ? perLine : rowsN)
    this.x0 = Math.floor((this.pageW - this.gridW) / 2)
    this.y0 = margin + header + mm2px(3, this.dpi)
    this.vertical = vertical

    if (vertical && ['pinyin4', 'composition', 'control'].includes(p.grid)) {
      this.warnings.push('竖排下四线格／作文格／控笔格不适用，已改用田字格')
      this.p = { ...p, grid: 'tian' }
      p = this.p
    }
    if (vertical && p.keep_punct) {
      this.warnings.push('竖排下标点仍按横排字形绘制，正式临帖建议关闭保留标点')
    }
    if (p.traditional) {
      this.warnings.push('静态版不含繁体词表，已按简体渲染；需要转繁体请用桌面版')
    }

    this.rows = composeRows(this.p)
    this.pages = paginate(this.rows, rowsN)
    this.charCount = this.rows.reduce((n, row) => n + row.filter(Boolean).length, 0)
  }

  /** 纯数据的一页版面，便于测试与绘制复用 */
  layoutPage(index) {
    const p = this.p
    const cells = []
    const pageRows = this.pages[Math.max(0, Math.min(index, this.pages.length - 1))] || []
    for (let r = 0; r < pageRows.length; r++) {
      for (let c = 0; c < pageRows[r].length; c++) {
        const s = pageRows[r][c]
        if (!s) continue
        const style = s.style === 'demo' ? 'demo' : p.trace_style
        let opacity = null
        if (p.mode === 'fade' && s.style === 'trace' && style === 'gray') {
          const span = Math.max(2, p.columns)
          const t = Math.min(1, Math.max(0, (c - 1) / Math.max(1, span - 2)))
          opacity = Math.max(0.04, p.trace_opacity * (1 - 0.88 * t))
        }
        const x = this.vertical ? this.x0 + (this.rowsPerPage - 1 - r) * this.cell
          : this.x0 + c * this.cell
        const y = this.vertical ? this.y0 + c * this.cell : this.y0 + r * this.cell
        cells.push({ char: s.char, style, opacity, x, y, col: c, row: r })
      }
    }
    return {
      pageW: this.pageW, pageH: this.pageH, cell: this.cell,
      x0: this.x0, y0: this.y0, gridW: this.gridW, gridH: this.gridH,
      cols: this.vertical ? this.rowsPerPage : p.columns,
      rows: this.vertical ? p.columns : this.rowsPerPage,
      grid: p.grid, vertical: this.vertical,
      paper: p.paper_color, gridColor: p.grid_color,
      fontColor: p.font_color, fontFamily: fontFamily(p.font_id),
      fontRatio: p.font_ratio, traceOpacity: p.trace_opacity,
      header: p.show_header ? {
        title: p.title, label: `第 ${index + 1} 页 / 共 ${this.pages.length} 页`,
        size: mm2px(4.6, this.dpi), top: mm2px(p.margin_mm, this.dpi),
        color: avg(this.paper) < 128 ? '#d8d2c6' : '#6b6b6b'
      } : null,
      cells
    }
  }
}

/* ==========================================================================
 * 三、Canvas 绘制 —— 对应 grid.py 与 glyphs.py
 * ========================================================================== */
function hexRgb(hex) {
  let s = String(hex || '').replace('#', '')
  if (s.length === 3) s = [...s].map(c => c + c).join('')
  const n = parseInt(s, 16)
  if (!Number.isFinite(n) || s.length !== 6) return [255, 255, 255]
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
const avg = rgb => (rgb[0] + rgb[1] + rgb[2]) / 3
const cssRgb = rgb => `rgb(${rgb.join(',')})`
function mix(color, ratio, paperRgb) {
  const c = hexRgb(color)
  return cssRgb(c.map((v, i) => Math.round(paperRgb[i] + (v - paperRgb[i]) * ratio)))
}

function line(ctx, x1, y1, x2, y2, color, width, dash) {
  ctx.beginPath()
  ctx.setLineDash(dash || [])
  ctx.strokeStyle = color
  ctx.lineWidth = width
  ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
  ctx.setLineDash([])
}

function controlPath(ctx, x, y, cell, variant, color, width) {
  const pad = cell * 0.14, span = cell - pad * 2
  const cx = x + cell / 2, cy = y + cell / 2
  const pts = []
  if (variant === 0) {
    for (let i = 0; i < 97; i++) {
      const t = i / 96
      pts.push([x + pad + span * t, cy + Math.sin(t * Math.PI * 6) * span * 0.26])
    }
  } else if (variant === 1) {
    for (let i = 0; i < 145; i++) {
      const t = i / 144, a = t * Math.PI * 7, r = span * 0.46 * t
      pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r])
    }
  } else if (variant === 2) {
    for (let i = 0; i < 13; i++) {
      const t = i / 12
      pts.push([x + pad + span * t, cy + (span * 0.28 * (i % 2 ? 1 : -1))])
    }
  } else {
    for (let i = 0; i < 145; i++) {
      const t = i / 144 * Math.PI * 2
      pts.push([cx + Math.sin(t) * span * 0.42, cy + Math.sin(t * 2) * span * 0.24])
    }
  }
  ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = width
  ctx.lineJoin = 'round'; ctx.lineCap = 'round'
  ctx.moveTo(pts[0][0], pts[0][1])
  for (const [px, py] of pts.slice(1)) ctx.lineTo(px, py)
  ctx.stroke()
}

function drawGrid(ctx, L) {
  const { x0, y0, cols, rows, cell, grid, gridColor, paper } = L
  const paperRgb = hexRgb(paper)
  const width = cols * cell, height = rows * cell
  const dash = Math.max(8, Math.floor(cell / 16)), gap = Math.max(6, Math.floor(cell / 22))
  const faint = mix(gridColor, 0.42, paperRgb)
  const lw = Math.max(1, Math.floor(cell / 60))

  if (grid === 'vertical') {
    for (let i = 0; i <= cols; i++) line(ctx, x0 + i * cell, y0, x0 + i * cell, y0 + height, gridColor, lw)
    return
  }
  if (grid === 'line') {
    for (let j = 0; j <= rows; j++) line(ctx, x0, y0 + j * cell, x0 + width, y0 + j * cell, gridColor, lw)
    return
  }
  for (let i = 0; i <= cols; i++) line(ctx, x0 + i * cell, y0, x0 + i * cell, y0 + height, gridColor, lw)
  for (let j = 0; j <= rows; j++) line(ctx, x0, y0 + j * cell, x0 + width, y0 + j * cell, gridColor, lw)
  if (grid === 'blank') return

  if (grid === 'pinyin4') {
    for (let j = 0; j < rows; j++) {
      for (let k = 1; k <= 2; k++) {
        line(ctx, x0, y0 + j * cell + k * cell / 3, x0 + width,
          y0 + j * cell + k * cell / 3, faint, 1, [dash, gap])
      }
    }
    return
  }
  if (grid === 'composition') {
    const r = Math.max(2, Math.floor(cell / 60))
    ctx.fillStyle = faint
    for (let j = 0; j < rows; j++) {
      for (let i = 0; i < cols; i++) {
        ctx.beginPath()
        ctx.arc(x0 + i * cell + cell / 2, y0 + j * cell + cell / 2, r, 0, Math.PI * 2)
        ctx.fill()
      }
    }
    return
  }
  if (grid === 'control') {
    const trace = mix(gridColor, 0.30, paperRgb)
    const cw = Math.max(1, Math.floor(cell / 90))
    for (let j = 0; j < rows; j++) {
      for (let i = 0; i < cols; i++) {
        controlPath(ctx, x0 + i * cell, y0 + j * cell, cell, (i + j * 2) % 4, trace, cw)
      }
    }
    return
  }
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i < cols; i++) {
      const x = x0 + i * cell, y = y0 + j * cell
      const mx = x + cell / 2, my = y + cell / 2
      const right = x + cell, bottom = y + cell
      if (grid === 'tian' || grid === 'mi') {
        line(ctx, mx, y, mx, bottom, gridColor, 1, [dash, gap])
        line(ctx, x, my, right, my, gridColor, 1, [dash, gap])
        if (grid === 'mi') {
          line(ctx, x, y, right, bottom, gridColor, 1, [dash, gap])
          line(ctx, right, y, x, bottom, gridColor, 1, [dash, gap])
        }
      } else if (grid === 'jiugong') {
        for (let k = 1; k <= 2; k++) {
          line(ctx, x + cell * k / 3, y, x + cell * k / 3, bottom, gridColor, 1, [dash, gap])
          line(ctx, x, y + cell * k / 3, right, y + cell * k / 3, gridColor, 1, [dash, gap])
        }
      } else if (grid === 'huigong') {
        const inset = cell * 0.25
        ctx.strokeStyle = gridColor; ctx.lineWidth = 1
        ctx.strokeRect(x + inset, y + inset, cell - inset * 2, cell - inset * 2)
      }
    }
  }
}

let dotCache = null
function dotPattern(ctx, color, cell) {
  const key = `${color}|${Math.round(cell)}`
  if (dotCache && dotCache.key === key) return dotCache.pattern
  const s = Math.max(3, Math.round(cell / 22))
  const c = document.createElement('canvas')
  c.width = c.height = s
  const g = c.getContext('2d')
  g.fillStyle = color
  g.beginPath(); g.arc(s / 2, s / 2, Math.max(0.7, s * 0.17), 0, Math.PI * 2); g.fill()
  const pattern = ctx.createPattern(c, 'repeat')
  dotCache = { key, pattern }
  return pattern
}

/** 按墨迹实际包围盒缩放到格内并居中，等价于后端的 GlyphFactory */
function drawGlyph(ctx, item, L) {
  const { char, style, opacity, x, y } = item
  const cell = L.cell
  const probe = cell
  ctx.font = `${probe}px ${L.fontFamily}`
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'
  const m = ctx.measureText(char)
  const bw = (m.actualBoundingBoxLeft || 0) + (m.actualBoundingBoxRight || m.width)
  const bh = (m.actualBoundingBoxAscent || probe * 0.8) + (m.actualBoundingBoxDescent || probe * 0.2)
  if (!(bw > 0) || !(bh > 0)) return
  const size = Math.max(6, Math.round(probe * Math.min(cell * L.fontRatio / bw, cell * L.fontRatio / bh)))
  ctx.font = `${size}px ${L.fontFamily}`
  const m2 = ctx.measureText(char)
  const left = m2.actualBoundingBoxLeft || 0
  const right = m2.actualBoundingBoxRight || m2.width
  const asc = m2.actualBoundingBoxAscent || size * 0.8
  const desc = m2.actualBoundingBoxDescent || size * 0.2
  const px = x + cell / 2 - (right - left) / 2
  const py = y + cell / 2 + (asc - desc) / 2

  const paperRgb = hexRgb(L.paper)
  if (style === 'outline') {
    ctx.lineWidth = Math.max(1, cell / 90)
    ctx.strokeStyle = mix(L.fontColor, Math.min(0.9, L.traceOpacity + 0.15), paperRgb)
    ctx.strokeText(char, px, py)
  } else if (style === 'dot') {
    ctx.fillStyle = dotPattern(ctx, mix(L.fontColor, Math.max(0.15, L.traceOpacity), paperRgb), cell)
    ctx.fillText(char, px, py)
  } else if (style === 'gray') {
    ctx.fillStyle = mix(L.fontColor, opacity ?? L.traceOpacity, paperRgb)
    ctx.fillText(char, px, py)
  } else {
    ctx.fillStyle = L.fontColor
    ctx.fillText(char, px, py)
  }
}

export function paint(ctx, sheet, index, scale = 1) {
  const L = sheet.layoutPage(index)
  ctx.save()
  ctx.scale(scale, scale)
  ctx.fillStyle = L.paper
  ctx.fillRect(0, 0, L.pageW, L.pageH)
  drawGrid(ctx, L)
  for (const item of L.cells) drawGlyph(ctx, item, L)
  if (L.header) {
    ctx.fillStyle = L.header.color
    ctx.font = `${L.header.size}px ${L.fontFamily}`
    ctx.textBaseline = 'middle'
    const baseY = L.header.top + L.header.size / 2
    ctx.textAlign = 'left'
    if (L.header.title) ctx.fillText(L.header.title, L.x0, baseY)
    ctx.textAlign = 'right'
    ctx.fillText(L.header.label, L.x0 + L.gridW, baseY)
  }
  ctx.restore()
  return L
}

/** 渲染一页到 canvas；width 给定时按比例缩小（预览／缩略图） */
export function renderCanvas(params, index = 0, width = null) {
  const sheet = new Sheet(params)
  const p0 = sheet.layoutPage(index)
  const scale = width ? Math.min(1, width / p0.pageW) : 1
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(p0.pageW * scale))
  canvas.height = Math.max(1, Math.round(p0.pageH * scale))
  const ctx = canvas.getContext('2d')
  paint(ctx, sheet, index, scale)
  return { canvas, sheet, scale }
}

/* ==========================================================================
 * 四、字体（CSS 字体栈 + FontFace 上传）
 * ========================================================================== */
const BUILTIN_FONTS = [
  { id: 'tk', name: '楷体', family: '"KaiTi","STKaiti","楷体","BiauKai","DFKai-SB",serif' },
  { id: 'fs', name: '仿宋', family: '"FangSong","STFangsong","仿宋","FangSong_GB2312",serif' },
  { id: 'st', name: '宋体', family: '"SimSun","Songti SC","STSong","宋体",serif' },
  { id: 'ht', name: '黑体', family: '"SimHei","Heiti SC","STHeiti","黑体",sans-serif' },
  { id: 'yh', name: '微软雅黑', family: '"Microsoft YaHei","PingFang SC","微软雅黑",sans-serif' },
  { id: 'ls', name: '隶书', family: '"LiSu","STLiti","隶书",serif' },
  { id: 'xk', name: '行楷', family: '"STXingkai","华文行楷","KaiTi",cursive' },
  { id: 'yy', name: '幼圆', family: '"YouYuan","幼圆","Microsoft YaHei",sans-serif' }
]
const customFonts = []

function fontById(id) {
  return BUILTIN_FONTS.find(f => f.id === id) || customFonts.find(f => f.id === id) || null
}
function fontFamily(id) {
  const f = fontById(id) || BUILTIN_FONTS[0]
  return f.family
}
function fontList() {
  return [...BUILTIN_FONTS, ...customFonts].map(f => ({
    id: f.id, name: f.name, source: f.source || 'system', has_cjk: true,
    sample: '永', coverage: 100
  }))
}

/* ==========================================================================
 * 五、二进制生成：最小 PDF 与 ZIP（不引第三方库）
 * ========================================================================== */
function dataUrlBytes(dataUrl) {
  const bin = atob(dataUrl.slice(dataUrl.indexOf(',') + 1))
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}
const concatBytes = parts => {
  const total = parts.reduce((n, b) => n + b.length, 0)
  const out = new Uint8Array(total)
  let at = 0
  for (const b of parts) { out.set(b, at); at += b.length }
  return out
}
const enc = s => new TextEncoder().encode(s)

/** pages: [{ jpeg: Uint8Array, w, h, wPt, hPt }] */
export function makePdf(pages) {
  const chunks = []
  let len = 0
  const push = v => { const b = typeof v === 'string' ? enc(v) : v; chunks.push(b); len += b.length }
  const offsets = [0]
  const n = pages.length

  // PDF 文件头是规范强制项，缺失会被阅读器直接判为损坏；
  // 第二行的高位字节让传输层不至于把它当纯文本改写（必须按原始字节写）。
  push('%PDF-1.4\n')
  push(new Uint8Array([0x25, 0xE2, 0xE3, 0xCF, 0xD3, 0x0A]))

  const begin = (num, head) => { offsets[num] = len; push(`${num} 0 obj\n${head}\n`) }
  const stream = (bytes) => {
    push('stream\n'); push(bytes); push('\nendstream\n')
  }
  const end = () => push('endobj\n')

  begin(1, '<< /Type /Catalog /Pages 2 0 R >>'); end()
  const kids = pages.map((_, i) => `${3 + i * 3} 0 R`).join(' ')
  begin(2, `<< /Type /Pages /Kids [${kids}] /Count ${n} >>`); end()

  pages.forEach((page, i) => {
    const pageNo = 3 + i * 3, contentNo = pageNo + 1, imageNo = pageNo + 2
    const W = page.wPt.toFixed(2), H = page.hPt.toFixed(2)
    begin(pageNo,
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${W} ${H}] ` +
      `/Resources << /XObject << /Im0 ${imageNo} 0 R >> >> /Contents ${contentNo} 0 R >>`)
    end()
    const cmd = `q\n${W} 0 0 ${H} 0 0 cm\n/Im0 Do\nQ\n`
    begin(contentNo, `<< /Length ${enc(cmd).length} >>`); stream(enc(cmd)); end()
    begin(imageNo,
      `<< /Type /XObject /Subtype /Image /Width ${page.w} /Height ${page.h} ` +
      `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${page.jpeg.length} >>`)
    stream(page.jpeg); end()
  })

  const xrefAt = len
  const total = 2 + n * 3 + 1
  let xref = `xref\n0 ${total}\n0000000000 65535 f \n`
  for (let i = 1; i < total; i++) xref += `${String(offsets[i] || 0).padStart(10, '0')} 00000 n \n`
  push(xref)
  push(`trailer\n<< /Size ${total} /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF\n`)
  return concatBytes(chunks)
}

const CRC_TABLE = (() => {
  const t = new Uint32Array(256)
  for (let i = 0; i < 256; i++) {
    let c = i
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1
    t[i] = c >>> 0
  }
  return t
})()
function crc32(bytes) {
  let c = 0xFFFFFFFF
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 255] ^ (c >>> 8)
  return (c ^ 0xFFFFFFFF) >>> 0
}
function u16(n) { return new Uint8Array([n & 255, (n >> 8) & 255]) }
function u32(n) { return new Uint8Array([n & 255, (n >> 8) & 255, (n >> 16) & 255, (n >>> 24) & 255]) }

/** files: [{ name, bytes }]，store 模式（不压缩） */
export function makeZip(files) {
  const locals = [], centrals = []
  let offset = 0
  const now = new Date()
  const dosTime = ((now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1)) & 0xFFFF
  const dosDate = (((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate()) & 0xFFFF
  for (const f of files) {
    const name = enc(f.name)
    const crc = crc32(f.bytes)
    const local = concatBytes([
      u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(dosTime), u16(dosDate),
      u32(crc), u32(f.bytes.length), u32(f.bytes.length), u16(name.length), u16(0),
      name, f.bytes
    ])
    locals.push(local)
    centrals.push(concatBytes([
      u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(dosTime), u16(dosDate),
      u32(crc), u32(f.bytes.length), u32(f.bytes.length), u16(name.length),
      u16(0), u16(0), u16(0), u16(0), u32(0), u32(offset), name
    ]))
    offset += local.length
  }
  const cd = concatBytes(centrals)
  const eocd = concatBytes([
    u32(0x06054b50), u16(0), u16(0), u16(files.length), u16(files.length),
    u32(cd.length), u32(offset), u16(0)
  ])
  return concatBytes([...locals, cd, eocd])
}

/* ==========================================================================
 * 六、难度评估 —— 对应 backend/app/difficulty.py
 * ========================================================================== */
const LEVEL_LABELS = ['入门', '基础', '进阶', '熟练', '挑战']
let rankMap = null
function ranks() {
  if (!rankMap) { rankMap = new Map(); [...STATIC.freq].forEach((ch, i) => { if (!rankMap.has(ch)) rankMap.set(ch, i) }) }
  return rankMap
}
export function scoreText(text, keepPunct = true) {
  const clean = normalize(text, keepPunct)
  const han = [...clean].filter(ch => CJK.test(ch))
  const map = ranks(), tableLen = Math.max(1, map.size), n = han.length
  if (!n) return { level: 1, label: LEVEL_LABELS[0], points: 0, chars: 0, unique: 0,
    rare: 0, coverage: 100.0, avg_rank: 0, reasons: ['还没有汉字内容'] }
  const rare = han.filter(ch => !map.has(ch)).length
  const rareRatio = rare / n
  const avgRank = han.reduce((s, ch) => s + (map.get(ch) ?? tableLen), 0) / n
  const unique = new Set(han).size
  const uniqueRatio = unique / n
  const points = [
    avgRank > 500, avgRank > 800, avgRank > 1100, rare >= 2, rare >= 3,
    n > 30, n > 40, uniqueRatio > 0.90, n > 120, n > 300
  ].filter(Boolean).length
  const level = 1 + Math.min(4, Math.round(points * 4 / 10))
  const coverage = Math.round((n - rare) / n * 1000) / 10
  return {
    level, label: LEVEL_LABELS[level - 1], points, chars: n, unique, rare,
    coverage, avg_rank: Math.trunc(avgRank),
    reasons: [
      `正文 ${n} 字，含 ${unique} 个不同汉字（重复率 ${Math.round((1 - uniqueRatio) * 100)}%）`,
      `常用字覆盖 ${coverage}%（${rare} 字超出常用字表）`,
      `平均字频排名约 ${Math.trunc(avgRank)}`
    ]
  }
}
function analyze(text, title = '', keepPunct = true) {
  const result = scoreText(text, keepPunct)
  const level = result.level
  const pool = STATIC.library_flat.filter(x => !title || !title.startsWith(x.title))
  const pick = (items, reason, limit) => items.slice(0, limit).map(x => ({ ...x, reason }))
  let picked = pick(pool.filter(x => x.level === level), '难度相近，换一篇巩固', 2)
  picked = picked.concat(pick(pool.filter(x => x.level === level + 1), '略提难度，往上练一档', 1))
  if (picked.length < 3) picked = picked.concat(pick(pool.filter(x => x.level === level - 1), '回调难度，巩固基本功', 3 - picked.length))
  if (picked.length < 3) picked = picked.concat(pick(pool.filter(x => ![level - 1, level, level + 1].includes(x.level)), '换个题材练练', 3 - picked.length))
  result.recommend = picked.slice(0, 3)
  result.library_total = STATIC.library_flat.length
  return result
}

/* ==========================================================================
 * 七、与 /api/* 同形状的本地实现
 * ========================================================================== */
function safeName(text, fallback = '字帖') {
  return String(text || '').replace(/[\\/:*?"<>|\r\n\t]/g, '').trim().slice(0, 40) || fallback
}
function stamp() {
  const d = new Date()
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
}
function dataUrl(canvas, mime = 'image/png', quality) {
  return quality == null ? canvas.toDataURL(mime) : canvas.toDataURL(mime, quality)
}
function pagePt(sheet) {
  const [wMm, hMm] = PAGE_MM[sheet.p.page_size] || PAGE_MM.A4
  return [wMm / 25.4 * 72, hMm / 25.4 * 72]
}
function nameFor(params, ext) {
  return `${safeName(params.title || '字帖')}_${stamp()}.${ext}`
}
function blobOf(bytes, mime) { return new Blob([bytes], { type: mime }) }

/** 逐页渲染成 JPEG 并组装 PDF；一次只持有一页像素 */
function buildPdf(params, indices) {
  const sheet = new Sheet(params)
  const [wPt, hPt] = pagePt(sheet)
  const pages = []
  for (const i of indices) {
    const { canvas } = renderCanvas(params, i)
    const jpeg = dataUrlBytes(dataUrl(canvas, 'image/jpeg', 0.94))
    pages.push({ jpeg, w: canvas.width, h: canvas.height, wPt, hPt })
    canvas.width = canvas.height = 0
  }
  return makePdf(pages)
}

function splitText(text, size) {
  const chunks = []
  for (let i = 0; i < text.length; i += size) chunks.push(text.slice(i, i + size))
  return chunks.length ? chunks : [text]
}

export const localApi = {
  async meta() {
    return {
      fonts: fontList(),
      charsets: STATIC.charsets.map(({ id, name, desc, count }) => ({ id, name, desc, count })),
      library: STATIC.library,
      grids: STATIC.grids,
      page_sizes: STATIC.page_sizes,
      defaults: { ...STATIC.defaults, font_id: 'tk', traditional: false },
      capabilities: {
        traditional: false, version: STATIC.version + '+static',
        formats: ['pdf', 'png'], modes: 7, directions: 2, engine: 'browser'
      }
    }
  },
  async fonts() { return { fonts: fontList(), bundled: 0, system: fontList().length } },

  async uploadFont(file) {
    if (typeof FontFace === 'undefined' || !document.fonts) {
      throw new Error('当前浏览器不支持本地字体加载')
    }
    const id = `custom_${customFonts.length + 1}`
    const name = file.name.replace(/\.(ttf|otf|ttc|woff2?)$/i, '') || id
    const face = new FontFace(name, await file.arrayBuffer())
    await face.load()
    document.fonts.add(face)
    const item = { id, name, family: `"${name}",serif`, source: 'custom' }
    customFonts.push(item)
    return { font: { id, name, source: 'custom', has_cjk: true, sample: '永', coverage: 100 } }
  },

  async preview(params, page = 0) {
    // 预览固定按 150dpi 出图，避免 300dpi 拖动参数时卡顿；
    // 版面线性依赖 dpi，缩放后的行数／页数与导出完全一致。
    const sheet = new Sheet({ ...withDefaults(params), dpi: 150 })
    const idx = Math.max(0, Math.min(page, sheet.pages.length - 1))
    const { canvas } = renderCanvas({ ...sheet.p, dpi: 150 }, idx, 820)
    return {
      image: dataUrl(canvas), pages: sheet.pages.length, char_count: sheet.charCount,
      warnings: sheet.warnings, missing: [], font_id: sheet.p.font_id
    }
  },

  async charset(id) {
    const item = STATIC.charsets.find(c => c.id === id)
    if (!item) throw new Error(`没有这张字表：${id}`)
    return { id, chars: item.chars, count: item.count }
  },

  async library() { return { groups: STATIC.library } },

  async analyze(text, title = '', keepPunct = true) { return analyze(text, title, keepPunct) },

  async thumbnails(params, width = 170, limit = 40) {
    const sheet = new Sheet(params)
    const total = sheet.pages.length
    const thumbs = []
    for (let i = 0; i < Math.min(total, limit); i++) {
      const { canvas } = renderCanvas({ ...sheet.p, dpi: 150 }, i, width)
      thumbs.push(dataUrl(canvas, 'image/jpeg', 0.8))
    }
    return { thumbs, total, truncated: total > limit }
  },

  async printPages(params, pageRange = '', limit = 30) {
    const sheet = new Sheet(params)
    const indices = parsePageRange(pageRange, sheet.pages.length)
    if (indices.length > limit) throw new Error(`一次最多打印 ${limit} 页，当前选了 ${indices.length} 页，请缩小页码范围`)
    const pages = indices.map(i => dataUrl(renderCanvas({ ...sheet.p, dpi: 200 }, i).canvas, 'image/jpeg', 0.94))
    return { pages, total: sheet.pages.length, selected: indices.length }
  },

  async parseFile(file) {
    let text = await file.text()
    text = text.replace(/^---[\s\S]*?---\s*/, '')       // front matter
      .replace(/```[\s\S]*?```/g, '')                    // 代码块
      .replace(/^\s{0,3}#{1,6}\s+/gm, '')               // Markdown 标题
      .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')        // 链接与图片
      .replace(/[*_`>]/g, '')
    return { text: text.trim(), filename: file.name }
  },

  async exportSheet(params, opts = {}) {
    const o = typeof opts === 'number' ? { splitSize: opts } : opts
    const p = withDefaults(params)
    const sheet = new Sheet(p)
    const indices = parsePageRange(o.pageRange || '', sheet.pages.length)
    const format = o.format || 'pdf'
    const stampName = safeName(p.title || '字帖')

    if (o.splitSize > 0) {
      const files = []
      const chunks = splitText(p.text, o.splitSize)
      chunks.forEach((chunk, i) => {
        const part = { ...p, text: chunk, title: `${stampName}·第${i + 1}册` }
        const s = new Sheet(part)
        const bytes = format === 'png'
          ? dataUrlBytes(dataUrl(renderCanvas(part, 0).canvas))
          : buildPdf(part, [...Array(s.pages.length).keys()])
        files.push({ name: `${stampName}_第${i + 1}册_${stamp()}.${format === 'png' ? 'png' : 'pdf'}`, bytes })
      })
      return { blob: blobOf(makeZip(files), 'application/zip'),
        name: `${stampName}_分册${chunks.length}册_${stamp()}.zip` }
    }

    if (format === 'png') {
      if (indices.length === 1) {
        const bytes = dataUrlBytes(dataUrl(renderCanvas(p, indices[0]).canvas))
        return { blob: blobOf(bytes, 'image/png'), name: nameFor(p, 'png') }
      }
      const files = indices.map(i => ({
        name: `${stampName}_第${String(i + 1).padStart(2, '0')}页.png`,
        bytes: dataUrlBytes(dataUrl(renderCanvas(p, i).canvas))
      }))
      return { blob: blobOf(makeZip(files), 'application/zip'),
        name: `${stampName}_${indices.length}页_${stamp()}.zip` }
    }

    return { blob: blobOf(buildPdf(p, indices), 'application/pdf'), name: nameFor(p, 'pdf') }
  }
}

/* 暴露纯逻辑给 Node 测试（浏览器里不会用到） */
export const __test = { hexRgb, mix, pagePt, fontList, fontFamily, splitText }
