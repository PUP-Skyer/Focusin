<script setup>
defineProps({ channel: String })
const TILE = {
  wechat: '#07c160', feishu: '#3370ff', dingtalk: '#0089ff',
  qq: '#12b7f5', email: '#ff9d00'
}
</script>

<template>
  <span class="chic" :style="{ background: TILE[channel] || 'var(--brand)' }">
    <svg v-if="channel === 'wechat'" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
      <circle cx="8.7" cy="11" r=".7" fill="currentColor" stroke="none" />
      <circle cx="12.6" cy="11" r=".7" fill="currentColor" stroke="none" />
    </svg>
    <svg v-else-if="channel === 'feishu'" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M22 2 11 13" />
      <path d="M22 2 15 22l-4-9-9-4 20-7z" />
    </svg>
    <svg v-else-if="channel === 'dingtalk'" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <path d="M8 9h8M8 12.5h5" />
    </svg>
    <svg v-else-if="channel === 'qq'" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="7.8" r="4.2" />
      <path d="M5.5 21c.6-4.5 3-7.6 6.5-7.6s5.9 3.1 6.5 7.6" />
      <circle cx="10.4" cy="7.6" r=".6" fill="currentColor" stroke="none" />
      <circle cx="13.6" cy="7.6" r=".6" fill="currentColor" stroke="none" />
    </svg>
    <svg v-else-if="channel === 'email'" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </svg>
    <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
    </svg>
  </span>
</template>

<style scoped>
.chic {
  width: 34px; height: 34px; flex-shrink: 0; border-radius: 10px;
  display: inline-flex; align-items: center; justify-content: center;
  color: #fff;
  box-shadow: 0 2px 6px rgba(29, 28, 26, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.25);
}
.chic svg { width: 19px; height: 19px; }
</style>
