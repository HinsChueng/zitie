/** 配置分享：整套参数编进 URL hash，不经过服务端。
 *  有 CompressionStream 时用 deflate 压缩（约省一半长度），否则退回 UTF-8 base64。
 *  前缀 c. = 压缩，j. = 明文，方便解码端判断。
 */

function toB64url(bytes) {
  let bin = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function fromB64url(text) {
  const b64 = text.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - text.length % 4) % 4)
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

export async function encodeConfig(params) {
  const raw = new TextEncoder().encode(JSON.stringify({ v: 2, p: params }))
  if (typeof CompressionStream !== 'undefined') {
    try {
      const stream = new Blob([raw]).stream().pipeThrough(new CompressionStream('deflate'))
      const buf = await new Response(stream).arrayBuffer()
      return 'c.' + toB64url(new Uint8Array(buf))
    } catch (_) { /* 压缩不可用时退回明文 */ }
  }
  return 'j.' + toB64url(raw)
}

export async function decodeConfig(code) {
  if (!code || code[1] !== '.') throw new Error('分享链接格式不对')
  let bytes = fromB64url(code.slice(2))
  if (code[0] === 'c') {
    if (typeof DecompressionStream === 'undefined') {
      throw new Error('当前浏览器无法解压该链接，请换用生成链接时的浏览器')
    }
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate'))
    bytes = new Uint8Array(await new Response(stream).arrayBuffer())
  } else if (code[0] !== 'j') {
    throw new Error('无法识别的分享链接')
  }
  const obj = JSON.parse(new TextDecoder().decode(bytes))
  if (!obj || typeof obj.p !== 'object' || obj.p === null) {
    throw new Error('分享链接里没有字帖配置')
  }
  return obj.p
}

export function parseHash(hash) {
  const m = /^#cfg=(.+)$/.exec(hash || '')
  return m ? m[1] : ''
}
