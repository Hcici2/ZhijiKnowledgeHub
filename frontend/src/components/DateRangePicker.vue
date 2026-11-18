<script setup lang="ts">
import { ref } from 'vue'
import NoteCalendar from './NoteCalendar.vue'

const from = defineModel<string>('from', { required: true })
const to = defineModel<string>('to', { required: true })
const emit = defineEmits<{ apply: []; preset: [preset: 'all' | 'today' | 'week' | 'month-days' | 'month'] }>()
const props = defineProps<{ error: string; label: string }>()
const panel = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const now = new Date()
const today = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-')
const calendarDay = ref(today)
const calendarOpen = ref(false)
const pickEnd = ref(false)
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

function selectDay(day: string) {
  calendarDay.value = day
  if (pickEnd.value) to.value = day
  else {
    from.value = day
    to.value = ''
  }
  pickEnd.value = !pickEnd.value
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
      <details class="date-calendar" @toggle="calendarOpen = ($event.currentTarget as HTMLDetailsElement).open">
        <summary>打开日历选择</summary>
        <template v-if="calendarOpen">
          <p aria-live="polite">{{ pickEnd ? '选择结束日期' : '选择开始日期' }}</p>
          <NoteCalendar :selected-day="calendarDay" :today="today" :counts="{}" item-label="日期" range-picker
            @navigate="calendarDay = $event" @select="selectDay" @today="selectDay(today)" />
        </template>
      </details>
    </div>
  </div>
</template>

<style scoped>
.date-range-panel { width: min(340px, calc(100vw - 24px)); }
.date-range-picker > button {
  min-height: var(--zh-control-height);
  padding: 4px 10px;
  border: 1px solid var(--zh-border);
  border-radius: var(--zh-radius-sm);
  background: var(--zh-panel);
  color: var(--zh-ink);
  font-size: 13px;
}
.date-range-picker > button:hover { background: var(--zh-field); }
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
.date-calendar { margin-top: 8px; color: var(--zh-muted); }
.date-calendar summary { cursor: pointer; }
.date-calendar :deep(.calendar) { padding: 6px; margin-top: 5px; }
.date-calendar :deep(.calendar-day) { min-height: 28px; aspect-ratio: auto; padding: 3px; }
</style>
