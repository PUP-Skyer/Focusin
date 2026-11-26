<script setup>
import { nextTick, onMounted, inject, ref } from 'vue'
import Mascot from '../components/Mascot.vue'
import { get, post, chatStream } from '../api.js'

const setMood = inject('setMood')
const items = ref([]) // {kind: user|assistant|thinking|tool, ...}
const input = ref('')
const busy = ref(false)
const approval = ref(null) // 待审批卡
const listEl = ref(null)

const QUICK = [
  '帮我看看接下来的日程',
  '领导上周关于报销说了什么',
  '帮我起草一条回复',
  '提醒我周五下午 3 点开会'
]

onMounted(async () => {
  const h = await get('/chat/history')
  items.value = h.reverse().map(m => ({ kind: m.role, text: m.content }))
})

function scrollBottom() {
  nextTick(() => { if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight })
}

async function send(text) {
  const msg = (text ?? input.value).trim()
  if (!msg || busy.value) return
  input.value = ''
  busy.value = true
  setMood('working')
  items.value.push({ kind: 'user', text: msg })

  let assistant = { kind: 'assistant', text: '', thinking: [], tools: [] }
  items.value.push(assistant)
  let sawApproval = false

  try {
    for await (const ev of chatStream(msg)) {
      if (ev.type === 'delta') { assistant.text += ev.text; scrollBottom() }
      else if (ev.type === 'thinking') { assistant.thinking.push(ev.text) }
      else if (ev.type === 'tool_start') {
        assistant.tools.push({ name: ev.name, args: ev.args, risk: ev.risk, ok: null, result: '' })
        scrollBottom()
      } else if (ev.type === 'tool_end') {
        const t = assistant.tools.find(x => x.name === ev.name && x.ok === null)
        if (t) { t.ok = ev.ok; t.result = ev.result }
        scrollBottom()
      } else if (ev.type === 'approval') {
        sawApproval = true
        approval.value = ev
        setMood('waiting')
        scrollBottom()
      } else if (ev.type === 'approval_resolved') {
        if (approval.value && approval.value.id === ev.id) { approval.value = null }
        setMood(ev.decision === 'approve' ? 'working' : 'error')
      } else if (ev.type === 'error') {
        assistant.text += `\n⚠️ ${ev.message}`
      } else if (ev.type === 'done') {
        if (!assistant.text && ev.content) assistant.text = ev.content
      }
    }
    assistant.text = assistant.text || '（处理完成）'
  } catch (e) {
    assistant.text = `⚠️ 连接本地服务失败：${e.message}`
  }

  busy.value = false
  setMood(sawApproval ? 'idle' : 'happy')
  setTimeout(() => setMood('idle'), 2500)
  scrollBottom()
}

async function decide(d) {
  if (!approval.value) return
  await post(`/approvals/${approval.value.id}/decision`, { decision: d })
}

/* 语音输入：浏览器原生 Web Speech API，不支持则隐藏 */
const sr = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window
const rec = ref(null)
function speak() {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!R) return
  if (!rec.value) {
    rec.value = new R()
    rec.value.lang = 'zh-CN'
    rec.value.onresult = (e) => { input.value = e.results[0][0].transcript }
    rec.value.onend = () => { if (input.value) send() }
  }
  rec.value.start()
}
</script>

<template>
  <div class="chat">
    <div class="msgs" ref="listEl">
      <div v-if="!items.length" class="hello card">
        <Mascot mood="idle" :size="52" />
        <h3>你好，我是小聚 🕊️</h3>
        <p>我以你聚合的消息为工作上下文。试试：</p>
        <div class="quick">
          <button v-for="q in QUICK" :key="q" class="btn" @click="send(q)">{{ q }}</button>
        </div>
      </div>

      <template v-for="(m, i) in items" :key="i">
        <div v-if="m.kind === 'user'" class="bub user-bub">{{ m.text }}</div>

        <div v-else class="bub bot">
          <Mascot mood="idle" :size="26" />

          <!-- 思考过程（可折叠） -->
          <details v-if="m.thinking?.length" class="think">
            <summary>正在思考…（{{ m.thinking.length }} 步）</summary>
            <p v-for="(t, j) in m.thinking" :key="j">· {{ t }}</p>
          </details>

          <!-- 工具调用段 -->
          <details v-for="(t, j) in m.tools" :key="'t' + j" class="tool"
            :class="{ bad: t.ok === false }">
            <summary>
              <span class="dot" :class="{ run: t.ok === null, okk: t.ok === true, bad: t.ok === false }" />
              🔧 {{ t.name }}
              <span class="risk" :class="'r-' + t.risk">{{ t.risk }}</span>
            </summary>
            <pre class="t-args">{{ JSON.stringify(t.args, null, 2) }}</pre>
            <pre class="t-res">{{ t.result }}</pre>
          </details>

          <!-- 审批等待提示 -->
          <div v-if="m.tools?.some(t => t.ok === null && t.risk !== 'safe')"
            class="wait-approval">
            ⏸ 有操作在等你审批（右上弹窗 / 下方审批卡）
          </div>

          <p v-if="m.text" class="bot-txt" v-text="m.text" />
        </div>
      </template>
    </div>

    <footer class="composer card">
      <textarea v-model="input" rows="1" placeholder="问消息、查日程、起草回复……全程平台内完成"
        @keydown.enter.exact.prevent="send()" />
      <button v-if="sr" class="icon-btn" title="语音输入" @click="speak">🎙</button>
      <button class="btn btn-brand" :disabled="busy" @click="send()">发送</button>
    </footer>

    <!-- HITL 审批弹窗 -->
    <div v-if="approval" class="mask" @click.self="decide('deny')">
      <div class="approve card">
        <div class="warn-bar">敏感操作审批 · 点击遮罩默认拒绝（宁拦勿纵）</div>
        <h4>🔧 {{ approval.tool }} <span :class="'risk r-' + approval.risk">{{ approval.risk }}</span></h4>
        <pre class="ap-args">{{ JSON.stringify(approval.args, null, 2) }}</pre>
        <div class="scope">
          作用域：
          <select>
            <option>仅本次</option><option>本会话</option>
            <option>24 小时内</option><option>始终允许</option>
          </select>
        </div>
        <div class="ap-acts">
          <button class="btn btn-brand" @click="decide('approve')">批准</button>
          <button class="btn" @click="decide('deny')">拒绝</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat { display: flex; flex-direction: column; height: 100%; max-width: 860px; margin: 0 auto; }
.msgs { flex: 1; overflow: auto; padding: 6px 2px 16px; display: flex;
  flex-direction: column; gap: 12px; }

.hello { padding: 24px; text-align: center; display: flex; flex-direction: column;
  align-items: center; gap: 10px; }
.hello p { color: var(--text-2); margin: 0; }
.quick { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }

.bub { max-width: 82%; font-size: 13px; line-height: 1.6; }
.user-bub { align-self: flex-end; background: var(--brand); color: #fff;
  padding: 9px 14px; border-radius: 14px 14px 4px 14px; white-space: pre-wrap; }
.bot { align-self: flex-start; display: flex; gap: 8px; }
.bot-txt { margin: 4px 0 0; white-space: pre-wrap; background: var(--surface);
  border: 1px solid var(--line); padding: 9px 14px; border-radius: 4px 14px 14px 14px; }

.think, .tool { font-size: 11px; color: var(--text-2); background: var(--surface-2);
  border-radius: 8px; padding: 4px 10px; margin: 4px 0; }
.think summary, .tool summary { cursor: pointer; list-style: none; display: flex;
  align-items: center; gap: 6px; }
.tool .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-3); }
.tool .dot.run { background: var(--brand); animation: breathe 1s infinite; }
.tool .dot.okk { background: var(--ok); }
.tool .dot.bad { background: var(--warn); }
.risk { font-size: 10px; border-radius: 4px; padding: 0 4px; margin-left: auto; }
.r-safe { background: #e3f7f1; color: #0e8a70; }
.r-moderate { background: #fdeed9; color: #b05e00; }
.r-sensitive { background: #ffe7e7; color: #d0342c; }
.t-args, .t-res { font-size: 10px; white-space: pre-wrap; word-break: break-all;
  margin: 4px 0; color: var(--text-3); max-height: 160px; overflow: auto; }
.wait-approval { font-size: 11px; color: var(--brand-strong); padding: 4px 8px; }

.composer { display: flex; gap: 8px; padding: 10px 12px; align-items: flex-end; margin-top: 12px; }
.composer textarea { flex: 1; border: none; outline: none; resize: none; font-size: 13px;
  background: transparent; max-height: 100px; }
.icon-btn { border: none; background: none; font-size: 16px; }

.mask { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); display: flex;
  align-items: center; justify-content: center; z-index: 50; }
.approve { width: 420px; padding: 0 0 16px; overflow: hidden; }
.warn-bar { background: var(--warn); color: #fff; font-size: 12px; padding: 8px 14px; }
.approve h4 { margin: 14px 14px 8px; display: flex; align-items: center; gap: 8px; }
.ap-args { margin: 0 14px; background: var(--surface-2); border-radius: 8px;
  padding: 10px; font-size: 11px; max-height: 180px; overflow: auto; white-space: pre-wrap; }
.scope { margin: 12px 14px 0; font-size: 12px; color: var(--text-2); }
.scope select { margin-left: 6px; }
.ap-acts { display: flex; gap: 10px; margin: 14px 14px 0; justify-content: flex-end; }
</style>
