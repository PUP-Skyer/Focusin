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
  await load()
  msg.value = cfg.value.available
    ? '已保存。当前使用真实 LLM（OpenAI 兼容）。'
    : '已保存。模型配置尚未完整，当前使用本地规则兜底模式。'
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
        <span class="blk-sub">{{ cfg.available ? 'LLM 已就绪 ✓' : '规则兜底模式 · 配置未完整' }}</span>
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
      <table v-if="audit.length" class="tb">
        <thead><tr><th>时间</th><th>工具</th><th>风险</th><th>结果</th></tr></thead>
        <tbody>
          <tr v-for="a in audit" :key="a.id">
            <td>{{ a.ts }}</td><td>{{ a.tool }}</td>
            <td><span :class="'risk r-' + a.risk">{{ a.risk }}</span></td>
            <td class="res">{{ a.result?.slice(0, 46) }}</td>
          </tr>
        </tbody>
      </table>
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
.set { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.block { padding: 18px; }
.blk-hd { display: flex; align-items: baseline; gap: 10px; margin-bottom: 14px; }
.blk-hd h3 { margin: 0; font-size: 15px; }
.blk-sub { font-size: 11px; color: var(--text-3); margin-left: auto; }

.row { display: grid; grid-template-columns: 80px 1fr; gap: 10px; align-items: center;
  margin-bottom: 10px; font-size: 13px; }
.row input { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px;
  background: var(--surface); font-size: 13px; outline: none; }
.row input:focus { border-color: var(--brand); }
.note { font-size: 11px; color: var(--text-3); margin: 0 0 12px; }
.acts { display: flex; gap: 10px; }
.ok { font-size: 12px; color: var(--ok); margin: 12px 0 0; }

.tb { width: 100%; border-collapse: collapse; font-size: 12px; }
.tb th { text-align: left; font-size: 11px; color: var(--text-3); padding: 4px 8px; font-weight: 500; }
.tb td { border-top: 1px solid var(--line); padding: 6px 8px; vertical-align: top; }
.res { color: var(--text-2); max-width: 300px; }
.risk { font-size: 10px; border-radius: 4px; padding: 0 4px; }
.r-safe { background: #e3f7f1; color: #0e8a70; }
.r-moderate { background: #fdeed9; color: #b05e00; }
.r-sensitive { background: #ffe7e7; color: #d0342c; }
.r-unknown { background: var(--surface-2); color: var(--text-3); }
.empty { font-size: 12px; color: var(--text-3); }
.about p { font-size: 12px; color: var(--text-2); line-height: 1.7; }
</style>
