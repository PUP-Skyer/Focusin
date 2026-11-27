<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { get, post, GROUP_LABEL, GROUP_CLASS, CH_CLASS, messageSource, openMessageSource, senderDisplayName } from '../api.js'
import ChannelIcon from '../components/ChannelIcon.vue'

const gotoMessages = inject('gotoMessages')
const goChat = inject('goChat')
const data = ref(null)
const sourceNotice = ref('')
let sourceNoticeTimer

const WDAY = ['日', '一', '二', '三', '四', '五', '六']
const today = new Date()
const hello = computed(() => data.value?.greeting || '')

async function load() {
  data.value = await get('/overview')
}
onMounted(() => { load(); setInterval(load, 8000) })

function star(m) {
  post(`/messages/${m.id}/star`).then(() => load())
}

const doneRate = computed(() => {
  const s = data.value?.stats
  if (!s || !s.todo_total) return 0
  return Math.round((s.todos_done / s.todo_total) * 100)
})

const bars = computed(() => data.value?.stats?.bars || [])
const maxBar = computed(() => {
  const m = Math.max(...bars.value.map(b => Object.values(b.counts).reduce((a, b) => a + b, 0)), 1)
  return m
})
const hovered = ref(null)
const barsTotal = b => Object.values(b.counts).reduce((a, b) => a + b, 0)
const CH_NAME = computed(() => Object.fromEntries(
  (data.value?.channels || []).map(c => [c.key, c.name])))
const maxCh = computed(() =>
  Math.max(...(data.value?.channels || []).map(c => c.msgs), 1))

function jump(m) {
  gotoMessages({ channel: m.channel_key, conv: m.conv_key, account: m.account_key || '' })
}

async function openSource(m) {
  sourceNotice.value = await openMessageSource(m)
  clearTimeout(sourceNoticeTimer)
  sourceNoticeTimer = setTimeout(() => { sourceNotice.value = '' }, 5000)
}

function sourceTitle(m) {
  const source = messageSource(m)
  return source.supported ? `点击打开${source.label}` : '点击复制定位信息'
}

/* 重要文字胶囊高亮：标题【】、@提及、时间/日期表达 */
const HL_RE = /(【[^】]{1,14}】|@我|@所有人|@大家|明天|明早|明晚|今晚|后天|大后天|下周[一二三四五六日天]?|本周[一二三四五六日天]?|[上下]午|晚上|\d{1,2}\s*月\s*\d{1,2}\s*[日号]?|\d{1,2}[:：]\d{2}|\d{1,2}\s*点(?:\s*\d{1,2}\s*分)?|下班前|v\d+)/g

function esc(t) {
  return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function hl(t) {
  return esc(t).replace(HL_RE, m => `<mark class="hl">${m}</mark>`)
}
</script>

<template>
  <div v-if="data" class="ov">
    <p v-if="sourceNotice" class="source-notice" role="status">{{ sourceNotice }}</p>
    <div class="glow glow-a" aria-hidden="true" />
    <div class="glow glow-b" aria-hidden="true" />

    <!-- Hero：今日聚光横幅 -->
    <section class="hero card">
      <div class="hero-txt">
        <p class="hi">{{ hello }}，今天有 {{ data.hero.things }} 件事需要你 🔥</p>
        <h1>{{ data.hero.convs }} 个会话 · {{ data.hero.msgs }} 条消息，聚成一束光</h1>
        <p class="sub">已自动分诊：待办 / 日程 / 通知 / 重要已就位，闲聊默认折叠。</p>
        <button class="btn btn-primary" @click="goChat">开始今日聚光 →</button>
      </div>
      <div class="hero-deco"><span>✦</span> <span>✧</span> <span>✦</span></div>
    </section>

    <!-- 渠道进度卡片行 -->
    <section class="ch-row">
      <div v-for="c in data.channels" :key="c.key" class="card ch-card"
        @click="gotoMessages({ channel: c.key })">
        <ChannelIcon :channel="c.key" />
        <div class="ch-main">
          <div class="ch-top">
            <span :class="['ch-dot', CH_CLASS[c.key]]" />
            <b>{{ c.name }}</b>
            <span class="more">···</span>
          </div>
          <p class="big">{{ c.msgs }}<i> 条今日</i></p>
          <div class="ch-track" :title="`占今日最活跃渠道的 ${Math.round((c.msgs / maxCh) * 100)}%`">
            <i :class="CH_CLASS[c.key]" :style="{ width: (c.msgs / maxCh) * 100 + '%' }" />
          </div>
          <p class="mini" :class="{ hot: c.todo }">
            {{ c.type === 'official' ? '官方 API' : c.type === 'imap' ? 'IMAP 水位' : '本地只读 · 实验' }}
            · 待办 {{ c.todo }}
          </p>
        </div>
      </div>
    </section>

    <div class="cols">
      <div class="col-main">
        <!-- 继续查看：重要消息卡片流 -->
        <section class="card block">
          <header class="blk-hd">
            <h3>继续查看</h3>
            <span class="blk-sub">打开即答案 · 待办 {{ data.stats.todos }} 个</span>
          </header>
          <div class="cw">
            <article v-for="m in data.recent" :key="m.id" class="card cw-card"
              :title="sourceTitle(m)" role="link" tabindex="0"
              @click="openSource(m)" @keydown.enter.self.prevent="openSource(m)">
              <header>
                <span :class="['grp', GROUP_CLASS[m.grp]]">{{ GROUP_LABEL[m.grp] }}</span>
                <span class="cw-src">{{ m.conv_title.split('·')[0] }} · {{ senderDisplayName(m) }}</span>
                <button class="heart" :class="{ on: m.star }" @click.stop="star(m)">♥</button>
              </header>
              <p class="cw-txt" v-html="hl(m.text)" />
              <footer>
                <span>{{ m.ts }}</span>
                <span class="cw-actions">
                  <button class="btn mini-btn" @click.stop="jump(m)">聚光内查看</button>
                  <button class="btn mini-btn" @click.stop="openSource(m)">原平台 ↗</button>
                </span>
              </footer>
            </article>
          </div>
        </section>

        <!-- 今日简报表 -->
        <section class="card block">
          <header class="blk-hd">
            <h3>今日简报</h3>
            <span class="blk-sub">昨日摘要 + 今日日程 + 待办清单</span>
          </header>
          <table class="digest">
            <thead><tr><th>来源</th><th>类型</th><th>一行摘要</th><th></th></tr></thead>
            <tbody>
              <tr v-for="m in data.digest" :key="m.id" :title="sourceTitle(m)"
                role="link" tabindex="0" @click="openSource(m)"
                @keydown.enter.self.prevent="openSource(m)">
                <td class="dg-src"><span :class="['ch-dot', CH_CLASS[m.channel_key]]" />{{ m.conv_title.split('·')[0] }}</td>
                <td><span :class="['grp', GROUP_CLASS[m.grp]]">{{ GROUP_LABEL[m.grp] }}</span></td>
                <td class="dg-txt">{{ m.text.slice(0, 30) }}</td>
                <td><button class="btn mini-btn" @click.stop="jump(m)">聚光内查看</button></td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

      <div class="col-side">
        <!-- 统计面板 -->
        <section class="card block">
          <header class="blk-hd"><h3>统计</h3><span class="blk-sub">···</span></header>
          <div class="stat-ring">
            <svg viewBox="0 0 84 84">
              <circle cx="42" cy="42" r="36" class="ring-bg" />
              <circle cx="42" cy="42" r="36" class="ring-fg"
                :stroke-dasharray="`${(doneRate / 100) * 226} 226`" />
              <text x="42" y="47" class="ring-t">{{ doneRate }}%</text>
            </svg>
            <p>待办完成率 · {{ data.stats.todos_done }}/{{ data.stats.todo_total }}<br />
              <em class="pending" v-if="data.stats.pending_events">
                {{ data.stats.pending_events }} 个日程待确认 → 日历页
              </em></p>
          </div>
          <div class="chart">
            <div class="y-axis" aria-hidden="true">
              <span>{{ maxBar }}</span><span>{{ Math.round(maxBar / 2) }}</span><span>0</span>
            </div>
            <div class="plot" @mouseleave="hovered = null">
              <div class="grid" aria-hidden="true"><i v-for="k in 4" :key="k" /></div>
              <div v-for="(b, idx) in bars" :key="b.date" class="bar-col"
                :class="{ today: idx === bars.length - 1 }"
                @mouseenter="hovered = idx">
                <div class="bar-stack">
                  <i v-for="(n, ch) in b.counts" :key="ch" :class="CH_CLASS[ch]"
                    :style="{ height: (n / maxBar) * 110 + 'px' }" />
                </div>
                <span>{{ b.date }}</span>
                <div v-if="hovered === idx" class="tip">
                  <b>{{ b.date }}</b>
                  <em v-for="(n, ch) in b.counts" :key="ch">
                    <span :class="['ch-dot', CH_CLASS[ch]]" />{{ CH_NAME[ch] || ch }} {{ n }}
                  </em>
                  <strong>共 {{ barsTotal(b) }} 条</strong>
                </div>
              </div>
            </div>
          </div>
          <p class="bar-cap">近 7 日消息量（按渠道分色 · 悬停看明细）</p>
        </section>

        <!-- 常用群组 -->
        <section class="card block">
          <header class="blk-hd"><h3>常用会话</h3><span class="blk-sub">＋</span></header>
          <ul class="fav">
            <li v-for="m in data.recent.slice(0, 3)" :key="'f' + m.id"
              @click="jump(m)">
              <span :class="['ch-dot', CH_CLASS[m.channel_key]]" />
              <b>{{ m.conv_title.split('｜')[0] }}</b>
              <button class="btn mini-btn">进入</button>
            </li>
          </ul>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ov { display: flex; flex-direction: column; gap: var(--sp-5); position: relative; }
.source-notice {
  position: relative; z-index: 2; margin: 0; padding: 10px 13px;
  border: 1px solid var(--line); border-left: 3px solid var(--brand); border-radius: 8px;
  background: var(--surface-2); color: var(--text-2); font-size: var(--text-xs); line-height: var(--leading-snug);
}

/* 毛玻璃底：光斑 + 磨砂卡片 */
.glow {
  position: absolute; pointer-events: none; z-index: 0;
  border-radius: 50%; filter: blur(64px); opacity: 0.55;
}
.glow-a {
  width: 420px; height: 260px; top: 110px; right: 40px;
  background: radial-gradient(closest-side, rgba(245, 166, 35, 0.5), transparent);
}
.glow-b {
  width: 380px; height: 240px; top: 640px; left: -60px;
  background: radial-gradient(closest-side, rgba(51, 112, 255, 0.22), transparent);
}
.ov > section, .ov > .cols { position: relative; z-index: 1; }

@supports (backdrop-filter: blur(1px)) {
  .ov .card:not(.hero) {
    background: rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(14px) saturate(1.4);
    -webkit-backdrop-filter: blur(14px) saturate(1.4);
    border-color: rgba(255, 255, 255, 0.7);
    box-shadow: 0 1px 2px rgba(29, 28, 26, 0.04), 0 8px 24px rgba(29, 28, 26, 0.07);
  }
  [data-theme="dark"] .ov .card:not(.hero) {
    background: rgba(32, 31, 29, 0.5);
    border-color: rgba(255, 255, 255, 0.08);
  }
  [data-theme="dark"] .glow { opacity: 0.35; }
}

.hero {
  position: relative; overflow: hidden; color: #fff;
  background:
    radial-gradient(520px 260px at 12% -10%, rgba(255, 235, 200, 0.22), transparent 65%),
    linear-gradient(115deg, #f9bd4a 0%, var(--grad-a) 36%, var(--grad-b) 68%, var(--grad-c) 100%);
  border: none; padding: var(--sp-6) var(--sp-8);
}
.hero::after {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(420px 180px at 88% 20%, rgba(255, 255, 255, 0.18), transparent 70%);
}
.hero::before {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(300px 140px at 95% 95%, rgba(60, 20, 0, 0.18), transparent 70%);
}
.hi { margin: 0 0 var(--sp-1); font-size: var(--text-base); opacity: 0.92; font-weight: 500; line-height: var(--leading-snug); }
h1 {
  margin: 0 0 var(--sp-2);
  font-size: var(--text-3xl);
  font-weight: 750;
  letter-spacing: -0.025em;
  line-height: 1.2;
  text-wrap: balance;
}
.hero .sub { margin: 0 0 var(--sp-5); font-size: var(--text-sm); line-height: var(--leading-snug); opacity: 0.88; }
.hero .btn-primary { background: #fff; border-color: #fff; color: #7a3a0a; }
.hero .btn-primary:hover { background: #fff; color: #5c2a04; }
.hero-deco { position: absolute; right: 44px; top: 32px; font-size: 18px; }
.hero-deco span { display: inline-block; animation: twinkle 2.4s ease-in-out infinite; }
.hero-deco span:nth-child(2) { animation-delay: 0.8s; }
.hero-deco span:nth-child(3) { animation-delay: 1.6s; }

.ch-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: var(--sp-3); }
.ch-card {
  display: flex; gap: var(--sp-3); align-items: flex-start;
  padding: var(--sp-4); cursor: pointer;
}
.ch-main { flex: 1; min-width: 0; }
.ch-track {
  height: 4px; border-radius: 999px; background: var(--surface-2);
  overflow: hidden; margin: var(--sp-2) 0 var(--sp-1);
}
.ch-track i {
  display: block; height: 100%; border-radius: 999px; min-width: 0;
  transition: width 0.5s var(--ease-spring);
}
.ch-top { display: flex; align-items: center; gap: var(--sp-2); }
.ch-top b { font-size: var(--text-base); font-weight: 650; }
.more { margin-left: auto; color: var(--text-3); letter-spacing: 2px; }
.big { font-size: 26px; font-weight: 650; margin: var(--sp-2) 0 var(--sp-1); letter-spacing: -0.025em; line-height: 1.15; }
.big i { font-style: normal; font-size: var(--text-xs); color: var(--text-3); font-weight: 400; margin-left: 3px; }
.mini { margin: 0; font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--text-3); }
.mini.hot { color: var(--brand-strong); font-weight: 600; }

.cols { display: grid; grid-template-columns: 1fr 320px; gap: var(--sp-4); align-items: start; }
.block { padding: var(--sp-5); }
.blk-hd { display: flex; align-items: baseline; gap: var(--sp-3); margin-bottom: var(--sp-4); }
.blk-hd h3 { margin: 0; font-family: var(--font-display); font-size: var(--text-lg); font-weight: 700; letter-spacing: -0.015em; }
.blk-sub { font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--text-3); margin-left: auto; }

.cw { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: var(--sp-3); }
.cw-card { padding: var(--sp-4); cursor: pointer; border-radius: 12px; transition: transform 150ms ease, box-shadow 150ms ease; }
.cw-card:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(29, 28, 26, .08); }
.cw-card:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.cw-card header { display: flex; align-items: center; gap: var(--sp-2); }
.cw-src { font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.heart { margin-left: auto; border: none; background: none; color: var(--line); font-size: 14px; transition: transform var(--dur-1) var(--ease-spring), color var(--dur-1); }
.heart:hover { transform: scale(1.25); }
.heart.on { color: var(--warn); }
.cw-txt {
  font-size: var(--text-base); font-weight: 500; margin: var(--sp-3) 0 var(--sp-2); line-height: var(--leading-relaxed);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
/* 重要文字圆角胶囊高亮（v-html 注入，需 :deep） */
.cw-txt :deep(.hl) {
  background: var(--brand-weak); color: var(--brand-strong);
  border-radius: 999px; padding: 1px 7px; margin: 0 2px;
  font-weight: 600; white-space: nowrap; display: inline-block;
}
.cw-card footer { display: flex; align-items: center; gap: 8px; font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--text-3); }
.cw-actions { display: flex; gap: 5px; margin-left: auto; }
.cw-actions .mini-btn { height: 26px; padding: 0 9px; font-size: var(--text-2xs); }

.digest { width: 100%; border-collapse: collapse; font-size: var(--text-sm); line-height: var(--leading-snug); }
.digest th { text-align: left; font-size: var(--text-2xs); color: var(--text-3); font-weight: 650; padding: var(--sp-2) var(--sp-2); }
.digest td { padding: 11px var(--sp-2); border-top: 1px solid var(--line); vertical-align: middle; transition: background var(--dur-1); }
.digest tbody tr { cursor: pointer; transition: background var(--dur-1) var(--ease-out); }
.digest tbody tr:hover { background: var(--surface-2); }
.digest tbody tr:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; }
.dg-src { white-space: nowrap; font-weight: 500; }
.dg-txt { color: var(--text-2); }
.mini-btn { height: 28px; padding: 0 12px; font-size: var(--text-xs); }

.stat-ring { display: flex; gap: var(--sp-4); align-items: center; margin-bottom: var(--sp-4); }
.ring-bg { fill: var(--surface-2); stroke: var(--surface-2); stroke-width: 8; }
.ring-fg {
  fill: none; stroke: var(--brand); stroke-width: 8; stroke-linecap: round;
  transform: rotate(-90deg); transform-origin: center;
  transition: stroke-dasharray 0.6s var(--ease-spring);
}
.ring-t { text-anchor: middle; font-size: 16px; font-weight: 700; fill: var(--text); }
.stat-ring p { font-size: var(--text-xs); color: var(--text-2); line-height: var(--leading-normal); margin: 0; }
.pending { color: var(--brand-strong); font-style: normal; font-weight: 600; }

.chart { display: flex; gap: 6px; margin-bottom: var(--sp-4); }
.y-axis {
  width: 22px; height: 126px; display: flex; flex-direction: column;
  justify-content: space-between; align-items: flex-end;
  font-size: 9px; color: var(--text-3); font-variant-numeric: tabular-nums;
  padding-top: 12px;
}
.plot {
  flex: 1; position: relative; display: flex; gap: 6px;
  align-items: flex-end; justify-content: space-between; padding-top: 12px;
}
.grid {
  position: absolute; left: 0; right: 0; bottom: 16px; height: 110px;
  display: flex; flex-direction: column; justify-content: space-between;
  pointer-events: none;
}
.grid i { border-top: 1px dashed var(--line); }

.bar-col { position: relative; display: flex; flex-direction: column; align-items: center; }
.bar-col span {
  font-size: 10px; color: var(--text-3); line-height: 16px; height: 16px;
  font-variant-numeric: tabular-nums;
}
.bar-col.today span { color: var(--brand-strong); font-weight: 600; }
.bar-col.today .bar-stack { background: var(--brand-weak); border-radius: 6px; padding: 0 3px; }
.bar-stack {
  display: flex; flex-direction: column-reverse; align-items: center;
  padding: 0 3px; transition: background var(--dur-1);
}
.bar-stack i {
  width: 14px; border-radius: 3px 3px 0 0; display: block; min-height: 2px;
  transition: height 0.5s var(--ease-out);
}
.bar-col:hover .bar-stack { background: var(--surface-2); border-radius: 6px; }

.tip {
  position: absolute; bottom: calc(100% - 8px); left: 50%; transform: translateX(-50%);
  background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
  box-shadow: var(--shadow-1); padding: 6px 9px; z-index: 3;
  display: flex; flex-direction: column; gap: 2px; white-space: nowrap;
  font-size: 10.5px; color: var(--text-2);
}
.tip b { font-size: 11px; color: var(--text); }
.tip em { font-style: normal; display: flex; align-items: center; gap: 5px; }
.tip em .ch-dot { width: 6px; height: 6px; }
.tip strong { color: var(--brand-strong); font-size: 10.5px; margin-top: 2px; }
.bar-col:nth-last-child(-n+2) .tip { left: auto; right: 0; transform: none; }

.bar-cap { font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--text-3); text-align: center; margin: var(--sp-3) 0 0; }

.fav { list-style: none; margin: 0; padding: 0; }
.fav li { display: flex; align-items: center; gap: var(--sp-3); padding: var(--sp-2) var(--sp-1); cursor: pointer; border-radius: var(--radius-sm); }
.fav b { font-size: var(--text-sm); line-height: var(--leading-snug); font-weight: 650; }
.fav .btn { margin-left: auto; }

@media (max-width: 1100px) {
  .ch-row { grid-template-columns: repeat(3, 1fr); }
  .cols { grid-template-columns: 1fr; }
}
</style>
