<script setup>
import { onMounted, ref } from 'vue'
import { get, post, notifyConversationsChanged } from '../api.js'

const list = ref([])
const form = ref({})
const selectedAccount = ref({})
const testing = ref({})
const discover = ref({})   // form key -> {conversations, error, loading}
const syncing = ref({})
const syncResult = ref({})
const subs = ref([])
const openKey = ref('')
const keywordOpen = ref('')
const keywordDraft = ref({})
const keywordSaving = ref({})
const keywordFeedback = ref({})
const feishuOauth = ref({ authorized: false, configured: false, user: null })
const oauthStarting = ref(false)
const oauthFeedback = ref('')

const formKey = (c, aid = selectedAccount.value[c.key]) =>
  c.key === 'email' ? `${c.key}:${aid || 'new'}` : c.key
const currentAccount = c => c.accounts?.find(a => a.account_key === selectedAccount.value[c.key])
const maskedFor = c => c.key === 'email' ? currentAccount(c)?.masked || {} : c.masked || {}
const configuredFor = c => c.key === 'email' ? !!currentAccount(c)?.configured : c.configured

function ensureForm(c, aid = selectedAccount.value[c.key]) {
  const key = formKey(c, aid)
  if (form.value[key]) return
  const account = c.accounts?.find(a => a.account_key === aid)
  form.value[key] = account
    ? { host: account.host, port: String(account.port || 993), username: account.username, password: '' }
    : {}
}

function selectAccount(c, aid) {
  selectedAccount.value[c.key] = aid || 'new'
  ensureForm(c)
}

async function load() {
  list.value = await get('/connectors')
  for (const c of list.value) {
    if (c.key === 'email') {
      const selected = selectedAccount.value[c.key]
      if (selected !== 'new' && !c.accounts.some(a => a.account_key === selected)) {
        selectedAccount.value[c.key] = c.accounts[0]?.account_key || 'new'
      }
      for (const a of c.accounts) ensureForm(c, a.account_key)
      ensureForm(c, 'new')
    } else {
      ensureForm(c)
    }
  }
  subs.value = await get('/subscriptions')
  keywordDraft.value = Object.fromEntries(subs.value.map(s => [subIdentity(s), keywordsOf(s).join('\n')]))
}

async function loadFeishuOauth() {
  try { feishuOauth.value = await get('/connectors/feishu/oauth/status') } catch { /* 服务未启动 */ }
}

async function startFeishuOAuth() {
  oauthStarting.value = true
  oauthFeedback.value = ''
  try {
    const result = await post('/connectors/feishu/oauth/start', { web_origin: window.location.origin })
    if (!result.ok) {
      oauthFeedback.value = result.error || '无法发起飞书授权'
      return
    }
    window.location.assign(result.authorize_url)
  } catch (error) {
    oauthFeedback.value = error.message || '无法发起飞书授权'
  } finally {
    oauthStarting.value = false
  }
}

async function logoutFeishuOAuth() {
  await post('/connectors/feishu/oauth/logout')
  await loadFeishuOauth()
  oauthFeedback.value = '已退出飞书账号，后续将使用应用机器人身份同步'
}

onMounted(async () => {
  const params = new URLSearchParams(window.location.search)
  const feishuResult = params.get('feishu')
  if (feishuResult === 'connected') oauthFeedback.value = '飞书账号授权成功'
  if (feishuResult === 'denied') oauthFeedback.value = '你取消了飞书授权'
  if (feishuResult === 'oauth_failed') {
    oauthFeedback.value = `飞书授权失败：${params.get('reason') || '请重试'}`
  }
  await load()
  await loadFeishuOauth()
})

function open(c) {
  openKey.value = openKey.value === c.key ? '' : c.key
}

async function saveCred(c) {
  const aid = selectedAccount.value[c.key]
  const key = formKey(c)
  testing.value[key] = true
  try {
    const payload = { fields: form.value[key] || {} }
    if (c.key === 'email') payload.account_id = aid === 'new' ? '' : aid
    const r = await post(`/connectors/${c.key}/credentials`, payload)
    c.test = r
    if (r.ok && c.key === 'email') selectedAccount.value[c.key] = r.account_id
    if (r.ok) {
      await load()
      await loadFeishuOauth()
      const updated = list.value.find(x => x.key === c.key)
      if (updated) await doDiscover(updated)
    }
  } finally { testing.value[key] = false }
}

async function doDiscover(c) {
  const aid = selectedAccount.value[c.key]
  if (c.key === 'email' && (!aid || aid === 'new')) return
  const key = formKey(c)
  discover.value[key] = { loading: true }
  const payload = c.key === 'email' ? { account_id: aid } : {}
  const r = await post(`/connectors/${c.key}/discover`, payload)
  discover.value[key] = { loading: false, conversations: r.conversations || [], error: r.error }
}

function isSubbed(key, convKey, accountKey = '') {
  return subs.value.some(s => s.channel_key === key && s.conv_key === convKey
    && (s.account_key || '') === accountKey && s.active)
}

async function toggleSub(c, conv) {
  const accountKey = c.key === 'email' ? selectedAccount.value[c.key] : ''
  const on = !isSubbed(c.key, conv.conv_key, accountKey)
  const r = await post(`/connectors/${c.key}/subscribe`, {
    conv_key: conv.conv_key, conv_title: conv.conv_title, account_key: accountKey, on
  })
  subs.value = await get('/subscriptions')
  c.subscriptions = r.subscriptions
}

async function doSync(c) {
  const key = formKey(c)
  syncing.value[key] = true
  syncResult.value[key] = null
  try {
    const payload = c.key === 'email' ? { account_id: selectedAccount.value[c.key] } : {}
    const result = await post(`/connectors/${c.key}/sync`, payload)
    syncResult.value[key] = result
    if (result.ok || result.fetched) notifyConversationsChanged()
  } finally { syncing.value[key] = false }
}

async function unsub(s) {
  const r = await post(`/connectors/${s.channel_key}/subscribe`, {
    conv_key: s.conv_key, conv_title: s.conv_title, account_key: s.account_key || '', on: false
  })
  subs.value = await get('/subscriptions')
  const c = list.value.find(x => x.key === s.channel_key)
  if (c) c.subscriptions = r.subscriptions
}

function subscriptionSource(s) {
  const c = list.value.find(x => x.key === s.channel_key)
  const account = c?.accounts?.find(a => a.account_key === s.account_key)
  return account ? `${c.name} · ${account.short_label}` : c?.name || s.channel_key
}

function subIdentity(s) {
  return `${s.channel_key}:${s.account_key || ''}:${s.conv_key}`
}

function keywordsOf(s) {
  return Array.isArray(s.keywords) ? s.keywords : []
}

function parseKeywordDraft(value) {
  return [...new Set(String(value || '').split(/[,，\n]+/).map(k => k.trim()).filter(Boolean))]
}

function toggleKeywords(s) {
  const key = subIdentity(s)
  if (keywordOpen.value === key) {
    keywordOpen.value = ''
    return
  }
  keywordOpen.value = key
  keywordDraft.value[key] = keywordsOf(s).join('\n')
  keywordFeedback.value[key] = ''
}

async function saveKeywords(s) {
  const key = subIdentity(s)
  const keywords = parseKeywordDraft(keywordDraft.value[key])
  if (keywords.length > 20) {
    keywordFeedback.value[key] = '每个群聊最多设置 20 个关键词'
    return
  }
  if (keywords.some(k => k.length > 50)) {
    keywordFeedback.value[key] = '单个关键词不能超过 50 个字符'
    return
  }
  keywordSaving.value[key] = true
  keywordFeedback.value[key] = ''
  try {
    const result = await post(`/connectors/${s.channel_key}/subscriptions/keywords`, {
      conv_key: s.conv_key, keywords
    })
    if (!result.ok) {
      keywordFeedback.value[key] = result.error || '保存失败'
      return
    }
    subs.value = await get('/subscriptions')
    keywordDraft.value[key] = result.keywords.join('\n')
    keywordFeedback.value[key] = '已保存，点击上方「立即同步」应用规则'
  } finally {
    keywordSaving.value[key] = false
  }
}

const status = c => c.ready
  ? (c.configured ? (c.subscriptions ? '已连接 · 监听中' : '已连接') : '待配置')
  : '实验预留'

const feishuIdentity = () => feishuOauth.value.authorized
  ? `用户身份 · ${feishuOauth.value.user?.name || '已登录'}`
  : '应用机器人身份'
</script>

<template>
  <div class="conn">

    <section class="card privacy">
      <b>隐私红线</b>
      <p>只有你在下面<b>手动勾选</b>的会话会被监听入库；没有勾选的群聊 / 文件夹，
        聚光<b>不请求、不拉取、不存储</b>任何内容。凭据仅保存在本机数据库，接口永不回传原文。</p>
    </section>

    <div class="grid">
      <section v-for="c in list" :key="c.key" class="card cc"
        :class="{ open: openKey === c.key }">
        <header tabindex="0" role="button" :aria-expanded="openKey === c.key"
          @click="open(c)" @keydown.enter.prevent="open(c)" @keydown.space.prevent="open(c)">
          <span :class="['ch-dot', 'ch-' + c.key]" />
          <b>{{ c.name }}</b>
          <span class="grp" :class="c.ready ? (c.configured ? 'grp-notice' : 'grp-chatter') : 'grp-important'">
            {{ status(c) }}
          </span>
          <span class="arrow">{{ openKey === c.key ? '▾' : '▸' }}</span>
        </header>
        <p class="desc">{{ c.desc }}</p>

        <div v-if="openKey === c.key && c.ready" class="body">
          <div v-if="c.key === 'email'" class="account-switcher">
            <button v-for="a in c.accounts" :key="a.account_key"
              :class="{ on: selectedAccount[c.key] === a.account_key }"
              @click="selectAccount(c, a.account_key)">{{ a.short_label }}</button>
            <button :class="{ on: selectedAccount[c.key] === 'new' }"
              @click="selectAccount(c, 'new')">＋ 添加其他邮箱</button>
          </div>

          <div v-if="c.key === 'feishu'" class="safe-note">
            <b>官方 API 接入要求</b>
            <p>创建自建应用并开启机器人能力，申请 im:chat:readonly、im:message:readonly、
              im:message.group_msg 权限，发布后把机器人加入目标群。使用用户账号登录还需开通
              im:message.group_msg:get_as_user；真实姓名和头像需开通 contact:user.base:readonly。
              外部群需额外开启对外共享；仅同步你手动勾选的群。</p>
          </div>

          <div v-if="c.key === 'feishu'" class="oauth-panel">
            <div class="oauth-head">
              <div>
                <b>飞书账号登录</b>
                <p>使用你本人的飞书账号授权，可读取你可见且手动订阅的群聊。</p>
              </div>
              <span class="identity-chip">{{ feishuIdentity() }}</span>
            </div>
            <div v-if="feishuOauth.authorized" class="oauth-user">
              <img v-if="feishuOauth.user?.avatar_url" :src="feishuOauth.user.avatar_url" alt="">
              <span v-else class="avatar-fallback">{{ feishuOauth.user?.name?.slice(0, 1) || '飞' }}</span>
              <div class="oauth-user-copy">
                <b>{{ feishuOauth.user?.name || '飞书用户' }}</b>
                <small>用户身份授权有效</small>
              </div>
              <button class="btn mini-btn" @click="logoutFeishuOAuth">退出登录</button>
            </div>
            <div v-else class="oauth-actions">
              <button class="btn btn-primary" :disabled="oauthStarting || !configuredFor(c)" @click="startFeishuOAuth">
                {{ oauthStarting ? '正在跳转…' : '登录飞书账号' }}
              </button>
              <span v-if="!configuredFor(c)">请先保存并验证应用凭据</span>
            </div>
            <p v-if="oauthFeedback" class="oauth-feedback" :class="{ ok: oauthFeedback.includes('成功') }">
              {{ oauthFeedback }}
            </p>
            <p class="oauth-help">首次使用需在飞书开发者后台「安全设置 → 重定向 URL」添加：
              <code>http://127.0.0.1:8765/api/connectors/feishu/oauth/callback</code>
            </p>
          </div>

          <div v-if="c.key === 'wechat'" class="safe-note">
            <b>本地只读安全边界</b>
            <p>不会读取微信进程、不会自动取钥、不会 Hook 或注入，也不会联网上传数据。
              当前 PoC 仅读取你提供的静态数据库副本中的文本消息，需手动同步；
              真实 Windows 微信版本兼容性需以你的数据库副本实测。</p>
          </div>

          <div v-for="f in c.fields" :key="f.key" class="field" :class="{ 'check-field': f.type === 'checkbox' }">
            <label>{{ f.label }}</label>
            <select v-if="f.presets" v-model="form[formKey(c)][f.key]">
              <option value="" disabled>选择服务器…</option>
              <option v-for="p in f.presets" :key="p[1]" :value="p[1]">{{ p[0] }}（{{ p[1] }}）</option>
              <option value="__custom">手动输入…</option>
            </select>
            <input v-else-if="f.type === 'checkbox'" type="checkbox" v-model="form[formKey(c)][f.key]">
            <input v-else-if="!f.presets || form[formKey(c)][f.key] === '__custom'"
              :type="f.type || 'text'" v-model="form[formKey(c)][f.key]"
              :placeholder="f.placeholder || ''" autocomplete="off">
            <em v-if="f.hint" class="hint">{{ f.hint }}</em>
          </div>

          <p v-if="configuredFor(c)" class="masked">
            已保存：{{ Object.values(maskedFor(c)).filter(Boolean).join(' · ') }}
          </p>
          <p v-if="c.test && !c.test.ok" class="err">✗ {{ c.test.error }}</p>

          <div class="acts">
            <button class="btn btn-primary"
              :disabled="testing[formKey(c)] || (c.key === 'wechat' && !form[formKey(c)]?.authorized)"
              @click="saveCred(c)">{{ testing[formKey(c)] ? '验证中…' : configuredFor(c) ? '保存并重新验证' : '保存并验证' }}</button>
          </div>

          <template v-if="configuredFor(c)">
            <div class="sec-hd">
              <b>选择要监听的会话</b>
              <button class="btn mini-btn" @click="doDiscover(c)">刷新列表</button>
            </div>
            <p v-if="discover[formKey(c)]?.loading">加载中…</p>
            <p v-else-if="discover[formKey(c)]?.error" class="err">{{ discover[formKey(c)].error }}</p>
            <ul v-else-if="discover[formKey(c)]?.conversations" class="conv-list">
              <li v-for="conv in discover[formKey(c)].conversations" :key="conv.conv_key"
                :class="{ on: isSubbed(c.key, conv.conv_key, c.key === 'email' ? selectedAccount[c.key] : '') }"
                @click="toggleSub(c, conv)">
                <span class="tick">{{ isSubbed(c.key, conv.conv_key, c.key === 'email' ? selectedAccount[c.key] : '') ? '☑' : '☐' }}</span>
                <span class="t">{{ conv.conv_title }}</span>
                <em v-if="isSubbed(c.key, conv.conv_key, c.key === 'email' ? selectedAccount[c.key] : '')">监听中</em>
              </li>
              <li v-if="!discover[formKey(c)].conversations.length" class="empty">
                {{ c.key === 'wechat' ? '没有发现会话，请检查数据库副本与密钥文件' : '没有发现会话（飞书需先把机器人拉进群）' }}
              </li>
            </ul>

            <div class="acts">
              <button class="btn" :disabled="syncing[formKey(c)]" @click="doSync(c)">
                {{ syncing[formKey(c)] ? '同步中…' : '立即同步' }}
              </button>
              <div v-if="syncResult[formKey(c)]" class="sync-feedback">
                <span class="sync-r" :class="{ err: syncResult[formKey(c)].ok === false }">
                  {{ syncResult[formKey(c)].ok === false
                    ? '✗ ' + (syncResult[formKey(c)].error || syncResult[formKey(c)].errors?.join('；') || '同步失败')
                    : `✓ 拉取 ${syncResult[formKey(c)].fetched} 条 · 新入库 ${syncResult[formKey(c)].new} 条` }}
                </span>
                <span v-if="c.key === 'feishu' && syncResult[formKey(c)].identity" class="sync-identity">
                  {{ syncResult[formKey(c)].identity === 'user' ? '本次使用你的飞书账号' : '本次使用应用机器人' }}
                </span>
                <p v-if="syncResult[formKey(c)].warnings?.length" class="sync-warning">
                  {{ syncResult[formKey(c)].warnings.join('；') }}
                </p>
                <p v-if="syncResult[formKey(c)].unresolved_senders" class="sync-warning">
                  仍有 {{ syncResult[formKey(c)].unresolved_senders }} 个发送人未获得昵称。
                  可点击消息旁的“补昵称”手动修正；外部群成员名单不完整时，飞书不会返回其余外部用户昵称。
                </p>
              </div>
            </div>
          </template>
        </div>
      </section>
    </div>

    <section class="card block" v-if="subs.filter(s => s.active).length">
      <header class="blk-hd"><h3>监听清单（{{ subs.filter(s => s.active).length }} 个会话）</h3>
        <span class="blk-sub">未在清单中的会话一律不监听</span></header>
      <ul class="subs">
        <li v-for="s in subs.filter(s => s.active)" :key="subIdentity(s)"
          :class="{ editing: keywordOpen === subIdentity(s) }">
          <div class="sub-row">
            <span :class="['ch-dot', 'ch-' + s.channel_key]" />
            <b>{{ s.conv_title || s.conv_key }}</b>
            <span class="ch-name">{{ subscriptionSource(s) }}</span>
            <span v-if="s.channel_key === 'feishu'" class="kw-summary" :class="{ on: keywordsOf(s).length }">
              {{ keywordsOf(s).length ? `${keywordsOf(s).length} 个关键词` : '默认规则' }}
            </span>
            <div class="sub-actions">
              <button v-if="s.channel_key === 'feishu'" class="btn mini-btn kw-toggle"
                :aria-expanded="keywordOpen === subIdentity(s)" @click="toggleKeywords(s)">
                {{ keywordOpen === subIdentity(s) ? '收起关键词' : '关键词' }}
              </button>
              <button class="btn mini-btn" @click="unsub(s)">停止监听</button>
            </div>
          </div>
          <div v-if="s.channel_key === 'feishu' && keywordOpen === subIdentity(s)" class="kw-editor">
            <div class="kw-heading">
              <label :for="`kw-${subIdentity(s)}`">自定义重要关键词</label>
              <span>命中后标记为「重要」并保留</span>
            </div>
            <textarea :id="`kw-${subIdentity(s)}`" v-model="keywordDraft[subIdentity(s)]" rows="3"
              maxlength="1200" placeholder="例如：截止、评审、紧急&#10;多个关键词用逗号或换行分隔"></textarea>
            <div v-if="parseKeywordDraft(keywordDraft[subIdentity(s)]).length" class="kw-preview">
              <span v-for="keyword in parseKeywordDraft(keywordDraft[subIdentity(s)])" :key="keyword"># {{ keyword }}</span>
            </div>
            <p class="kw-help">仅作用于这个群聊，最多 20 个；保存后点击上方飞书的「立即同步」。</p>
            <div class="kw-actions">
              <button class="btn btn-primary mini-btn" :disabled="keywordSaving[subIdentity(s)]"
                @click="saveKeywords(s)">{{ keywordSaving[subIdentity(s)] ? '保存中…' : '保存关键词' }}</button>
              <button class="btn mini-btn" @click="keywordOpen = ''">取消</button>
              <span v-if="keywordFeedback[subIdentity(s)]" class="kw-feedback"
                :class="{ ok: keywordFeedback[subIdentity(s)].startsWith('已保存') }">
                {{ keywordFeedback[subIdentity(s)] }}
              </span>
            </div>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.conn { display: flex; flex-direction: column; gap: var(--sp-5); }
.privacy { padding: var(--sp-4) var(--sp-5); border-left: 3px solid var(--brand); }
.privacy b { font-family: var(--font-display); font-size: var(--text-md); line-height: 1.35; }
.privacy p { margin: 7px 0 0; font-size: var(--text-sm); color: var(--text-2); line-height: var(--leading-relaxed); }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: var(--sp-4); }
.cc { padding: var(--sp-5); }
.cc header { display: flex; align-items: center; gap: var(--sp-2); cursor: pointer; border-radius: 8px; }
.cc header:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.cc header b { font-family: var(--font-display); font-size: var(--text-md); line-height: 1.35; font-weight: 700; }
.arrow { margin-left: auto; color: var(--text-3); }
.desc { font-size: var(--text-xs); color: var(--text-3); line-height: var(--leading-normal); margin: 9px 0 0; }
.body { margin-top: var(--sp-4); display: flex; flex-direction: column; gap: var(--sp-3); }
.safe-note { padding: 12px 14px; border: 1px solid var(--line); border-left: 3px solid var(--ok); border-radius: 8px; background: var(--surface-2); }
.safe-note b { font-size: var(--text-sm); line-height: 1.4; }
.safe-note p { margin: 5px 0 0; color: var(--text-2); font-size: var(--text-xs); line-height: var(--leading-relaxed); }
.oauth-panel {
  padding: 14px; border: 1px solid var(--line); border-left: 3px solid var(--brand);
  border-radius: 10px; background: var(--surface-2);
}
.oauth-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.oauth-head b { font-size: var(--text-sm); line-height: 1.4; }
.oauth-head p { margin: 4px 0 0; color: var(--text-2); font-size: var(--text-xs); line-height: var(--leading-relaxed); }
.identity-chip {
  flex-shrink: 0; padding: 3px 8px; border-radius: 999px; background: var(--brand-weak);
  color: var(--brand-strong); font-size: var(--text-2xs); line-height: 1.5;
}
.oauth-user { display: flex; align-items: center; gap: 10px; margin-top: 12px; }
.oauth-user img, .avatar-fallback {
  width: 36px; height: 36px; border-radius: 50%; object-fit: cover; flex-shrink: 0;
  background: var(--brand-weak); color: var(--brand-strong);
}
.avatar-fallback { display: grid; place-items: center; font-size: var(--text-sm); font-weight: 700; }
.oauth-user-copy { display: flex; flex-direction: column; min-width: 0; }
.oauth-user-copy b { font-size: var(--text-sm); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.oauth-user-copy small { color: var(--text-3); font-size: var(--text-2xs); }
.oauth-user .btn { margin-left: auto; }
.oauth-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 12px; }
.oauth-actions span { color: var(--text-3); font-size: var(--text-2xs); }
.oauth-feedback { margin: 10px 0 0; color: var(--warn); font-size: var(--text-xs); line-height: var(--leading-snug); }
.oauth-feedback.ok { color: var(--ok); }
.oauth-help { margin: 10px 0 0; color: var(--text-3); font-size: var(--text-2xs); line-height: 1.6; overflow-wrap: anywhere; }
.oauth-help code { color: var(--text-2); font-size: 11px; }
.sync-identity { color: var(--text-3); font-size: var(--text-2xs); white-space: nowrap; }
.account-switcher { display: flex; flex-wrap: wrap; gap: 6px; padding-bottom: 2px; }
.account-switcher button {
  border: 1px solid var(--line); background: var(--surface-2); color: var(--text-2);
  border-radius: 999px; padding: 6px 10px; font-size: var(--text-xs); line-height: 1.3; max-width: 100%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.account-switcher button.on { border-color: var(--brand); background: var(--brand-weak); color: var(--brand-strong); }

.field { display: flex; flex-direction: column; gap: 7px; }
.field label { font-size: var(--text-xs); line-height: 1.4; color: var(--text-2); font-weight: 600; }
.field input, .field select {
  height: 40px; border: 1px solid var(--line); border-radius: 8px;
  padding: 0 12px; background: var(--surface-2); font-size: var(--text-base); line-height: 1.3;
}
.field input:focus-visible { outline: 2px solid var(--brand); outline-offset: 1px; }
.check-field { display: grid; grid-template-columns: 18px minmax(0, 1fr); align-items: start; column-gap: 8px; }
.check-field label { grid-column: 2; grid-row: 1; line-height: 1.5; cursor: pointer; }
.check-field input { grid-column: 1; grid-row: 1; width: 16px; height: 16px; margin: 1px 0 0; accent-color: var(--brand); }
.check-field .hint { grid-column: 2; }
.hint { font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--text-3); font-style: normal; }
.masked { font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--text-3); }
.err { font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--warn); }

.acts { display: flex; align-items: center; gap: var(--sp-3); margin-top: var(--sp-1); }
.sec-hd { display: flex; align-items: center; justify-content: space-between; margin-top: var(--sp-3); }
.sec-hd b { font-size: var(--text-sm); font-weight: 650; }

.conv-list { list-style: none; margin: 0; padding: 0; max-height: 260px; overflow: auto; }
.conv-list li {
  display: flex; align-items: center; gap: var(--sp-2); padding: 7px var(--sp-2);
  border-radius: 8px; cursor: pointer; font-size: var(--text-sm);
}
.conv-list li:hover { background: var(--surface-2); }
.conv-list li.on { background: var(--brand-weak); }
.conv-list .tick { color: var(--brand-strong); }
.conv-list .t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conv-list em {
  font-style: normal; margin-left: auto; font-size: var(--text-2xs); color: var(--brand-strong);
}
.empty { font-size: var(--text-xs); color: var(--text-3); }
.sync-r { font-size: var(--text-xs); color: var(--text-2); }
.sync-feedback { min-width: 0; }
.sync-warning { margin: 6px 0 0; color: var(--warn); font-size: var(--text-xs); line-height: var(--leading-snug); }

.block { padding: var(--sp-5); }
.blk-hd { display: flex; align-items: baseline; gap: var(--sp-3); margin-bottom: var(--sp-3); }
.blk-hd h3 { margin: 0; font-size: var(--text-lg); font-weight: 700; }
.blk-sub { font-size: var(--text-xs); color: var(--text-3); margin-left: auto; }
.subs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.subs li { padding: 8px 4px; border-radius: 10px; }
.subs li:hover { background: var(--surface-2); }
.subs li.editing { background: var(--surface-2); }
.sub-row { display: flex; align-items: center; gap: var(--sp-3); min-width: 0; }
.sub-row b { font-size: var(--text-sm); font-weight: 650; }
.ch-name { font-size: var(--text-xs); color: var(--text-3); }
.kw-summary {
  flex-shrink: 0; padding: 2px 8px; border: 1px solid var(--line); border-radius: 999px;
  font-size: var(--text-2xs); line-height: 1.5; color: var(--text-3); font-variant-numeric: tabular-nums;
}
.kw-summary.on { border-color: transparent; background: var(--brand-weak); color: var(--brand-strong); }
.sub-actions { display: flex; align-items: center; gap: 6px; margin-left: auto; flex-shrink: 0; }
.kw-toggle { color: var(--brand-strong); }
.kw-editor {
  margin: 10px 0 4px 26px; padding: 14px 16px; border: 1px solid var(--line);
  border-left: 3px solid var(--brand); border-radius: 8px; background: var(--surface);
}
.kw-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.kw-heading label { font-size: var(--text-sm); font-weight: 650; color: var(--text); }
.kw-heading span { font-size: var(--text-2xs); color: var(--text-3); }
.kw-editor textarea {
  width: 100%; min-height: 76px; margin-top: 10px; padding: 10px 12px; resize: vertical;
  border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2);
  color: var(--text); font: inherit; font-size: var(--text-sm); line-height: 1.6;
}
.kw-editor textarea:focus-visible { outline: 2px solid var(--brand); outline-offset: 1px; }
.kw-preview { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.kw-preview span {
  max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  padding: 3px 9px; border-radius: 999px; background: var(--brand-weak);
  color: var(--brand-strong); font-size: var(--text-2xs); line-height: 1.5;
}
.kw-help { margin: 9px 0 0; color: var(--text-3); font-size: var(--text-2xs); line-height: 1.6; }
.kw-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.kw-feedback { color: var(--warn); font-size: var(--text-2xs); line-height: 1.5; }
.kw-feedback.ok { color: var(--ok); }

@media (max-width: 768px) {
  .grid { grid-template-columns: 1fr; }
  .blk-hd, .sec-hd { align-items: flex-start; flex-direction: column; gap: 4px; }
  .oauth-head { flex-direction: column; gap: 7px; }
  .blk-sub { margin-left: 0; }
  .sub-row { flex-wrap: wrap; gap: 6px 12px; }
  .sub-actions { margin-left: auto; }
  .kw-editor { margin-left: 0; }
  .kw-heading { align-items: flex-start; flex-direction: column; gap: 3px; }
}
</style>
