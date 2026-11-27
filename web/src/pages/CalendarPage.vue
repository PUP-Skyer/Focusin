<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { get, post, CH_CLASS, messageSource, openMessageSource } from '../api.js'

const gotoMessages = inject('gotoMessages')
const events = ref([])
const month = ref(new Date())
const sourceNotice = ref('')
let sourceNoticeTimer

async function load() {
  events.value = await get('/schedule')
}
onMounted(() => { load(); setInterval(load, 15000) })

async function confirm(e) { await post(`/schedule/${e.id}/confirm`); load() }
async function dismiss(e) { await post(`/schedule/${e.id}/dismiss`); load() }

async function openSource(e) {
  if (!e.source) return
  if (messageSource(e.source).supported) {
    sourceNotice.value = await openMessageSource(e.source)
    clearTimeout(sourceNoticeTimer)
    sourceNoticeTimer = setTimeout(() => { sourceNotice.value = '' }, 5000)
    return
  }
  if (!e.source_msg_id || !e.src_channel || !e.src_conv_key) return
  gotoMessages({ channel: e.src_channel, conv: e.src_conv_key, account: e.src_account || '' })
}

const pending = computed(() => events.value.filter(e => e.status === 'pending'))
const confirmed = computed(() => events.value.filter(e => e.status === 'confirmed'))

const WD = ['一', '二', '三', '四', '五', '六', '日']
const grid = computed(() => {
  const y = month.value.getFullYear(), m = month.value.getMonth()
  const first = new Date(y, m, 1)
  const start = new Date(first)
  start.setDate(1 - ((first.getDay() + 6) % 7)) // 周一开头
  const days = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    days.push({
      d, key, out: d.getMonth() !== m,
      evs: events.value.filter(e => e.start_at.startsWith(key))
    })
  }
  return days
})

function shift(n) {
  month.value = new Date(month.value.getFullYear(), month.value.getMonth() + n, 1)
}
const isToday = (k) => k === new Date().toISOString().slice(0, 10)
</script>

<template>
  <div class="cal">
    <p v-if="sourceNotice" class="source-notice" role="status">{{ sourceNotice }}</p>
    <!-- 待确认日程：仅展示重点，点击卡片查看原文 -->
    <section v-if="pending.length" class="card block">
      <header class="blk-hd"><h3>待确认日程</h3>
        <span class="blk-sub">仅展示重点 · 点击卡片查看原文</span>
      </header>
      <div class="confirm-row">
        <article v-for="e in pending" :key="e.id" class="confirm card"
          :class="{ clickable: e.source_msg_id && e.src_conv_key }"
          @click="openSource(e)">
          <div class="c-when">
            <b>{{ e.start_at.slice(5, 10) }}</b>
            <span>{{ e.start_at.slice(11, 16) }}</span>
          </div>
          <div class="c-body">
            <div class="c-topline">
              <span class="c-status">待确认</span>
              <span class="c-source">{{ e.src_channel === 'email' ? '邮件' : '群消息' }}</span>
            </div>
            <b class="c-title" :title="e.title">{{ e.title }}</b>
            <div class="c-acts" @click.stop @keydown.stop>
              <button class="btn btn-brand" @click="confirm(e)">确认入库</button>
              <button class="btn" @click="dismiss(e)">忽略</button>
              <button v-if="e.source_msg_id && e.src_conv_key" class="btn btn-link"
                @click.stop="openSource(e)">查看详情 ↗</button>
            </div>
          </div>
        </article>
      </div>
    </section>

    <div class="cal-cols">
      <section class="card block">
        <header class="blk-hd">
          <button class="btn mini-btn" @click="shift(-1)">‹</button>
          <h3>{{ month.getFullYear() }} 年 {{ month.getMonth() + 1 }} 月</h3>
          <button class="btn mini-btn" @click="shift(1)">›</button>
        </header>
        <div class="grid">
          <span v-for="w in WD" :key="w" class="wd">{{ w }}</span>
          <button v-for="g in grid" :key="g.key" class="day"
            :class="{ out: g.out, today: isToday(g.key) }">
            {{ g.d.getDate() }}
            <i v-for="e in g.evs" :key="e.id" :title="e.title"
              :class="[e.status === 'confirmed' ? 'ev-on' : 'ev-pending']" />
          </button>
        </div>
      </section>

      <section class="card block">
        <header class="blk-hd"><h3>日程清单</h3>
          <span class="blk-sub">{{ confirmed.length }} 个已确认</span>
        </header>
        <ul class="evs">
          <li v-for="e in events" :key="e.id" :class="{ clickable: e.source_msg_id && e.src_conv_key }"
            @click="openSource(e)">
            <span :class="['ch-dot', CH_CLASS[e.src_channel || 'feishu']]"></span>
            <div class="e-body">
              <b>{{ e.start_at.slice(5, 16) }}</b>
              <span class="e-title" :title="e.title">{{ e.title }}</span>
              <em v-if="e.status === 'pending'">待确认</em>
              <span v-if="e.source_msg_id && e.src_conv_key" class="e-arrow">↗</span>
            </div>
          </li>
        </ul>
        <p v-if="!events.length" class="empty">还没有日程，去消息流页「模拟新消息入站」试试。</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.block { padding: var(--sp-5); margin-bottom: var(--sp-4); }
.source-notice {
  margin: 0 0 var(--sp-3); padding: 10px 12px; border: 1px solid var(--line);
  border-left: 3px solid var(--brand); border-radius: 8px;
  background: var(--surface-2); color: var(--text-2); font-size: var(--text-xs); line-height: var(--leading-snug);
}
.blk-hd { display: flex; align-items: baseline; gap: var(--sp-3); margin-bottom: var(--sp-4); }
.blk-hd h3 { margin: 0; font-family: var(--font-display); font-size: var(--text-lg); font-weight: 700; letter-spacing: -0.015em; }
.blk-sub { font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--text-3); margin-left: auto; }
.mini-btn { padding: 0 10px; font-size: var(--text-xs); }

.confirm-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--sp-3); }
.confirm {
  display: flex; gap: var(--sp-4); padding: var(--sp-4) var(--sp-5);
  background: var(--surface-2); border-color: transparent; box-shadow: none;
  transition: border-color 160ms, background 160ms, transform 160ms;
}
.confirm.clickable { cursor: pointer; }
.confirm.clickable:hover {
  background: var(--surface); border-color: var(--line); transform: translateY(-1px);
}
.c-when {
  flex: 0 0 62px; align-self: flex-start; text-align: center;
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-sm);
  padding: 10px 6px;
}
.c-when b { display: block; font-size: 18px; line-height: 1.1; color: var(--brand-strong); letter-spacing: -0.03em; }
.c-when span { display: block; margin-top: 6px; font-size: var(--text-xs); line-height: 1.3; color: var(--text-2); font-variant-numeric: tabular-nums; }
.c-body { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.c-topline { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.c-status {
  display: inline-flex; align-items: center; min-height: 20px; padding: 0 8px;
  border-radius: 999px; background: var(--brand-weak); color: var(--brand-strong);
  font-size: var(--text-2xs); font-weight: 650;
}
.c-source { font-size: var(--text-2xs); line-height: 1.35; color: var(--text-3); }
.c-title {
  display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical;
  -webkit-line-clamp: 2; font-size: var(--text-md); line-height: var(--leading-snug); font-weight: 650;
  letter-spacing: -0.01em; overflow-wrap: anywhere;
}
.c-acts { display: flex; align-items: center; gap: var(--sp-2); margin-top: 14px; }
.btn-link { margin-left: auto; padding-inline: 2px; color: var(--brand-strong); background: transparent; border-color: transparent; }
.btn-link:hover { background: transparent; color: var(--brand); }

.cal-cols { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; }
.grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.wd { text-align: center; font-size: var(--text-xs); line-height: 1.35; color: var(--text-3); padding: 5px 0; }
.day { border: none; background: var(--surface-2); border-radius: 8px; aspect-ratio: 1;
  font-size: var(--text-sm); line-height: 1.2; color: var(--text); display: flex; flex-direction: column; align-items: center;
  padding-top: 5px; gap: 3px; position: relative; }
.day.out { color: var(--text-3); background: transparent; }
.day.today { outline: 2px solid var(--brand); }
.day i { width: 5px; height: 5px; border-radius: 50%; }
.ev-on { background: var(--brand); }
.ev-pending { background: var(--text-3); }

.evs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.evs li { display: flex; gap: 10px; align-items: center; padding: 10px 8px; border-radius: 8px; }
.evs li.clickable { cursor: pointer; }
.evs li.clickable:hover { background: var(--surface-2); }
.e-body { min-width: 0; flex: 1; display: flex; align-items: center; gap: 8px; }
.e-body b { flex: 0 0 auto; font-size: var(--text-xs); line-height: 1.35; color: var(--text-3); font-weight: 600; font-variant-numeric: tabular-nums; }
.e-title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--text-sm); line-height: 1.4; }
.e-body em { flex: 0 0 auto; font-style: normal; font-size: var(--text-2xs); color: var(--brand-strong); }
.e-arrow { flex: 0 0 auto; margin-left: auto; color: var(--text-3); font-size: var(--text-xs); }
.empty { color: var(--text-3); font-size: var(--text-xs); line-height: var(--leading-normal); }
</style>
