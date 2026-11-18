<script setup lang="ts">
import { ref } from 'vue'

const from = defineModel<string>('from', { required: true })
const to = defineModel<string>('to', { required: true })
const emit = defineEmits<{ apply: []; preset: [preset: 'all' | 'today' | 'week' | 'month-days' | 'month'] }>()
const props = defineProps<{ error: string; label: string }>()
const panel = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const presets = [
  ['all', '不限时间'], ['today', '今天'], ['week', '最近 7 天'],
  ['month-days', '最近 30 天'], ['month', '本月'],
] as const

function close() {
  panel.value?.hidePopover()
  trigger.value?.focus({ preventScroll: true })
}

function apply() {
  emit('apply')
  if (!from.value || !to.value || from.value <= to.value) close()
}
</script>

<template>
  <div class="date-range-picker">
    <button ref="trigger" type="button" class="search-clear" popovertarget="knowledge-date-range">{{ props.label }}</button>
    <div id="knowledge-date-range" ref="panel" class="zh-popover date-range-panel" popover role="group" aria-label="笔记日期范围">
      <div class="date-presets">
        <button v-for="[key, label] in presets" :key="key" type="button"
          @click="emit('preset', key); close()">{{ label }}</button>
      </div>
      <form class="custom-range" @submit.prevent="apply">
        <p>自定义日期</p>
        <label>开始日期<input v-model="from" type="date" /></label>
        <label>结束日期<input v-model="to" type="date" /></label>
        <p v-if="props.error" role="alert" class="date-error">{{ props.error }}</p>
        <button type="submit" class="range-apply">应用日期</button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.date-range-panel { width: min(340px, calc(100vw - 24px)); }
.date-presets { display: flex; flex-wrap: wrap; gap: var(--zh-gap-sm); }
.date-presets button, .range-apply, .custom-range input {
  min-height: var(--zh-control-height);
  padding: 4px 9px;
  border: 1px solid var(--zh-border);
  border-radius: var(--zh-radius-sm);
  background: var(--zh-field);
  color: var(--zh-ink);
}
.date-presets button:hover { border-color: var(--zh-accent); }
.custom-range { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--zh-gap-sm); margin-top: 12px; }
.custom-range p, .range-apply { grid-column: 1 / -1; }
.custom-range label { display: grid; gap: 4px; min-width: 0; color: var(--zh-muted); }
.custom-range input { width: 100%; min-width: 0; }
.custom-range .range-apply { background: var(--zh-accent); color: white; }
.date-error { color: #963d32; }
</style>
