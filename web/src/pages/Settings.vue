<script setup>
import { onMounted, ref } from 'vue'
import { get, post } from '../api.js'

const cfg = ref({ llm_base_url: '', llm_model: '', has_key: false })
const apiKey = ref('')
const audit = ref([])
const msg = ref('')

async function load() {
  cfg.value = await get('/settings')
  audit.value = await get('/audit')
}
onMounted(load)

async function save() {
  await post('/settings', {
    llm_base_url: cfg.value.llm_base_url,
    llm_model: cfg.value.llm_model,
    llm_api_key: apiKey.value || undefined
  })
  apiKey.value = ''
  msg.value = '已保存。配置后对话页即走 LLM（多模型 OpenAI 兼容）。'
  await load()
}

async function reseed() {
  await post('/seed')
  msg.value = '演示数据集已重置（8 群 × 200+ 条，含待办/日程/闲聊混合）。'
  await load()
}
</script>

<template>
  <div class="set">
    <section class="card block">
      <header class="blk-hd"><h3>模型接入（OpenAI 兼容）</h3>
        <span class="blk-sub">{{ cfg.has_key ? '已配置 Key ✓' : '未配置 · 规则兜底模式' }}</span>
      </header>
      <label class="row">
        <span>Base URL</span>
        <input v-model="cfg.llm_base_url" placeholder="https://api.deepseek.com/v1" />
      </label>
      <label class="row">
        <span>API Key</span>
        <input v-model="apiKey" type="password" :placeholder="cfg.has_key ? '已设置（输入可更换）' : 'sk-…'" />
      </label>
      <label class="row">
        <span>模型</span>
        <input v-model="cfg.llm_model" placeholder="deepseek-chat / qwen-plus / glm-4 …" />
      </label>
      <p class="note">密钥仅存本地 SQLite，不出本机；摘要/对话/向量化按需调用你自选的服务商。</p>
      <div class="acts">
        <button class="btn btn-brand" @click="save">保存</button>
        <button class="btn" @click="reseed">重置演示数据集</button>
      </div>
      <p v-if="msg" class="ok">{{ msg }}</p>
    </section>

    <section class="card block">
      <header class="blk-hd"><h3>工具调用审计（Sentinel）</h3>
        <span class="blk-sub">每次工具调用：时间 · 工具 · 风险 · 审批</span>
      </header>
      <div v-if="audit.length" class="tb-wrap">
        <table class="tb">
          <thead><tr><th>时间</th><th>工具</th><th>风险</th><th>结果</th></tr></thead>
          <tbody>
            <tr v-for="a in audit" :key="a.id">
              <td>{{ a.ts }}</td><td>{{ a.tool }}</td>
              <td><span :class="'risk r-' + a.risk">{{ a.risk }}</span></td>
              <td class="res">{{ a.result?.slice(0, 46) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="empty">暂无工具调用记录。去对话页让小聚干活，这里会留下全量审计。</p>
    </section>

    <section class="card block about">
      <h3>关于聚光</h3>
      <p>本地优先的消息聚合 + AI 分诊 + Agent 执行平台。聚合消息，聚焦要事——
        不是让你看更多消息，而是让你少看消息。</p>
      <p><b>合规边界</b>：飞书/钉钉/邮箱走官方 API；微信/QQ/抖音为实验性本地只读插件，
        可一键停用，停用后平台以官方渠道完整运行。外发动作永远只起草，发送由你自己完成。</p>
    </section>
  </div>
</template>

<style scoped>
.set { max-width: 760px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--sp-5); }
.block { padding: 20px; }
.blk-hd { display: flex; align-items: baseline; gap: var(--sp-3); margin-bottom: var(--sp-4); flex-wrap: wrap; }
.blk-hd h3 { margin: 0; font-size: var(--text-lg); font-weight: 700; line-height: var(--leading-tight); }
.blk-sub { font-size: var(--text-xs); color: var(--text-3); margin-left: auto; line-height: var(--leading-snug); }

.row { display: grid; grid-template-columns: 88px 1fr; gap: var(--sp-3); align-items: center;
  margin-bottom: var(--sp-3); font-size: var(--text-sm); }
.row input { border: 1px solid var(--line); border-radius: 8px; padding: 9px 11px;
  background: var(--surface); font-size: var(--text-base); line-height: 1.4; outline: none; }
.row input:focus-visible { border-color: var(--brand); outline: 2px solid var(--brand); outline-offset: 1px; }
.note { font-size: var(--text-xs); color: var(--text-3); margin: var(--sp-3) 0 0; line-height: var(--leading-relaxed); }
.acts { display: flex; gap: 10px; flex-wrap: wrap; margin-top: var(--sp-4); }
.ok { font-size: var(--text-xs); color: var(--ok); margin: var(--sp-3) 0 0; line-height: var(--leading-snug); }

.tb-wrap { overflow-x: auto; }
.tb { width: 100%; border-collapse: collapse; font-size: var(--text-sm); min-width: 520px; }
.tb th { text-align: left; font-size: var(--text-2xs); color: var(--text-3); padding: 7px 8px; font-weight: 650; line-height: 1.4; }
.tb td { border-top: 1px solid var(--line); padding: 10px 8px; vertical-align: top; line-height: var(--leading-snug); }
.res { color: var(--text-2); max-width: 300px; overflow-wrap: anywhere; }
.risk { font-size: var(--text-2xs); border-radius: 4px; padding: 1px 5px; white-space: nowrap; }
.r-safe { background: #e3f7f1; color: #0e8a70; }
.r-moderate { background: #fdeed9; color: #b05e00; }
.r-sensitive { background: #ffe7e7; color: #d0342c; }
.r-unknown { background: var(--surface-2); color: var(--text-3); }
.empty { font-size: var(--text-xs); color: var(--text-3); line-height: var(--leading-relaxed); }
.about p { font-size: var(--text-sm); color: var(--text-2); line-height: var(--leading-relaxed); margin: 0 0 12px; }
.about p:last-child { margin-bottom: 0; }

@media (max-width: 640px) {
  .set { gap: 16px; }
  .block { padding: 16px; }
  .blk-hd { align-items: flex-start; flex-direction: column; gap: 6px; }
  .blk-sub { margin-left: 0; }
  .row { grid-template-columns: 1fr; gap: 6px; }
}
</style>
