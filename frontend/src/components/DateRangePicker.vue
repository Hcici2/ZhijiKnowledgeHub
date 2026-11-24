<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import AppIcon from './AppIcon.vue'
import NoteCalendar from './NoteCalendar.vue'

const props = defineProps<{ from: string; to: string; label: string }>()
const presets = [
  ['all', '不限时间'], ['today', '今天'], ['week', '最近 7 天'],
  ['month-days', '最近 30 天'], ['month', '本月']
] as const
const emit = defineEmits<{ apply: [from: string, to: string]; preset: [value: typeof presets[number][0]] }>()
const id = useId()
const panel = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const start = ref('')
const end = ref('')
const field = ref<'start' | 'end'>('start')
const today = ref('')
const cursor = ref('')
const opened = ref(false)
const invalid = computed(() => Boolean(start.value && end.value && end.value < start.value))

function dateLabel(value: string) {
  return value ? value.replace(/^(\d+)-0?(\d+)-0?(\d+)$/, '$1年$2月$3日') : '不限'
}

function beforeToggle(event: ToggleEvent) {
  opened.value = event.newState === 'open'
  if (!opened.value) return
  const now = new Date()
  today.value = [now.getFullYear(), String(now.getMonth()+1).padStart(2,'0'), String(now.getDate()).padStart(2,'0')].join('-')
  start.value = props.from
  end.value = props.to
  field.value = 'start'
  cursor.value = props.from || props.to || today.value
}

function restoreFocus(event: ToggleEvent) {
  if (event.newState === 'closed' && document.activeElement === document.body) {
    trigger.value?.focus({ preventScroll: true })
  }
}

function chooseField(next: 'start' | 'end') {
  field.value = next
  cursor.value = (next === 'start' ? start.value : end.value) || cursor.value
}

function selectDay(day: string) {
  cursor.value = day
  if (field.value === 'start') {
    start.value = day
    field.value = 'end'
  } else end.value = day
}

function close() {
  panel.value?.hidePopover()
  trigger.value?.focus({ preventScroll: true })
}

function apply() {
  if (invalid.value) return
  emit('apply', start.value, end.value)
  close()
}
</script>

<template>
  <div class="date-range-picker">
    <button ref="trigger" class="range-trigger" type="button" :popovertarget="id" :aria-label="label"
      :aria-expanded="opened" :class="{ applied: from || to }">
      <AppIcon name="calendar" :size="16" />{{ label }}
      <span v-if="from || to">{{ from || '不限' }} 至 {{ to || '不限' }}</span>
    </button>
    <section :id="id" ref="panel" class="zh-popover range-panel" popover :aria-label="label"
      @beforetoggle="beforeToggle" @toggle="restoreFocus" @keydown.esc.stop.prevent="close">
      <header><strong>{{ label }}</strong><button type="button" aria-label="关闭日期选择" @click="close"><AppIcon name="close" :size="16" /></button></header>
      <div class="presets">
        <button v-for="[key, text] in presets" :key="key" type="button" @click="emit('preset', key); close()">{{ text }}</button>
      </div>
      <div class="bounds">
        <button type="button" :aria-pressed="field === 'start'" @click="chooseField('start')"><small>开始日期</small>{{ dateLabel(start) }}</button>
        <button type="button" :aria-pressed="field === 'end'" @click="chooseField('end')"><small>结束日期</small>{{ dateLabel(end) }}</button>
      </div>
      <NoteCalendar v-if="opened" :selected-day="cursor" :today="today" :counts="{}" item-label="日期" range-picker
        :range-start="start" :range-end="end" @select="selectDay" @today="cursor = today" @navigate="cursor = $event" />
      <p v-if="invalid" role="alert">结束日期早于开始日期，请重新选择。</p>
      <footer>
        <button type="button" :disabled="!start && !end" @click="start = ''; end = ''; field = 'start'">清空暂选</button>
        <button type="button" @click="close">取消</button>
        <button type="button" class="apply" :disabled="invalid" @click="apply">应用日期</button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.range-trigger,.range-panel button { font: inherit; cursor: pointer; }
.range-trigger { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px; min-height: var(--zh-control-height); padding: 4px 10px; border: 1px solid var(--zh-border); border-radius: var(--zh-radius-sm); background: var(--zh-panel); color: var(--zh-ink); font-size: 13px; }
.range-trigger.applied,.range-trigger:hover { color: var(--zh-accent); background: var(--zh-field); }
.range-trigger span { font-size: 12px; font-variant-numeric: tabular-nums; }
.range-panel { width: min(358px,calc(100vw - 24px)); padding: 16px; overscroll-behavior: contain; }
.range-panel header,.range-panel footer,.presets { display:flex; align-items:center; gap:6px; }
.range-panel header { justify-content:space-between; margin-bottom:8px; font-size:16px; }
.range-panel button { border:0; border-radius:var(--zh-radius-sm); min-height:34px; padding:4px 8px; background:transparent; color:var(--zh-ink); }
.range-panel button:hover { background:var(--zh-field); }
.presets { flex-wrap:wrap; gap:4px; margin-bottom:12px; }
.presets button { font-size:13px; background:var(--zh-field); }
.bounds { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.bounds button { display:grid; gap:4px; text-align:start; padding:7px 10px; border:1px solid var(--zh-border); font-size:14px; font-variant-numeric:tabular-nums; }
.bounds small { font-size:12px; color:var(--zh-muted); }
.bounds [aria-pressed=true] { border-color:var(--zh-accent); background:var(--zh-selected); }
.range-panel :deep(.calendar) { padding:12px 0; margin:0; border:0; background:transparent; width:100%; max-height:none; overflow:visible; }
.range-panel :deep(.calendar-grid) {gap:3px}
.range-panel :deep(.calendar .calendar-toolbar button),
.range-panel :deep(.calendar-month-menu summary) { color:var(--zh-ink); background:var(--zh-field); }
.range-panel :deep(.calendar .calendar-toolbar button:hover) { background:var(--zh-selected); }
.range-panel :deep(.calendar .calendar-weekday) { color:var(--zh-muted); }
.range-panel :deep(.calendar-day) { min-height:34px; aspect-ratio:auto; padding:0; background:var(--zh-panel); color:var(--zh-ink); }
.range-panel :deep(.calendar-day:hover),.range-panel :deep(.in-range) { background:var(--zh-field); }
.range-panel :deep(.calendar-day.calendar-selected) { background:var(--zh-selected); color:var(--zh-accent); border-color:var(--zh-accent); }
.range-panel :deep(.is-today) { text-decoration:underline; text-underline-offset:3px; }
.range-panel footer { border-top:1px solid var(--zh-border); padding-top:10px; }
.range-panel footer button:first-child { margin-right:auto; color:var(--zh-muted); }
.range-panel .apply { background:var(--zh-accent); color:white; }
.range-panel button:disabled { opacity:.5; cursor:not-allowed; }
.range-panel p { color:#94372e; font-size:13px; margin-bottom:8px; }
@media(max-width:600px){ .range-panel { position-area:none; inset: auto 0 max(12px,env(safe-area-inset-bottom)); margin:auto; max-height:calc(100dvh - 24px); } }
</style>
