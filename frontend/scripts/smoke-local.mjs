/**
 * 浏览器引擎（local-engine.js）的运行时回归，不需要浏览器。
 *
 * 用最小 Canvas/DOM 桩跑通 preview / thumbnails / printPages / exportSheet
 * 的完整调用链，并断言编排规则与二进制产物结构。
 *
 * 用法：node scripts/smoke-local.mjs
 */
import { Buffer } from 'node:buffer'

/* ---------- 最小 Canvas / DOM 桩 ---------- */
const calls = { fillText: [], strokeText: [], line: 0, rect: 0, arc: 0 }
function mockCtx() {
  const noop = () => {}
  return {
    save: noop, restore: noop, scale: noop, beginPath: noop, closePath: noop,
    moveTo: noop, lineTo: noop, stroke: noop, fill: noop, strokeRect: noop,
    fillRect() { calls.rect++ }, arc() { calls.arc++ },
    setLineDash: noop, createPattern: () => ({ __pattern: true }),
    fillText(ch, x, y) { calls.fillText.push({ ch, x, y }) },
    strokeText(ch, x, y) { calls.strokeText.push({ ch, x, y }) },
    measureText(ch) {
      const size = parseFloat(String(this.font).replace('px', '')) || 20
      return {
        width: size * 0.9, actualBoundingBoxLeft: 0,
        actualBoundingBoxRight: size * 0.8,
        actualBoundingBoxAscent: size * 0.72,
        actualBoundingBoxDescent: size * 0.08
      }
    },
    strokeStyle: '', fillStyle: '', lineWidth: 1, font: '', textAlign: '',
    textBaseline: '', lineJoin: '', lineCap: ''
  }
}
class MockCanvas {
  constructor() { this.width = 0; this.height = 0 }
  getContext() { return mockCtx() }
  toDataURL(mime = 'image/png') {
    const payload = `fake-${this.width}x${this.height}-${mime}`
    return `data:${mime};base64,${Buffer.from(payload).toString('base64')}`
  }
}
globalThis.document = { createElement: () => new MockCanvas(), fonts: { add() {} } }

/* ---------- 断言 ---------- */
let passed = 0, failed = 0
function check(name, cond, extra = '') {
  if (cond) { passed++; console.log(`  PASS  ${name}${extra ? ' · ' + extra : ''}`) }
  else { failed++; console.log(`  FAIL  ${name}${extra ? ' · ' + extra : ''}`) }
}

const E = await import('../src/local-engine.js')
const { STATIC } = await import('../src/static-data.js')
const { localApi } = E

const P = (extra = {}) => ({
  ...STATIC.defaults,
  title: '静夜思', text: '床前明月光，疑是地上霜。举头望明月，低头思故乡。',
  auto_rows: false, rows: 6, columns: 10, dpi: 150,
  ...extra
})

console.log('\n浏览器引擎冒烟（无服务端）\n')

/* ---------- 静态数据 ---------- */
const meta = await localApi.meta()
check('meta() 形状与后端一致',
  Array.isArray(meta.fonts) && Array.isArray(meta.grids) &&
  Array.isArray(meta.charsets) && Array.isArray(meta.library) && meta.defaults,
  `${meta.fonts.length} 字体 / ${meta.grids.length} 格型 / ${meta.library.length} 类文库`)
check('meta() 明确标注浏览器引擎且转繁体不可用',
  meta.capabilities.engine === 'browser' && meta.capabilities.traditional === false)
check('默认 font_id 在静态字体表中存在', meta.fonts.some(f => f.id === meta.defaults.font_id))

/* ---------- 文本编排 ---------- */
check('normalize 丢空白与 emoji、保留汉字数字标点',
  E.normalize('床前 明月光，\n疑是地上霜🙂 123') === '床前明月光，\n疑是地上霜123')
check('wrap 避头尾：标点不落在行首',
  E.wrap('一二三四，五六七八九十', 5, true, false).every(l => !/^[。，、；：？！]/.test(l)),
  E.wrap('一二三四，五六七八九十', 5, true, false).join('|'))
check('wrap 每行不超格数',
  E.normalize('床前明月光，疑是地上霜。').length > 0 &&
  E.wrap('床前明月光疑是地上霜举头望明月低头思故乡', 7).every(l => l.length <= 7))
check('break_at_punct 在句读处断行',
  E.wrap('床前明月光，疑是地上霜。', 6, true, true)[0] === '床前明月光，')

/* ---------- 练习模式 ---------- */
const rotate = E.composeRows(P({ mode: 'rotate', cycle_demo: 1, cycle_trace: 1, cycle_blank: 2 }))
check('rotate 三行循环结构（示范→描红→空→空）',
  rotate.length % 4 === 0 && rotate[0][0]?.style === 'demo' &&
  rotate[1][0]?.style === 'trace' && rotate[2].length === 0 && rotate[3].length === 0,
  `${rotate.length} 行`)

const fade = new E.Sheet(P({ mode: 'fade' }))
const fadeCells = fade.layoutPage(0).cells
const traceFade = fadeCells.filter(c => c.style === 'gray').slice(0, 4)
check('渐隐：浓度随列序递减且首字实心',
  fadeCells[0].style === 'demo' && traceFade.length >= 3 &&
  traceFade.every((c, i, a) => i === 0 || c.opacity < a[i - 1].opacity),
  traceFade.map(c => c.opacity.toFixed(3)).join(' > '))

const card = new E.Sheet(P({ mode: 'card', card_cells: 6, card_trace: 2 }))
const cardRow = card.layoutPage(0).cells.filter(c => c.row === 0)
check('生字卡：范字→描红→空白的重复块',
  cardRow.length > 0 && cardRow[0]?.style === 'demo' &&
  cardRow[1]?.style === 'gray' && cardRow[2]?.style === 'gray',
  `首行 ${cardRow.length} 个有字格`)

/* ---------- 竖排 ---------- */
const hSheet = new E.Sheet(P({ mode: 'demo' }))
const vSheet = new E.Sheet(P({ mode: 'demo', direction: 'vertical' }))
check('竖排网格宽高互换、编排行数不变',
  hSheet.gridW === vSheet.gridH && hSheet.gridH === vSheet.gridW &&
  hSheet.rows.length === vSheet.rows.length,
  `横 ${hSheet.gridW}×${hSheet.gridH} / 竖 ${vSheet.gridW}×${vSheet.gridH}`)
const vCells = vSheet.layoutPage(0).cells
check('竖排首列在最右、字自上而下',
  vCells[0].x > vCells[vCells.length - 1].x &&
  vCells.filter(c => c.x === vCells[0].x).every((c, i, a) => i === 0 || c.y > a[i - 1].y))
check('竖排下不适用的格型自动回退田字格',
  vSheet.warnings.length >= 0 &&
  new E.Sheet(P({ direction: 'vertical', grid: 'pinyin4' })).layoutPage(0).grid === 'tian')

/* ---------- 选页 ---------- */
check('parsePageRange 解析 1-2,4 且去重', E.parsePageRange('1-2,4,2', 5).join(',') === '0,1,3')
check('parsePageRange 空串代表全部', E.parsePageRange('', 3).join(',') === '0,1,2')
check('parsePageRange 越界报错可读',
  (() => { try { E.parsePageRange('99', 3); return false } catch (e) { return /超出范围/.test(e.message) } })())

/* ---------- 绘制调用链 ---------- */
const ctx = mockCtx()
E.paint(ctx, hSheet, 0, 1)
check('paint 真的画了字与格线', calls.fillText.length > 0 && calls.rect === 1,
  `${calls.fillText.length} 个字 / 1 次纸底填充`)

/* ---------- 难度 ---------- */
const an = await localApi.analyze('床前明月光，疑是地上霜。举头望明月，低头思故乡。', '静夜思')
check('analyze 与后端同样的 1–5 级 + 3 篇推荐',
  an.level >= 1 && an.level <= 5 && an.recommend.length === 3 && Array.isArray(an.reasons),
  `${an.level}★ ${an.label} / ${an.recommend.map(x => x.title).join('、')}`)
check('文库星级覆盖 1–4 级',
  new Set(STATIC.library_flat.map(x => x.level)).size >= 3)

/* ---------- 本地 API 全链路 ---------- */
const preview = await localApi.preview(P(), 0)
check('preview() 返回 data URL 与页数',
  preview.image.startsWith('data:image/png;base64,') && preview.pages >= 1 &&
  preview.char_count > 0, `${preview.pages} 页 / ${preview.char_count} 格`)

const thumbs = await localApi.thumbnails(P(), 90, 5)
check('thumbnails() 返回缩略图数组', Array.isArray(thumbs.thumbs) && thumbs.thumbs.length >= 1)

const printed = await localApi.printPages(P(), '', 5)
check('printPages() 返回可打印页', Array.isArray(printed.pages) && printed.pages.length >= 1)

const vPreview = await localApi.preview(P({ direction: 'vertical' }), 0)
check('preview() 竖排也能出图', vPreview.image.startsWith('data:image/'))

const cs = await localApi.charset('grade1')
check('charset() 返回分级字表', typeof cs.chars === 'string' && cs.chars.length === 100)
const lib = await localApi.library()
check('library() 返回分组篇目', lib.groups.some(g => g.items.length > 0))
const libItems = lib.groups.flatMap(g => g.items)
check('静态版文库同样按古今分类且含史记／现代名篇',
  lib.groups.some(g => g.era === '古代') && lib.groups.some(g => g.era === '现代') &&
  lib.groups.some(g => g.name === '史记') && lib.groups.some(g => g.name === '先秦史传') &&
  libItems.some(i => i.era === '现代' && i.author === '朱自清'),
  `${lib.groups.length} 类 / ${libItems.length} 篇`)
const parsed = await localApi.parseFile(new File(['# 春晓\n\n春眠不觉晓，处处闻啼鸟。'], 'a.md'))
check('parseFile() 去掉 Markdown 标题', parsed.text.includes('春眠') && !parsed.text.includes('#'))

/* ---------- 导出：PDF / PNG / ZIP ---------- */
const pdf = await localApi.exportSheet(P(), { format: 'pdf' })
const pdfBytes = new Uint8Array(await pdf.blob.arrayBuffer())
const pdfText = Buffer.from(pdfBytes).toString('latin1')
check('exportSheet() PDF 头尾与 xref 完整',
  pdfText.startsWith('%PDF-') && pdfText.trimEnd().endsWith('%%EOF') &&
  /xref\n0 \d+/.test(pdfText) && pdfText.includes('/DCTDecode') && pdfText.includes('startxref'),
  `${pdf.blob.size} bytes / ${pdf.name}`)
check('PDF 页数与 /Type /Page 数量一致',
  (pdfText.match(/\/Type \/Page\b/g) || []).length === preview.pages)

const png = await localApi.exportSheet(P(), { format: 'png', pageRange: '1' })
const pngHead = new Uint8Array(await png.blob.arrayBuffer()).slice(0, 8)
check('exportSheet() 单页 PNG',
  /\.png$/.test(png.name) && png.blob.type === 'image/png' && pngHead.length === 8,
  `${png.blob.size} bytes（Canvas 桩数据，仅验证链路）`)

const pngZip = await localApi.exportSheet(P({ text: '天地玄黄宇宙洪荒日月盈昃辰宿列张'.repeat(20), rows: 4 }),
  { format: 'png' })
const zipBytes = new Uint8Array(await pngZip.blob.arrayBuffer())
check('exportSheet() 多页 PNG 打成 ZIP',
  /\.zip$/.test(pngZip.name) && zipBytes[0] === 0x50 && zipBytes[1] === 0x4B &&
  Buffer.from(zipBytes).toString('latin1').includes('.png'), `${pngZip.blob.size} bytes`)

const split = await localApi.exportSheet(P(), { format: 'pdf', splitSize: 10 })
check('exportSheet() 分册打包 ZIP', /\.zip$/.test(split.name) && split.blob.size > 200,
  `${split.blob.size} bytes / ${split.name}`)

const bad = await localApi.exportSheet(P(), { format: 'pdf', pageRange: '99' }).then(() => null, e => e)
check('非法页码报错可读', bad instanceof Error && /超出范围/.test(bad.message), bad?.message)

console.log(`\n结果：${passed} 通过 / ${failed} 失败\n`)
process.exit(failed ? 1 : 0)
