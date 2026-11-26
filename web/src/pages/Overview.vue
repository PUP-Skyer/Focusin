<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { get, post, GROUP_LABEL, GROUP_CLASS, CH_CLASS } from '../api.js'

const gotoMessages = inject('gotoMessages')
const goChat = inject('goChat')
const data = ref(null)

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

function jump(m) {
  gotoMessages({ channel: m.channel_key, conv: m.conv_key })
}
</script>

<template>
  <div v-if="data" class="ov">

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
        <div class="ch-top">
          <span :class="['ch-dot', CH_CLASS[c.key]]" />
          <b>{{ c.name }}</b>
          <span class="more">···</span>
        </div>
        <p class="big">{{ c.msgs }}<i> 条今日</i></p>
        <p class="mini" :class="{ hot: c.todo }">
          {{ c.type === 'official' ? '官方 API' : c.type === 'imap' ? 'IMAP 水位' : '本地只读 · 实验' }}
          · 待办 {{ c.todo }}
        </p>
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
              @click="jump(m)">
              <header>
                <span :class="['grp', GROUP_CLASS[m.grp]]">{{ GROUP_LABEL[m.grp] }}</span>
                <span class="cw-src">{{ m.conv_title.split('·')[0] }} · {{ m.sender }}</span>
                <button class="heart" :class="{ on: m.star }" @click.stop="star(m)">♥</button>
              </header>
              <p class="cw-txt">{{ m.text }}</p>
              <footer>{{ m.ts }}</footer>
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
              <tr v-for="m in data.digest" :key="m.id">
                <td class="dg-src"><span :class="['ch-dot', CH_CLASS[m.channel_key]]" />{{ m.conv_title.split('·')[0] }}</td>
                <td><span :class="['grp', GROUP_CLASS[m.grp]]">{{ GROUP_LABEL[m.grp] }}</span></td>
                <td class="dg-txt">{{ m.text.slice(0, 30) }}</td>
                <td><button class="btn mini-btn" @click="jump(m)">跳转原文 →</button></td>
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
          <div class="bars">
            <div v-for="b in bars" :key="b.date" class="bar-col" :title="b.date">
              <div class="bar-stack">
                <i v-for="(n, ch) in b.counts" :key="ch" :class="CH_CLASS[ch]"
                  :style="{ height: (n / maxBar) * 90 + 'px' }" :title="ch + ' ' + n" />
              </div>
              <span>{{ b.date }}</span>
            </div>
          </div>
          <p class="bar-cap">近 7 日消息量（按渠道分色）</p>
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
.ov { display: flex; flex-direction: column; gap: var(--sp-4); }

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
.hi { margin: 0 0 var(--sp-1); font-size: 13px; opacity: 0.92; font-weight: 500; }
h1 {
  margin: 0 0 var(--sp-1);
  font-size: clamp(22px, 2.6vw, 28px);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.22;
  text-wrap: balance;
}
.hero .sub { margin: 0 0 var(--sp-4); font-size: 12px; opacity: 0.85; }
.hero .btn-primary { background: #fff; border-color: #fff; color: #7a3a0a; }
.hero .btn-primary:hover { background: #fff; color: #5c2a04; }
.hero-deco { position: absolute; right: 44px; top: 32px; font-size: 18px; }
.hero-deco span { display: inline-block; animation: twinkle 2.4s ease-in-out infinite; }
.hero-deco span:nth-child(2) { animation-delay: 0.8s; }
.hero-deco span:nth-child(3) { animation-delay: 1.6s; }

.ch-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--sp-3); }
.ch-card { padding: var(--sp-3) var(--sp-4); cursor: pointer; }
.ch-top { display: flex; align-items: center; gap: var(--sp-2); }
.ch-top b { font-size: 13px; font-weight: 600; }
.more { margin-left: auto; color: var(--text-3); letter-spacing: 2px; }
.big { font-size: 24px; font-weight: 700; margin: var(--sp-2) 0 var(--sp-1); letter-spacing: -0.02em; line-height: 1.15; }
.big i { font-style: normal; font-size: 11px; color: var(--text-3); font-weight: 400; margin-left: 2px; }
.mini { margin: 0; font-size: 11px; color: var(--text-3); }
.mini.hot { color: var(--brand-strong); font-weight: 600; }

.cols { display: grid; grid-template-columns: 1fr 320px; gap: var(--sp-4); align-items: start; }
.block { padding: var(--sp-5); }
.blk-hd { display: flex; align-items: baseline; gap: var(--sp-3); margin-bottom: var(--sp-4); }
.blk-hd h3 { margin: 0; font-size: 16px; font-weight: 700; letter-spacing: -0.01em; }
.blk-sub { font-size: 11px; color: var(--text-3); margin-left: auto; }

.cw { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--sp-3); }
.cw-card { padding: var(--sp-3); cursor: pointer; }
.cw-card header { display: flex; align-items: center; gap: var(--sp-2); }
.cw-src { font-size: 11px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.heart { margin-left: auto; border: none; background: none; color: var(--line); font-size: 14px; transition: transform var(--dur-1) var(--ease-spring), color var(--dur-1); }
.heart:hover { transform: scale(1.25); }
.heart.on { color: var(--warn); }
.cw-txt {
  font-size: 13.5px; font-weight: 500; margin: var(--sp-2) 0 var(--sp-1); line-height: 1.55;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.cw-card footer { font-size: 11px; color: var(--text-3); }

.digest { width: 100%; border-collapse: collapse; font-size: 13px; }
.digest th { text-align: left; font-size: 11px; color: var(--text-3); font-weight: 500; padding: var(--sp-1) var(--sp-2); }
.digest td { padding: 9px var(--sp-2); border-top: 1px solid var(--line); vertical-align: middle; transition: background var(--dur-1); }
.digest tbody tr { transition: background var(--dur-1) var(--ease-out); }
.digest tbody tr:hover { background: var(--surface-2); }
.dg-src { white-space: nowrap; font-weight: 500; }
.dg-txt { color: var(--text-2); }
.mini-btn { height: 26px; padding: 0 12px; font-size: 11px; }

.stat-ring { display: flex; gap: var(--sp-4); align-items: center; margin-bottom: var(--sp-4); }
.ring-bg { fill: var(--surface-2); stroke: var(--surface-2); stroke-width: 8; }
.ring-fg {
  fill: none; stroke: var(--brand); stroke-width: 8; stroke-linecap: round;
  transform: rotate(-90deg); transform-origin: center;
  transition: stroke-dasharray 0.6s var(--ease-spring);
}
.ring-t { text-anchor: middle; font-size: 16px; font-weight: 700; fill: var(--text); }
.stat-ring p { font-size: 12px; color: var(--text-2); line-height: 1.7; margin: 0; }
.pending { color: var(--brand-strong); font-style: normal; font-weight: 600; }

.bars { display: flex; gap: var(--sp-2); align-items: flex-end; justify-content: space-between; }
.bar-col { display: flex; flex-direction: column; align-items: center; gap: var(--sp-1); }
.bar-stack { display: flex; flex-direction: column-reverse; align-items: center; }
.bar-stack i { width: 16px; border-radius: 4px 4px 0 0; display: block; transition: height 0.4s var(--ease-out); }
.bar-col span { font-size: 10px; color: var(--text-3); }
.bar-cap { font-size: 11px; color: var(--text-3); text-align: center; margin: var(--sp-3) 0 0; }

.fav { list-style: none; margin: 0; padding: 0; }
.fav li { display: flex; align-items: center; gap: var(--sp-3); padding: var(--sp-2) var(--sp-1); cursor: pointer; border-radius: var(--radius-sm); }
.fav b { font-size: 13px; font-weight: 600; }
.fav .btn { margin-left: auto; }

@media (max-width: 1100px) {
  .ch-row { grid-template-columns: repeat(3, 1fr); }
  .cols { grid-template-columns: 1fr; }
}
</style>
