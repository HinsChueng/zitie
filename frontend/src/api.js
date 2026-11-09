/**
 * 双引擎 API 层。
 *
 *  - 有 Python 服务：走 /api/*，高精度渲染、系统全字体、pypdf 合并；
 *  - 无 Python 服务（本地 HTML / 内网静态目录）：自动切到 local-engine.js，
 *    全部计算在浏览器里完成，页面、参数、分享链接完全不变。
 *
 * 探测只做一次，结果缓存。也可用 ?engine=local / ?engine=remote 强制指定，
 * 便于离线开发或排查问题。
 */
import { localApi } from './local-engine.js'

const BASE = '/api'

/** 把 FastAPI 的 422 detail 数组摊平成一句人能读懂的话 */
function readable(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map(d => {
      const field = (d.loc || []).filter(x => !['body', 'params', 'query'].includes(x)).join('.')
      return `${field ? field + '：' : ''}${d.msg || d.type || ''}`
    }).join('；')
  }
  return JSON.stringify(detail)
}

async function handle(res) {
  // 兜底：防止把 fetch 返回的 Promise 误当 Response 传入，否则会报出无意义的 (undefined)
  if (!res || typeof res.ok !== 'boolean' || typeof res.json !== 'function') {
    throw new Error('内部错误：请求未正确发送（fetch 缺少 await）')
  }
  if (!res.ok) {
    let msg = `请求失败 (HTTP ${res.status})`
    try {
      const data = await res.json()
      if (data.detail) msg = readable(data.detail)
    } catch (_) { /* 忽略非 JSON 响应 */ }
    throw new Error(msg)
  }
  return res
}

function filenameFrom(res, fallback) {
  const cd = res.headers.get('Content-Disposition') || ''
  const m = /filename\*=UTF-8''([^;]+)/i.exec(cd)
  if (m) {
    try { return decodeURIComponent(m[1]) } catch (_) { /* 忽略解码失败 */ }
  }
  return fallback
}

async function post(path, body) {
  return handle(await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }))
}

const remote = {
  async meta() {
    const res = await handle(await fetch(`${BASE}/meta`))
    return res.json()
  },

  async fonts(refresh = false) {
    const res = await handle(await fetch(`${BASE}/fonts${refresh ? '?refresh=1' : ''}`))
    return res.json()
  },

  async uploadFont(file) {
    const form = new FormData()
    form.append('file', file)
    const res = await handle(await fetch(`${BASE}/fonts/upload`, { method: 'POST', body: form }))
    return res.json()
  },

  async preview(params, page = 0, full = false) {
    const res = await post('/preview', { params, page, full })
    return res.json()
  },

  async charset(id) {
    const res = await handle(await fetch(`${BASE}/charset/${id}`))
    return res.json()
  },

  async library() {
    const res = await handle(await fetch(`${BASE}/library`))
    return res.json()
  },

  async analyze(text, title = '', keepPunct = true) {
    const res = await post('/analyze', { text, title, keep_punct: keepPunct })
    return res.json()
  },

  async thumbnails(params, width = 170, limit = 40) {
    const res = await post('/thumbnails', { params, width, limit })
    return res.json()
  },

  async printPages(params, pageRange = '', limit = 30) {
    const res = await post('/print', { params, page_range: pageRange, limit })
    return res.json()
  },

  async parseFile(file) {
    const form = new FormData()
    form.append('file', file)
    const res = await handle(await fetch(`${BASE}/parse`, { method: 'POST', body: form }))
    return res.json()
  },

  /** opts 可传数字（兼容旧调用：每册字数）或 { splitSize, format, pageRange } */
  async exportSheet(params, opts = {}) {
    const o = typeof opts === 'number' ? { splitSize: opts } : opts
    const res = await post('/export', {
      params,
      split_size: o.splitSize || 0,
      file_format: o.format || 'pdf',
      page_range: (o.pageRange || '').trim()
    })
    return { blob: await res.blob(), name: filenameFrom(res, '字帖.pdf') }
  }
}

let enginePromise = null

async function detect() {
  // Node 回归测试没有 location，且 fetch 被包装成绝对地址，直接走后端
  if (typeof location === 'undefined') return remote
  const force = new URLSearchParams(location.search).get('engine')
  if (force === 'local') return localApi
  if (force === 'remote') return remote
  try {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 1500)
    let res
    try { res = await fetch(`${BASE}/health`, { signal: ctrl.signal }) }
    finally { clearTimeout(timer) }
    // 有些静态服务会把未知路径回退成 index.html（200 + text/html），必须校验 JSON
    if (res.ok && (res.headers.get('content-type') || '').includes('json')) {
      const data = await res.json()
      if (data && data.ok === true) return remote
    }
  } catch (_) { /* 连不上 / 超时 / file:// 下 fetch 被拦，都视作无服务端 */ }
  return localApi
}

function engine() {
  if (!enginePromise) enginePromise = detect()
  return enginePromise
}

/** 供界面显示当前模式：server = 桌面版，browser = 无服务端静态版 */
export async function engineMode() {
  return (await engine()) === remote ? 'server' : 'browser'
}

export const api = new Proxy({}, {
  get(_target, key) {
    if (typeof key !== 'string') return undefined
    return async (...args) => {
      const e = await engine()
      const fn = e[key]
      if (typeof fn !== 'function') throw new Error(`接口不存在：${key}`)
      return fn.apply(e, args)
    }
  }
})
