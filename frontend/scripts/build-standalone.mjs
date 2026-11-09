/**
 * 把 Vite 产物收成一个自包含的单文件 HTML，供「没有服务器」的场景使用。
 *
 * 用法：npm run build && npm run build:standalone
 * 输出：standalone/index.html
 *
 * 单文件可以直接双击（file://）打开，也可以放进本机／内网的静态目录；
 * 页面检测不到 /api/health 会自动切到浏览器内渲染引擎。
 */
import { readFile, writeFile, mkdir, readdir, copyFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const web = resolve(root, '../backend/web')
const outDir = resolve(root, '../standalone')

const indexPath = join(web, 'index.html')
if (!existsSync(indexPath)) {
  console.error('找不到 backend/web/index.html，请先执行 npm run build')
  process.exit(2)
}

let html = await readFile(indexPath, 'utf8')

// 内联 CSS
html = await replaceAll(html, /<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"[^>]*>/g,
  async (full, href) => {
    const file = join(web, href.replace(/^\.\//, ''))
    const css = await readFile(file, 'utf8')
    return `<style>\n${css}\n</style>`
  })

// 内联 JS（转义 </script 以免提前闭合）
html = await replaceAll(html, /<script([^>]*)src="([^"]+)"([^>]*)><\/script>/g,
  async (full, before, src, after) => {
    const file = join(web, src.replace(/^\.\//, ''))
    const js = (await readFile(file, 'utf8')).replace(/<\/script/gi, '<\\/script')
    const attrs = (before + after).replace(/\s*crossorigin/gi, '').trim()
    return `<script ${attrs}>\n${js}\n</script>`
  })

if (/src="\.\/assets\/|href="\.\/assets\//.test(html)) {
  console.error('仍有未内联的 assets 引用，单文件可能不完整')
  process.exit(1)
}

await mkdir(outDir, { recursive: true })
await writeFile(join(outDir, 'index.html'), html, 'utf8')

// 非 HTML 的静态资源（favicon 等）一并带上
for (const name of await readdir(web)) {
  if (name === 'index.html' || name === 'assets') continue
  const src = join(web, name)
  if (existsSync(src) && !name.startsWith('.')) await copyFile(src, join(outDir, name))
}

const kb = (Buffer.byteLength(html, 'utf8') / 1024).toFixed(1)
console.log(`已生成 standalone/index.html（${kb} KB，单文件、零外部请求）`)
console.log('可用方式：双击打开 / 发文件 / python -m http.server（本机或内网）')

async function replaceAll(text, re, fn) {
  const matches = [...text.matchAll(re)]
  let out = '', last = 0
  for (const m of matches) {
    out += text.slice(last, m.index)
    out += await fn(m[0], ...m.slice(1))
    last = m.index + m[0].length
  }
  return out + text.slice(last)
}
