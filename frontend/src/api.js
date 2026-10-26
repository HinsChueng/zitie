const BASE = '/api'

async function handle(res) {
  if (!res.ok) {
    let msg = `请求失败 (${res.status})`
    try {
      const data = await res.json()
      if (data.detail) msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
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

export const api = {
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
    const res = await handle(await fetch(`${BASE}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ params, page, full })
    }))
    return res.json()
  },

  async charset(id) {
    const res = await handle(await fetch(`${BASE}/charset/${id}`))
    return res.json()
  },

  async parseFile(file) {
    const form = new FormData()
    form.append('file', file)
    const res = await handle(await fetch(`${BASE}/parse`, { method: 'POST', body: form }))
    return res.json()
  },

  async exportSheet(params, splitSize = 0) {
    const res = await handle(await fetch(`${BASE}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ params, split_size: splitSize })
    }))
    return { blob: await res.blob(), name: filenameFrom(res, '字帖.pdf') }
  }
}
