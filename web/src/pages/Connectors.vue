<script setup>
import { onMounted, ref } from 'vue'
import { get, post } from '../api.js'

const list = ref([])
const form = ref({})
const testing = ref({})
const discover = ref({})   // key -> {conversations, error, loading}
const syncing = ref({})
const syncResult = ref({})
const subs = ref([])
const openKey = ref('')

async function load() {
  list.value = await get('/connectors')
  for (const c of list.value) {
    if (!form.value[c.key]) form.value[c.key] = {}
  }
  subs.value = await get('/subscriptions')
}

onMounted(load)

function open(c) {
  openKey.value = openKey.value === c.key ? '' : c.key
}

async function saveCred(c) {
  testing.value[c.key] = true
  try {
    const r = await post(`/connectors/${c.key}/credentials`, { fields: form.value[c.key] })
    c.configured = r.ok
    if (r.masked) c.masked = r.masked
    c.test = r
    if (r.ok) await doDiscover(c)
  } finally { testing.value[c.key] = false }
}

async function doDiscover(c) {
  discover.value[c.key] = { loading: true }
  const r = await post(`/connectors/${c.key}/discover`)
  discover.value[c.key] = { loading: false, conversations: r.conversations || [], error: r.error }
}

function isSubbed(key, convKey) {
  return subs.value.some(s => s.channel_key === key && s.conv_key === convKey && s.active)
}

async function toggleSub(c, conv) {
  const on = !isSubbed(c.key, conv.conv_key)
  const r = await post(`/connectors/${c.key}/subscribe`, {
    conv_key: conv.conv_key, conv_title: conv.conv_title, on
  })
  subs.value = await get('/subscriptions')
  c.subscriptions = r.subscriptions
}

async function doSync(c) {
  syncing.value[c.key] = true
  syncResult.value[c.key] = null
  try {
    syncResult.value[c.key] = await post(`/connectors/${c.key}/sync`)
  } finally { syncing.value[c.key] = false }
}

async function unsub(s) {
  const r = await post(`/connectors/${s.channel_key}/subscribe`, {
    conv_key: s.conv_key, conv_title: s.conv_title, on: false
  })
  subs.value = await get('/subscriptions')
  const c = list.value.find(x => x.key === s.channel_key)
  if (c) c.subscriptions = r.subscriptions
}

const status = c => c.ready
  ? (c.configured ? (c.subscriptions ? '已连接 · 监听中' : '已连接') : '待配置')
  : '实验预留'
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
        <header @click="open(c)">
          <span :class="['ch-dot', 'ch-' + c.key]" />
          <b>{{ c.name }}</b>
          <span class="grp" :class="c.ready ? (c.configured ? 'grp-notice' : 'grp-chatter') : 'grp-important'">
            {{ status(c) }}
          </span>
          <span class="arrow">{{ openKey === c.key ? '▾' : '▸' }}</span>
        </header>
        <p class="desc">{{ c.desc }}</p>

        <div v-if="openKey === c.key && c.ready" class="body">
          <div v-for="f in c.fields" :key="f.key" class="field">
            <label>{{ f.label }}</label>
            <select v-if="f.presets" v-model="form[c.key][f.key]">
              <option value="" disabled>选择服务器…</option>
              <option v-for="p in f.presets" :key="p[1]" :value="p[1]">{{ p[0] }}（{{ p[1] }}）</option>
              <option value="__custom">手动输入…</option>
            </select>
            <input v-if="!f.presets || form[c.key][f.key] === '__custom'"
              :type="f.type || 'text'" v-model="form[c.key][f.key]"
              :placeholder="f.placeholder || ''">
            <em v-if="f.hint" class="hint">{{ f.hint }}</em>
          </div>

          <p v-if="c.configured" class="masked">
            已保存：{{ Object.values(c.masked || {}).filter(Boolean).join(' · ') }}
          </p>
          <p v-if="c.test && !c.test.ok" class="err">✗ {{ c.test.error }}</p>

          <div class="acts">
            <button class="btn btn-primary" :disabled="testing[c.key]"
              @click="saveCred(c)">{{ testing[c.key] ? '验证中…' : c.configured ? '保存并重新验证' : '保存并验证' }}</button>
          </div>

          <template v-if="c.configured">
            <div class="sec-hd">
              <b>选择要监听的会话</b>
              <button class="btn mini-btn" @click="doDiscover(c)">刷新列表</button>
            </div>
            <p v-if="discover[c.key]?.loading">加载中…</p>
            <p v-else-if="discover[c.key]?.error" class="err">{{ discover[c.key].error }}</p>
            <ul v-else-if="discover[c.key]?.conversations" class="conv-list">
              <li v-for="conv in discover[c.key].conversations" :key="conv.conv_key"
                :class="{ on: isSubbed(c.key, conv.conv_key) }"
                @click="toggleSub(c, conv)">
                <span class="tick">{{ isSubbed(c.key, conv.conv_key) ? '☑' : '☐' }}</span>
                <span class="t">{{ conv.conv_title }}</span>
                <em v-if="isSubbed(c.key, conv.conv_key)">监听中</em>
              </li>
              <li v-if="!discover[c.key].conversations.length" class="empty">没有发现会话（飞书需先把机器人拉进群）</li>
            </ul>

            <div class="acts">
              <button class="btn" :disabled="syncing[c.key]" @click="doSync(c)">
                {{ syncing[c.key] ? '同步中…' : '立即同步' }}
              </button>
              <span v-if="syncResult[c.key]" class="sync-r">
                {{ syncResult[c.key].ok === false ? '✗ ' + syncResult[c.key].error
                  : `✓ 拉取 ${syncResult[c.key].fetched} 条 · 新入库 ${syncResult[c.key].new} 条` }}
              </span>
            </div>
          </template>
        </div>
      </section>
    </div>

    <section class="card block" v-if="subs.filter(s => s.active).length">
      <header class="blk-hd"><h3>监听清单（{{ subs.filter(s => s.active).length }} 个会话）</h3>
        <span class="blk-sub">未在清单中的会话一律不监听</span></header>
      <ul class="subs">
        <li v-for="s in subs.filter(s => s.active)" :key="s.channel_key + s.conv_key">
          <span :class="['ch-dot', 'ch-' + s.channel_key]" />
          <b>{{ s.conv_title || s.conv_key }}</b>
          <span class="ch-name">{{ list.find(x => x.key === s.channel_key)?.name }}</span>
          <button class="btn mini-btn" @click="unsub(s)">停止监听</button>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.conn { display: flex; flex-direction: column; gap: var(--sp-4); }
.privacy { padding: var(--sp-4) var(--sp-5); border-left: 3px solid var(--brand); }
.privacy b { font-size: 14px; }
.privacy p { margin: 6px 0 0; font-size: 12px; color: var(--text-2); line-height: 1.7; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: var(--sp-3); }
.cc { padding: var(--sp-4); }
.cc header { display: flex; align-items: center; gap: var(--sp-2); cursor: pointer; }
.cc header b { font-size: 14px; }
.arrow { margin-left: auto; color: var(--text-3); }
.desc { font-size: 11.5px; color: var(--text-3); line-height: 1.65; margin: 8px 0 0; }
.body { margin-top: var(--sp-3); display: flex; flex-direction: column; gap: var(--sp-2); }

.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 11px; color: var(--text-2); font-weight: 600; }
.field input, .field select {
  height: 36px; border: 1px solid var(--line); border-radius: 8px;
  padding: 0 12px; background: var(--surface-2); font-size: 13px;
}
.field input:focus-visible { outline: 2px solid var(--brand); outline-offset: 1px; }
.hint { font-size: 10.5px; color: var(--text-3); font-style: normal; }
.masked { font-size: 11px; color: var(--text-3); }
.err { font-size: 12px; color: var(--warn); }

.acts { display: flex; align-items: center; gap: var(--sp-3); margin-top: var(--sp-1); }
.sec-hd { display: flex; align-items: center; justify-content: space-between; margin-top: var(--sp-3); }
.sec-hd b { font-size: 13px; }

.conv-list { list-style: none; margin: 0; padding: 0; max-height: 260px; overflow: auto; }
.conv-list li {
  display: flex; align-items: center; gap: var(--sp-2); padding: 7px var(--sp-2);
  border-radius: 8px; cursor: pointer; font-size: 12.5px;
}
.conv-list li:hover { background: var(--surface-2); }
.conv-list li.on { background: var(--brand-weak); }
.conv-list .tick { color: var(--brand-strong); }
.conv-list .t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conv-list em {
  font-style: normal; margin-left: auto; font-size: 10px; color: var(--brand-strong);
}
.empty { font-size: 12px; color: var(--text-3); }
.sync-r { font-size: 12px; color: var(--text-2); }

.block { padding: var(--sp-5); }
.blk-hd { display: flex; align-items: baseline; gap: var(--sp-3); margin-bottom: var(--sp-3); }
.blk-hd h3 { margin: 0; font-size: 16px; font-weight: 700; }
.blk-sub { font-size: 11px; color: var(--text-3); margin-left: auto; }
.subs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.subs li { display: flex; align-items: center; gap: var(--sp-3); padding: 8px 4px; border-radius: 8px; }
.subs li:hover { background: var(--surface-2); }
.subs b { font-size: 13px; }
.ch-name { font-size: 11px; color: var(--text-3); }
.subs .btn { margin-left: auto; }
</style>
