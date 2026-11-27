<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { GROUP_LABEL, GROUP_CLASS, senderDisplayName, senderInitial, post } from '../api.js'

const props = defineProps({
  message: { type: Object, required: true },
  subject: { type: String, default: '' },
  body: { type: String, default: '' },
  editAlias: { type: Boolean, default: false }
})
defineEmits(['source', 'collapse'])

const failedImages = ref(new Set())
const aliasOpen = ref(false)
const aliasDraft = ref('')
const aliasSaving = ref(false)
const aliasError = ref('')
const aliasInput = ref(null)
const canEditAlias = computed(() => props.message.channel_key === 'feishu' && !!props.message.sender_id)
const needsAlias = computed(() => senderDisplayName(props.message) === '昵称未同步')

function startAliasEdit() {
  aliasOpen.value = true
  aliasError.value = ''
  aliasDraft.value = needsAlias.value ? '' : String(props.message.sender || '').trim()
  nextTick(() => aliasInput.value?.focus())
}

function toggleAlias() {
  if (aliasOpen.value) {
    aliasOpen.value = false
    aliasError.value = ''
    return
  }
  startAliasEdit()
}

watch(() => props.editAlias, edit => {
  if (edit && canEditAlias.value) startAliasEdit()
}, { immediate: true })

async function saveAlias() {
  const name = aliasDraft.value.trim()
  if (!name || name.length > 50) {
    aliasError.value = '昵称长度需为 1–50 个字符'
    return
  }
  aliasSaving.value = true
  aliasError.value = ''
  try {
    const result = await post('/senders/alias', {
      channel_key: props.message.channel_key,
      sender_id: props.message.sender_id,
      name
    })
    if (!result.ok) {
      aliasError.value = result.error || '保存失败'
      return
    }
    props.message.sender = result.name
    aliasOpen.value = false
  } catch {
    aliasError.value = '保存失败，请稍后重试'
  } finally {
    aliasSaving.value = false
  }
}

const article = computed(() => {
  const text = String(props.body || '').replace(/\r\n?/g, '\n').trim()
  const lines = text ? text.split('\n') : []
  const first = lines[0]?.trim() || ''
  if (props.subject) return { title: props.subject, content: text }
  if (lines.length > 1) return { title: first, content: lines.slice(1).join('\n').trim() }
  if (first.length > 76) return { title: `${first.slice(0, 76)}…`, content: first }
  return { title: first || '无标题消息', content: '' }
})

function parseBlocks(text) {
  const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let paragraph = []
  let list = null

  const flushParagraph = () => {
    const value = paragraph.join('\n').trim()
    if (value) blocks.push({ type: 'paragraph', text: value })
    paragraph = []
  }
  const flushList = () => {
    if (list?.items.length) blocks.push(list)
    list = null
  }
  const flush = () => { flushParagraph(); flushList() }

  for (const raw of lines) {
    const line = raw.trim()
    if (!line) { flush(); continue }

    const markdownHeading = line.match(/^(#{1,4})\s+(.+)$/)
    if (markdownHeading) {
      flush()
      blocks.push({ type: 'heading', level: markdownHeading[1].length, text: markdownHeading[2] })
      continue
    }

    const image = line.match(/^!\[(.*?)]\((https?:\/\/[^)]+)\)$/i)
    if (image) {
      flush()
      blocks.push({ type: 'image-link', alt: image[1] || '图片', url: image[2] })
      continue
    }

    if (/^>\s?/.test(line)) {
      flushParagraph()
      blocks.push({ type: 'quote', text: line.replace(/^>\s?/, '') })
      continue
    }

    const bullet = line.match(/^[-*•·]\s+(.+)$/)
    if (bullet) {
      flushParagraph()
      if (list?.type !== 'bullet') { flushList(); list = { type: 'bullet', items: [] } }
      list.items.push(bullet[1])
      continue
    }

    const ordered = line.match(/^(\d+)[.、)]\s*(.+)$/)
    if (ordered) {
      flushParagraph()
      const text = ordered[2].trim()
      if (text.length <= 46 && !/[。；！？]$/.test(text)) {
        flushList()
        blocks.push({ type: 'heading', level: 3, text: `${ordered[1]}. ${text}` })
      } else {
        if (list?.type !== 'ordered') { flushList(); list = { type: 'ordered', items: [] } }
        list.items.push(text)
      }
      continue
    }

    const chineseHeading = line.match(/^((?:第[一二三四五六七八九十百\d]+[章节部分]|[一二三四五六七八九十百]+[、.]|（[一二三四五六七八九十百]+）))\s*(.{1,52})$/)
    if (chineseHeading && !/[。；！？]$/.test(line)) {
      flush()
      blocks.push({ type: 'heading', level: 2, text: line })
      continue
    }

    flushList()
    paragraph.push(raw)
  }
  flush()
  return blocks
}

const blocks = computed(() => parseBlocks(article.value.content))
const imageAttachments = computed(() => (props.message.attachments || []).filter(a => a.mime?.startsWith('image/')))
const remainingImages = computed(() => imageAttachments.value.slice(1))
const contentBlocks = computed(() => {
  const result = [...blocks.value]
  if (!imageAttachments.value.length) return result
  const firstParagraph = result.findIndex(block => block.type === 'paragraph')
  result.splice(firstParagraph >= 0 ? firstParagraph + 1 : 0, 0, {
    type: 'attachment-image', attachment: imageAttachments.value[0]
  })
  return result
})
const fileAttachments = computed(() => (props.message.attachments || []).filter(a => !a.mime?.startsWith('image/')))
const links = computed(() => (props.message.links || []).filter(link => {
  try { return ['http:', 'https:', 'mailto:'].includes(new URL(link).protocol) } catch { return false }
}))
const conversation = computed(() => String(props.message.conv_title || '').split('｜')[0])

function fileSize(bytes) {
  if (!Number.isFinite(bytes)) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function fileType(mime) {
  if (!mime) return '文件'
  if (mime.includes('pdf')) return 'PDF'
  if (mime.includes('zip') || mime.includes('compressed')) return '压缩包'
  if (mime.includes('word')) return 'Word 文档'
  if (mime.includes('sheet') || mime.includes('excel')) return '表格'
  if (mime.includes('presentation') || mime.includes('powerpoint')) return '演示文稿'
  return mime.split('/')[1]?.toUpperCase() || '文件'
}
</script>

<template>
  <article class="message-article" @click.stop>
    <header class="article-topline">
      <div class="article-kicker"><i></i>消息原文</div>
      <button class="article-source" type="button" @click="$emit('source')">原平台 ↗</button>
    </header>

    <h1 class="article-title">{{ article.title }}</h1>

    <div class="article-byline">
      <span class="byline-avatar">
        <img v-if="message.sender_avatar" :src="message.sender_avatar" :alt="senderDisplayName(message)"
          referrerpolicy="no-referrer" @error="message.sender_avatar = ''">
        <span v-else>{{ senderInitial(message) }}</span>
      </span>
      <b>{{ senderDisplayName(message) }}</b>
      <button v-if="canEditAlias" type="button" class="alias-toggle" @click="toggleAlias">
        {{ needsAlias ? '补充昵称' : '修改昵称' }}
      </button>
      <span class="byline-dot">·</span>
      <span class="byline-conv">{{ conversation }}</span>
      <time :datetime="message.ts">{{ message.ts }}</time>
      <span v-if="message.grp !== 'chatter'" :class="['grp', GROUP_CLASS[message.grp]]">
        {{ GROUP_LABEL[message.grp] }}
      </span>
    </div>

    <form v-if="aliasOpen" class="alias-form" @submit.prevent="saveAlias">
      <label for="sender-alias">手动补充昵称</label>
      <p>{{ needsAlias ? '飞书未返回该用户昵称；' : '' }}保存后会更新此用户的全部历史消息，并优先于后续同步结果。</p>
      <div class="alias-actions">
        <input id="sender-alias" ref="aliasInput" v-model="aliasDraft" maxlength="50" placeholder="输入该用户在飞书中的昵称">
        <button type="submit" :disabled="aliasSaving">{{ aliasSaving ? '保存中…' : '保存昵称' }}</button>
        <button type="button" @click="toggleAlias">取消</button>
      </div>
      <span v-if="aliasError" class="alias-error">{{ aliasError }}</span>
    </form>

    <div class="article-divider"></div>

    <div class="article-content">
      <template v-for="(block, index) in contentBlocks" :key="index">
        <h2 v-if="block.type === 'heading' && block.level <= 2" class="article-h2">{{ block.text }}</h2>
        <h3 v-else-if="block.type === 'heading'" class="article-h3">{{ block.text }}</h3>
        <p v-else-if="block.type === 'paragraph'" class="article-p" :class="{ 'article-lead': index === 0 }">{{ block.text }}</p>
        <blockquote v-else-if="block.type === 'quote'" class="article-quote">{{ block.text }}</blockquote>
        <ol v-else-if="block.type === 'ordered'" class="article-list ordered">
          <li v-for="(item, i) in block.items" :key="i">{{ item }}</li>
        </ol>
        <ul v-else-if="block.type === 'bullet'" class="article-list">
          <li v-for="(item, i) in block.items" :key="i">{{ item }}</li>
        </ul>
        <figure v-else-if="block.type === 'attachment-image'" class="article-figure inline-figure">
          <img v-if="!failedImages.has(block.attachment.id)" :src="`/api/attachments/${block.attachment.id}`"
            :alt="block.attachment.filename" loading="lazy"
            @error="failedImages.add(block.attachment.id)">
          <div v-else class="image-fallback">图片预览不可用</div>
          <figcaption>{{ block.attachment.filename }}</figcaption>
        </figure>
        <a v-else-if="block.type === 'image-link'" class="article-image-link"
          :href="block.url" target="_blank" rel="noopener noreferrer">
          <span>图片</span><b>{{ block.alt }}</b><em>在新窗口查看 ↗</em>
        </a>
      </template>
    </div>

    <section v-if="remainingImages.length" class="article-figures">
      <figure v-for="attachment in remainingImages" :key="attachment.id" class="article-figure">
        <img v-if="!failedImages.has(attachment.id)" :src="`/api/attachments/${attachment.id}`"
          :alt="attachment.filename" loading="lazy"
          @error="failedImages.add(attachment.id)">
        <div v-else class="image-fallback">图片预览不可用</div>
        <figcaption>{{ attachment.filename }}</figcaption>
      </figure>
    </section>

    <section v-if="links.length || fileAttachments.length" class="article-resources">
      <h2 class="resource-title">消息资源</h2>
      <div v-if="links.length" class="resource-block">
        <span class="resource-label">链接 · {{ links.length }}</span>
        <a v-for="(link, index) in links" :key="`link-${index}`" class="resource-link"
          :href="link" target="_blank" rel="noopener noreferrer">
          <span>{{ link }}</span><em>↗</em>
        </a>
      </div>
      <div v-if="fileAttachments.length" class="resource-block">
        <span class="resource-label">附件 · {{ fileAttachments.length }}</span>
        <a v-for="attachment in fileAttachments" :key="attachment.id" class="resource-file"
          :href="`/api/attachments/${attachment.id}`" download>
          <span class="file-icon">↧</span>
          <span class="file-copy"><b>{{ attachment.filename }}</b><i>{{ fileType(attachment.mime) }} · {{ fileSize(attachment.size) }}</i></span>
          <em>下载</em>
        </a>
      </div>
    </section>

    <footer class="article-footer">
      <span>来源已聚合到聚光</span>
      <div>
        <button type="button" @click="$emit('source')">在原平台查看 ↗</button>
        <button type="button" class="collapse" @click="$emit('collapse')">收起正文 ↑</button>
      </div>
    </footer>
  </article>
</template>

<style scoped>
.message-article {
  max-width: 880px; margin: 0 auto 24px; padding: clamp(24px, 4vw, 52px);
  background: var(--surface); border: 1px solid var(--line); border-radius: 16px;
  box-shadow: 0 1px 2px rgba(29, 28, 26, 0.03);
  font-family: var(--font);
}
.article-topline { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.article-kicker { display: inline-flex; align-items: center; gap: 8px; color: var(--brand-strong); font-size: var(--text-xs); font-weight: 700; letter-spacing: .08em; line-height: 1.4; }
.article-kicker i { width: 18px; height: 3px; border-radius: 999px; background: var(--brand); }
.article-source { border: none; background: transparent; color: var(--text-2); font-size: var(--text-xs); padding: 4px 0; cursor: pointer; }
.article-source:hover { color: var(--brand-strong); }
.article-title {
  margin: 24px 0 20px; color: var(--text); font-size: clamp(28px, 3.5vw, 36px);
  line-height: 1.3; font-weight: 750; letter-spacing: -.025em; overflow-wrap: anywhere;
}
.article-byline { display: flex; align-items: center; flex-wrap: wrap; gap: 7px 9px; color: var(--text-3); font-size: var(--text-xs); line-height: var(--leading-snug); }
.article-byline b { color: var(--text-2); font-weight: 650; }
.article-byline time { margin-left: 2px; font-variant-numeric: tabular-nums; }
.byline-avatar { width: 24px; height: 24px; border-radius: 7px; overflow: hidden; display: inline-flex; align-items: center; justify-content: center; background: var(--surface-2); color: var(--text-3); font-size: var(--text-2xs); font-weight: 700; }
.byline-avatar img { width: 100%; height: 100%; object-fit: cover; }
.byline-dot { color: var(--line); }
.byline-conv { max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.alias-toggle { border: none; border-radius: 999px; padding: 3px 8px; background: var(--brand-weak); color: var(--brand-strong); font-size: var(--text-2xs); line-height: 1.4; cursor: pointer; }
.alias-toggle:hover { background: var(--brand); color: #fff; }
.alias-form { margin-top: 18px; padding: 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface-2); }
.alias-form label { display: block; color: var(--text); font-size: var(--text-sm); font-weight: 650; }
.alias-form p { margin: 5px 0 12px; color: var(--text-3); font-size: var(--text-xs); line-height: 1.6; }
.alias-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.alias-actions input { flex: 1; min-width: 180px; height: 36px; padding: 0 12px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); color: var(--text); font-size: var(--text-sm); }
.alias-actions input:focus { outline: 2px solid var(--brand); outline-offset: 2px; }
.alias-actions button { min-height: 34px; padding: 0 14px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); color: var(--text-2); font-size: var(--text-xs); cursor: pointer; }
.alias-actions button[type="submit"] { border-color: #241f1a; background: #241f1a; color: #fff; }
.alias-actions button:disabled { opacity: .6; cursor: wait; }
.alias-error { display: block; margin-top: 8px; color: var(--warn); font-size: var(--text-xs); }
.article-divider { height: 1px; background: var(--line); margin: 28px 0 32px; }
.article-content { color: var(--text); font-size: 16px; line-height: 1.9; letter-spacing: .005em; }
.article-p { margin: 0 0 20px; white-space: pre-line; overflow-wrap: anywhere; }
.article-p.article-lead { color: var(--text-2); font-size: 17px; line-height: 1.85; }
.article-p:last-child { margin-bottom: 0; }
.article-h2 { margin: 36px 0 14px; font-size: 22px; line-height: 1.45; font-weight: 700; letter-spacing: -.015em; }
.article-h3 { margin: 28px 0 12px; font-size: 18px; line-height: 1.5; font-weight: 700; }
.article-h2:first-child, .article-h3:first-child { margin-top: 0; }
.article-list { margin: 0 0 22px; padding-left: 24px; }
.article-list li { margin: 8px 0; padding-left: 3px; }
.article-list.ordered { padding-left: 22px; }
.article-list.ordered li::marker { color: var(--brand-strong); font-weight: 700; }
.article-list li::marker { color: var(--text-3); }
.article-quote { margin: 24px 0; padding: 14px 18px; border-left: 3px solid var(--brand); background: var(--brand-weak); color: var(--text-2); border-radius: 0 10px 10px 0; }
.article-image-link { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 12px; margin: 24px 0; padding: 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface-2); color: var(--text); text-decoration: none; font-size: var(--text-sm); }
.article-image-link span { padding: 4px 8px; border-radius: 999px; background: var(--brand-weak); color: var(--brand-strong); font-size: var(--text-2xs); font-weight: 700; }
.article-image-link b { font-size: var(--text-sm); font-weight: 650; }
.article-image-link em { color: var(--text-3); font-size: var(--text-xs); font-style: normal; white-space: nowrap; }
.article-figures { display: grid; gap: 24px; margin-top: 36px; }
.article-figure { margin: 0; }
.inline-figure { margin: 28px 0 32px; }
.article-figure img { display: block; width: 100%; max-height: 520px; object-fit: contain; border-radius: 12px; background: var(--surface-2); border: 1px solid var(--line); }
.article-figure figcaption { margin-top: 8px; color: var(--text-3); font-size: var(--text-xs); text-align: center; line-height: var(--leading-snug); }
.image-fallback { display: grid; place-items: center; min-height: 180px; border: 1px dashed var(--line); border-radius: 12px; color: var(--text-3); background: var(--surface-2); font-size: var(--text-sm); }
.article-resources { margin-top: 40px; padding-top: 28px; border-top: 1px solid var(--line); }
.resource-title { margin: 0 0 18px; font-size: 19px; font-weight: 700; }
.resource-block + .resource-block { margin-top: 24px; }
.resource-label { display: block; margin-bottom: 9px; color: var(--text-3); font-size: var(--text-xs); font-weight: 650; }
.resource-link { display: flex; align-items: center; gap: 12px; padding: 11px 13px; border: 1px solid var(--line); border-radius: 10px; color: var(--brand-strong); text-decoration: none; font-size: var(--text-sm); margin-top: 7px; }
.resource-link span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.resource-link em { margin-left: auto; font-style: normal; }
.resource-link:hover, .resource-file:hover { border-color: var(--brand); background: var(--brand-weak); }
.resource-file { display: flex; align-items: center; gap: 12px; padding: 12px 13px; border: 1px solid var(--line); border-radius: 10px; color: var(--text); text-decoration: none; margin-top: 7px; }
.file-icon { width: 32px; height: 32px; flex-shrink: 0; display: grid; place-items: center; border-radius: 9px; background: var(--surface-2); color: var(--brand-strong); }
.file-copy { min-width: 0; display: flex; flex: 1; flex-direction: column; }
.file-copy b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--text-sm); font-weight: 650; }
.file-copy i { color: var(--text-3); font-size: var(--text-xs); font-style: normal; }
.resource-file em { color: var(--brand-strong); font-size: var(--text-xs); font-style: normal; white-space: nowrap; }
.article-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--line); color: var(--text-3); font-size: var(--text-xs); line-height: var(--leading-snug); }
.article-footer div { display: flex; gap: 8px; flex-wrap: wrap; }
.article-footer button { border: 1px solid var(--line); border-radius: 999px; background: var(--surface); color: var(--text-2); padding: 7px 13px; font-size: var(--text-xs); cursor: pointer; }
.article-footer button:hover { border-color: var(--brand); color: var(--brand-strong); }
.article-footer button.collapse { background: var(--surface-2); }

@media (max-width: 640px) {
  .message-article { padding: 22px 18px; border-radius: 12px; }
  .article-content { font-size: 15px; line-height: 1.9; }
  .article-title { font-size: 25px; }
  .article-byline time { width: 100%; margin-left: 33px; }
  .article-footer { align-items: flex-start; flex-direction: column; }
  .article-image-link { grid-template-columns: auto 1fr; }
  .article-image-link em { display: none; }
}
</style>
