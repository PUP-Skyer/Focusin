<script setup>
import { computed, onMounted, ref } from 'vue'
import { get, post, CH_CLASS } from '../api.js'

const events = ref([])
const month = ref(new Date())

async function load() {
  events.value = await get('/schedule')
}
onMounted(() => { load(); setInterval(load, 15000) })

async function confirm(e) { await post(`/schedule/${e.id}/confirm`); load() }
async function dismiss(e) { await post(`/schedule/${e.id}/dismiss`); load() }

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
    <!-- 待确认日程（防幻觉：展示原文依据） -->
    <section v-if="pending.length" class="card block">
      <header class="blk-hd"><h3>待确认日程</h3>
        <span class="blk-sub">从消息中提取 · 展示原文依据，确认后落库生效</span>
      </header>
      <div class="confirm-row">
        <article v-for="e in pending" :key="e.id" class="confirm card">
          <div class="c-when">
            <b>{{ e.start_at.slice(5, 10) }}</b>
            <span>{{ e.start_at.slice(11, 16) }}</span>
          </div>
          <div class="c-body">
            <b>{{ e.title }}</b>
            <p class="src">依据原文：[{{ e.source?.ts }}] {{ e.source?.sender }}：「{{ e.source?.text }}」</p>
            <div class="c-acts">
              <button class="btn btn-brand" @click="confirm(e)">确认入库 · 双提醒生效</button>
              <button class="btn" @click="dismiss(e)">忽略</button>
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
          <li v-for="e in events" :key="e.id">
            <span :class="['ch-dot', CH_CLASS[e.src_channel || 'feishu']]"></span>
            <div class="e-body">
              <b>{{ e.start_at }}</b>
              <span>{{ e.title }}</span>
              <em v-if="e.status === 'pending'">待确认</em>
              <p class="src" v-if="e.source">来自：{{ e.source.conv }} · {{ e.source.sender }}</p>
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
.blk-hd { display: flex; align-items: center; gap: var(--sp-3); margin-bottom: var(--sp-4); }
.blk-hd h3 { margin: 0; font-size: 16px; font-weight: 700; letter-spacing: -0.01em; }
.blk-sub { font-size: 11px; color: var(--text-3); margin-left: auto; }
.mini-btn { padding: 0 10px; font-size: 12px; }

.confirm-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: var(--sp-3); }
.confirm {
  display: flex; gap: var(--sp-4); padding: var(--sp-4);
  background: var(--surface-2); border-color: transparent; box-shadow: none;
}
.c-when {
  text-align: center; background: var(--surface); border-radius: var(--radius-sm);
  padding: var(--sp-3) var(--sp-3); min-width: 64px;
}
.c-when b { display: block; font-size: 16px; color: var(--brand-strong); letter-spacing: -0.02em; }
.c-when span { font-size: 12px; }
.c-body b { font-size: 14px; font-weight: 600; }
.src { font-size: 11px; color: var(--text-2); margin: var(--sp-1) 0 var(--sp-3); line-height: 1.5; }
.c-acts { display: flex; gap: var(--sp-2); }

.cal-cols { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; }
.grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.wd { text-align: center; font-size: 11px; color: var(--text-3); padding: 4px 0; }
.day { border: none; background: var(--surface-2); border-radius: 8px; aspect-ratio: 1;
  font-size: 12px; color: var(--text); display: flex; flex-direction: column; align-items: center;
  padding-top: 4px; gap: 2px; position: relative; }
.day.out { color: var(--text-3); background: transparent; }
.day.today { outline: 2px solid var(--brand); }
.day i { width: 5px; height: 5px; border-radius: 50%; }
.ev-on { background: var(--brand); }
.ev-pending { background: var(--text-3); }

.evs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.evs li { display: flex; gap: 10px; align-items: flex-start; padding: 8px;
  border-radius: 8px; }
.evs li:hover { background: var(--surface-2); }
.e-body b { font-size: 12px; color: var(--text-2); margin-right: 8px; font-weight: 600; }
.e-body span { font-size: 13px; }
.e-body em { font-style: normal; font-size: 10px; color: var(--brand-strong); margin-left: 6px; }
.e-body .src { margin: 2px 0 0; }
.empty { color: var(--text-3); font-size: 12px; }
</style>
