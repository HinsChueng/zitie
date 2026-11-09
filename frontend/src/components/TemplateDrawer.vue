<script setup>
/** 我的模板 + 分享链接：整套参数（含正文）本地保存，或压进 URL 发给别人。 */
import { ref } from 'vue'

defineProps({
  open: { type: Boolean, default: false },
  templates: { type: Array, default: () => [] },
  tab: { type: String, default: 'templates' },
  shareUrl: { type: String, default: '' }
})
const emit = defineEmits(['close', 'save', 'apply', 'remove', 'share', 'share-copied', 'update:tab'])

const name = ref('')
const linkInput = ref(null)

function save() {
  const value = name.value.trim()
  if (!value) return
  emit('save', value)
  name.value = ''
}

async function copyLink() {
  const el = linkInput.value
  if (!el) return
  try {
    await navigator.clipboard.writeText(el.value)
  } catch (_) {
    el.select()
    document.execCommand('copy')
  }
  emit('share-copied')
}
</script>

<template>
  <div v-if="open" class="mask" @click.self="emit('close')">
    <div class="modal modal-narrow">
      <div class="modal-main">
        <header>
          <div class="seg" style="width:220px">
            <button :class="{ on: tab === 'templates' }" @click="emit('update:tab', 'templates')">我的模板</button>
            <button :class="{ on: tab === 'share' }" @click="emit('update:tab', 'share')">分享链接</button>
          </div>
          <button class="btn" @click="emit('close')">关闭</button>
        </header>

        <div v-if="tab === 'templates'" class="drawer-body">
          <p class="hint">把当前这一整套设置（含正文、字库、版式）存下来，下次一键套用。数据只存在本机浏览器。</p>
          <div class="row" style="margin:10px 0 16px">
            <input v-model="name" type="text" placeholder="给这套字帖起个名，例如：三年级 · 田字格描红"
                   @keyup.enter="save" />
            <button class="btn primary" style="flex:0 0 76px" :disabled="!name.trim()" @click="save">保存</button>
          </div>

          <div class="tpl-list">
            <div v-for="t in templates" :key="t.id" class="tpl-row">
              <div style="min-width:0">
                <b>{{ t.name }}</b>
                <div class="hint">{{ t.at }} · {{ (t.params?.text || '').length }} 字</div>
              </div>
              <button class="btn ghost" @click="emit('apply', t.id)">套用</button>
              <button class="btn ghost" @click="emit('remove', t.id)">删除</button>
            </div>
            <p v-if="!templates.length" class="hint" style="padding:14px 0">还没有模板，先存一个试试</p>
          </div>
        </div>

        <div v-else class="drawer-body">
          <p class="hint">把整套配置压进链接发给别人，对方打开即还原同样的字帖。链接不经过服务器，也不会上传正文。</p>
          <button class="btn primary" style="margin:12px 0" @click="emit('share')">生成并复制链接</button>
          <div v-if="shareUrl" class="share-box">
            <input ref="linkInput" :value="shareUrl" readonly @focus="$event.target.select()" />
            <button class="btn ghost" @click="copyLink">复制</button>
          </div>
          <p class="hint" style="margin-top:10px">链接较长属正常现象；正文越长链接越长，超长时建议改用模板文件或导出 PDF。</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-narrow { width: min(620px, 92vw); height: auto; max-height: 76vh; }
.drawer-body { padding: 16px 18px 22px; overflow-y: auto; }
.tpl-list { display: flex; flex-direction: column; gap: 6px; }
.tpl-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 9px;
}
.tpl-row > div:first-child { flex: 1; }
.tpl-row .btn { flex: 0 0 auto; height: 28px; padding: 0 10px; }
.share-box { display: flex; gap: 8px; }
.share-box input {
  flex: 1;
  min-width: 0;
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: var(--panel);
  color: var(--text);
  font-size: 12px;
}
</style>
