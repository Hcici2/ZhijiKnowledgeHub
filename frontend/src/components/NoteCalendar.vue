<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

const props = defineProps<{
  selectedDay: string
  today: string
  counts: Record<string, number>
  counting?: boolean
  error?: boolean
  itemLabel?: string
}>()
const emit = defineEmits<{ select: [day: string], today: [] }>()

const weekdays = ['一', '二', '三', '四', '五', '六', '日']
const year = computed(() => Number(props.selectedDay.slice(0, 4)))
const month = computed(() => Number(props.selectedDay.slice(5, 7)))
const monthLabel = computed(() => year.value + ' 年 ' + month.value + ' 月')
const minYear = 1
const maxYear = 9998
const monthMenu = ref<HTMLDetailsElement | null>(null)
const yearList = ref<HTMLElement | null>(null)
const draftYear = ref(year.value)
const yearChoices = computed(() => {
  const todayYear = Number(props.today.slice(0, 4))
  const start = Math.min(1900, Math.max(minYear, year.value - 15))
  const end = Math.min(maxYear, Math.max(todayYear + 15, year.value + 15))
  return Array.from({ length: end - start + 1 }, (_, index) => end - index)
})

function calendarDate(value: number, monthIndex: number, day: number) {
  const date = new Date(0)
  date.setFullYear(value, monthIndex, day)
  date.setHours(12, 0, 0, 0)
  return date
}

const offset = computed(() => (calendarDate(year.value, month.value - 1, 1).getDay() + 6) % 7)
const lastDay = computed(() => calendarDate(year.value, month.value, 0).getDate())
const cells = computed(() => Array.from({ length: lastDay.value }, (_, index) => {
  const day = index + 1
  return { day, key: props.selectedDay.slice(0, 7) + '-' + String(day).padStart(2, '0') }
}))
const total = computed(() => Object.values(props.counts).reduce((sum, count) => sum + count, 0))

function selectMonth(value: number, selectedMonth: number) {
  if (value < minYear || value > maxYear) return
  if (value === year.value && selectedMonth === month.value) return
  const key = String(value).padStart(4, '0') + '-' + String(selectedMonth).padStart(2, '0') + '-01'
  emit('select', key)
}

function moveMonth(delta: number) {
  const target = calendarDate(year.value, month.value - 1 + delta, 1)
  selectMonth(target.getFullYear(), target.getMonth() + 1)
}

async function onMonthMenuToggle() {
  if (!monthMenu.value?.open) return
  draftYear.value = year.value
  await nextTick()
  const list = yearList.value
  const selected = list?.querySelector<HTMLButtonElement>('[aria-pressed="true"]')
  if (list && selected) {
    list.scrollTop = selected.offsetTop - (list.clientHeight - selected.offsetHeight) / 2
    selected.focus({ preventScroll: true })
  }
}

function closeMonthMenu() {
  if (!monthMenu.value?.open) return
  monthMenu.value.open = false
  monthMenu.value.querySelector('summary')?.focus()
}

function jumpToMonth(selectedMonth: number) {
  if (!Number.isInteger(draftYear.value) || draftYear.value < minYear || draftYear.value > maxYear) return
  selectMonth(draftYear.value, selectedMonth)
  closeMonthMenu()
}
</script>

<template>
  <section class="calendar" :aria-label="(itemLabel || '笔记') + '月历'">
    <div class="calendar-toolbar">
      <div class="calendar-navigation">
        <button type="button" aria-label="上个月" title="上个月" @click="moveMonth(-1)">‹</button>
        <details ref="monthMenu" class="calendar-month-menu"
          @toggle="onMonthMenuToggle" @keydown.esc.stop.prevent="closeMonthMenu">
          <summary :aria-label="monthLabel + '，选择年份和月份'">{{ monthLabel }} <span class="month-chevron" aria-hidden="true"></span></summary>
          <div class="month-picker">
            <div ref="yearList" class="year-options" aria-label="选择年份" role="group">
              <button v-for="item in yearChoices" :key="item" type="button"
                :aria-pressed="item === draftYear" @click="draftYear = item">{{ item }} 年</button>
            </div>
            <div class="month-options" aria-label="选择月份" role="group">
              <button v-for="item in 12" :key="item" type="button"
                :aria-current="draftYear === year && item === month ? 'date' : undefined"
                @click="jumpToMonth(item)">{{ item }} 月</button>
            </div>
          </div>
        </details>
        <button type="button" aria-label="下个月" title="下个月" @click="moveMonth(1)">›</button>
      </div>
      <button type="button" class="calendar-today" @click="emit('today')">今天</button>
    </div>
    <div class="calendar-grid">
      <span v-for="day in weekdays" :key="day" class="calendar-weekday">{{ day }}</span>
      <span v-for="space in offset" :key="'space-' + space" aria-hidden="true"></span>
      <button v-for="cell in cells" :key="cell.key" type="button" class="calendar-day"
        :class="{ 'calendar-selected': cell.key === selectedDay, 'is-today': cell.key === today }"
        :aria-pressed="cell.key === selectedDay"
        :aria-label="cell.key + (counts[cell.key] ? '，' + counts[cell.key] + ' 条' + (itemLabel || '笔记') : '')"
        @click="emit('select', cell.key)">
        <span>{{ cell.day }}</span>
        <small v-if="counts[cell.key]">{{ counts[cell.key] }} 条</small>
      </button>
    </div>
    <p v-if="error" class="calendar-total" role="alert">无法读取本月{{ itemLabel || '笔记' }}数。</p>
    <p v-else class="calendar-total" role="status">{{ counting ? '正在统计…' : '本月 ' + total + ' 条' + (itemLabel || '笔记') }}</p>
  </section>
</template>

<style scoped>
.calendar {
  min-width: 0;
  padding: 14px;
  border: 1px solid #e9dfce;
  border-radius: 15px;
  background: #fffdf8;
  color: #30271d;
}

.calendar-toolbar,
.calendar-navigation {
  display: flex;
  align-items: center;
  gap: 5px;
}

.calendar-toolbar {
  justify-content: space-between;
  margin-bottom: 12px;
}

.calendar-month-menu summary {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 4px;
  color: #30271d;
  font-size: clamp(14px, 2vw, 19px);
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
  list-style: none;
}

.calendar-month-menu summary::-webkit-details-marker {
  display: none;
}

.month-chevron {
  width: 7px;
  height: 7px;
  margin: -3px 1px 0;
  border-right: 2px solid #8b6530;
  border-bottom: 2px solid #8b6530;
  transform: rotate(45deg);
}

.calendar-month-menu[open] .month-chevron {
  margin-top: 3px;
  transform: rotate(225deg);
}

.calendar-toolbar {
  position: relative;
}

.month-picker {
  position: absolute;
  top: calc(100% + 5px);
  left: 0;
  z-index: 3;
  display: grid;
  grid-template-columns: .9fr 1.25fr;
  width: min(270px, 100%);
  padding: 6px;
  border: 1px solid #e9dfce;
  border-radius: 12px;
  background: #fffdf8;
  box-shadow: 0 8px 24px #30271d21;
}

.year-options {
  position: relative;
  max-height: 218px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 3px 5px 3px 1px;
  border-right: 1px solid #eee4d4;
}

.month-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 3px;
  padding: 3px 0 3px 6px;
}

.calendar-toolbar :is(.year-options, .month-options) button {
  min-width: 0;
  padding: 4px 2px;
  background: transparent;
  font-size: 13px;
  white-space: nowrap;
}

.calendar-toolbar .year-options button {
  display: block;
  width: 100%;
  margin-bottom: 2px;
  border-radius: 20px;
}

.calendar-toolbar :is(.year-options, .month-options) button:hover {
  background: #f8edda;
}

.calendar-toolbar .year-options button[aria-pressed="true"] {
  background: #9b640c;
  color: #fff;
}

.calendar-toolbar .month-options button[aria-current] {
  background: #f7e2b6;
  color: #67410a;
}

.calendar-toolbar button {
  min-width: 32px;
  min-height: 32px;
  padding: 2px 6px;
  border: 0;
  border-radius: 8px;
  background: #f5eee2;
  color: #714c1a;
  font: inherit;
  font-weight: 650;
  cursor: pointer;
}

.calendar-navigation button {
  font-size: 21px;
  line-height: 1;
}

.calendar-toolbar button:hover {
  background: #f3e2c1;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: clamp(3px, .6vw, 7px);
}

.calendar-weekday {
  padding-bottom: 7px;
  color: #736858;
  text-align: center;
  font-size: 12px;
}

.calendar-day {
  display: flex;
  min-width: 0;
  min-height: clamp(41px, 5vw, 60px);
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 2px;
  padding: 4px 0;
  border: 1px solid transparent;
  border-radius: 10px;
  background: #f3f0ea;
  color: #30271d;
  font: inherit;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
}

.calendar-day:hover {
  background: #f4e8d2;
}

.calendar-day.is-today {
  border-color: #c28c39;
}

.calendar-day.calendar-selected {
  background: #f7e2b6;
  border-color: #c3944b;
  color: #68450d;
}

.calendar-day small {
  font-size: 10px;
  font-weight: 550;
  color: #795a28;
  white-space: nowrap;
}

.calendar-total {
  margin: 11px 0 0;
  color: #695b48;
  font-size: 12px;
}

@media (max-width: 500px) {
  .calendar { padding: 8px; }
  .calendar-day { border-radius: 6px; font-size: 12px; }
  .calendar-toolbar button { min-width: 25px; font-size: 13px; }
}
</style>
