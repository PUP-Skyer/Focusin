<script setup>
const props = defineProps({
  mood: { type: String, default: 'idle' }, // idle|working|waiting|happy|error
  size: { type: Number, default: 40 }
})

const FACE = {
  idle: '🕊️', working: '⚙️', waiting: '🙋', happy: '🎉', error: '💧'
}
const RING = {
  idle: 'var(--text-3)', working: 'var(--brand)',
  waiting: '#f2b84b', happy: 'var(--ok)', error: 'var(--warn)'
}
</script>

<template>
  <div class="mascot" :class="{ breathe: mood === 'idle', pulse: mood === 'working' }"
    :style="{ width: size + 'px', height: size + 'px' }">
    <span class="face">{{ FACE[mood] || '🕊️' }}</span>
    <i v-if="mood === 'working'" class="dot" :style="{ background: RING[mood] }" />
  </div>
</template>

<style scoped>
.mascot {
  position: relative; border-radius: 50%;
  background: var(--brand-weak);
  display: flex; align-items: center; justify-content: center;
  user-select: none;
}
.face { font-size: calc(0.55em + 10px); line-height: 1; }
.breathe { animation: breathe 3.5s ease-in-out infinite; }
.pulse { animation: badge-pop 1.2s ease-in-out infinite; }
.dot {
  position: absolute; right: 0; bottom: 0; width: 9px; height: 9px;
  border-radius: 50%; border: 2px solid var(--surface);
}
</style>
