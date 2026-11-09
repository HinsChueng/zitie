/**
 * 前端 api.js 的运行时回归测试（不需要浏览器）。
 *
 * 用法：
 *   node scripts/smoke-api.mjs                       # 默认打 http://127.0.0.1:8000
 *   ZITIE_BASE=http://127.0.0.1:8017 node scripts/smoke-api.mjs
 *
 * 背景：曾出现 post() 漏写 await、把 Promise 传给 handle() 的事故，
 * 表现为页面顶部「请求失败 (undefined)」且预览区空白。构建与后端接口
 * 冒烟都发现不了，必须真实调用一次前端 api.js 的每个方法。
 */
const BASE = process.env.ZITIE_BASE || 'http://127.0.0.1:8000'

// 浏览器里 BASE 是相对路径 '/api'，Node fetch 需要绝对地址，这里做一层转换
const realFetch = globalThis.fetch
globalThis.fetch = (url, opts) =>
  realFetch(String(url).startsWith('http') ? url : `${BASE}${url}`, opts)

let passed = 0
let failed = 0
function check(name, cond, extra = '') {
  if (cond) { passed++; console.log(`  PASS  ${name}${extra ? ' · ' + extra : ''}`) }
  else { failed++; console.log(`  FAIL  ${name}${extra ? ' · ' + extra : ''}`) }
}

try {
  const health = await realFetch(`${BASE}/api/health`, { signal: AbortSignal.timeout(5000) })
  if (!health.ok) throw new Error(`HTTP ${health.status}`)
} catch (e) {
  console.error(`后端未就绪：${BASE} (${e.message})`)
  console.error(`请先运行：python run.py --port ${new URL(BASE).port || 8000} --no-browser`)
  process.exit(2)
}

const { api } = await import('../src/api.js')

console.log(`\n前端 API 运行时冒烟 @ ${BASE}\n`)

/* ---------- GET ---------- */
const meta = await api.meta()
check('meta() 返回字体/格型/字表/文库',
  Array.isArray(meta.fonts) && Array.isArray(meta.grids) &&
  Array.isArray(meta.charsets) && Array.isArray(meta.library),
  `${meta.fonts.length} 字体 / ${meta.grids.length} 格型 / ${meta.library.length} 类文库`)
check('meta() 带默认参数', meta.defaults && typeof meta.defaults === 'object')

const fonts = await api.fonts()
check('fonts() 返回字体清单', Array.isArray(fonts.fonts), `${fonts.fonts.length} 款`)

const lib = await api.library()
check('library() 返回分组且含篇目',
  Array.isArray(lib.groups) ? lib.groups.some(g => g.items?.length)
                            : Array.isArray(lib) && lib.length > 0)
check('library() 篇目带难度星级',
  lib.groups?.[0]?.items?.some(i => i.level >= 1 && i.level <= 5))
check('library() 按古今两级分类且含现代篇目',
  lib.groups?.some(g => g.era === '古代') && lib.groups?.some(g => g.era === '现代') &&
  lib.groups.some(g => g.era === '现代' && g.items?.length),
  `古代 ${lib.groups?.filter(g => g.era === '古代').reduce((n, g) => n + g.items.length, 0)} 篇 / ` +
  `现代 ${lib.groups?.filter(g => g.era === '现代').reduce((n, g) => n + g.items.length, 0)} 篇`)

const charsetId = meta.charsets?.[0]?.id
if (charsetId) {
  const cs = await api.charset(charsetId)
  check('charset() 返回字表', typeof (cs.chars || cs.text || cs) === 'string' ||
    Array.isArray(cs.chars || cs.items), charsetId)
}

/* ---------- POST：这正是出过事故的路径 ---------- */
const params = {
  ...meta.defaults,
  title: '冒烟测试',
  text: '床前明月光，疑是地上霜。举头望明月，低头思故乡。',
  auto_rows: false,
  rows: 6
}

const preview = await api.preview(params, 0)
check('preview() 返回 base64 PNG + 页数',
  typeof preview.image === 'string' && preview.image.startsWith('data:image/') &&
  Number.isInteger(preview.pages) && preview.pages >= 1,
  `${preview.pages} 页 / ${preview.char_count} 格`)

const analysis = await api.analyze(params.text, params.title)
check('analyze() 离线难度与推荐',
  analysis.level >= 1 && analysis.level <= 5 && analysis.recommend?.length === 3 &&
  Array.isArray(analysis.reasons),
  `${analysis.level}★ ${analysis.label} / 推荐 ${analysis.recommend?.length} 篇`)

const vPreview = await api.preview({ ...params, direction: 'vertical' }, 0)
check('preview() 竖排也能出图',
  typeof vPreview.image === 'string' && vPreview.image.startsWith('data:image/'),
  `${vPreview.pages} 页`)

const thumbs = await api.thumbnails(params, 90, 5)
check('thumbnails() 返回缩略图数组', Array.isArray(thumbs.thumbs) && thumbs.thumbs.length >= 1,
  `${thumbs.thumbs.length} 张`)

const printed = await api.printPages(params, '', 5)
check('printPages() 返回可打印页', Array.isArray(printed.pages) && printed.pages.length >= 1,
  `${printed.pages.length} 页`)

const pdf = await api.exportSheet(params, { format: 'pdf' })
check('exportSheet() PDF 有内容且文件名正确',
  pdf.blob.size > 1000 && /\.pdf$/i.test(pdf.name), `${pdf.blob.size} bytes / ${pdf.name}`)

const png = await api.exportSheet(params, { format: 'png' })
check('exportSheet() PNG 有内容', png.blob.size > 1000 && /\.(png|zip)$/i.test(png.name),
  `${png.blob.size} bytes / ${png.name}`)

const badRange = await api.exportSheet(params, { format: 'pdf', pageRange: '99-100' })
  .then(() => null, e => e)
check('非法页码范围被后端拒绝且错误信息可读',
  badRange instanceof Error && !/undefined/.test(badRange.message),
  badRange?.message || '未报错')

/* ---------- 上传解析 ---------- */
const formFile = new File(['春眠不觉晓，处处闻啼鸟。'], 'poem.txt', { type: 'text/plain' })
const parsed = await api.parseFile(formFile)
check('parseFile() 解析正文', typeof parsed.text === 'string' && parsed.text.includes('春眠'),
  parsed.text?.slice(0, 12))

console.log(`\n结果：${passed} 通过 / ${failed} 失败\n`)
process.exit(failed ? 1 : 0)
