<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  task: { title: string, due_date: string | null, due_time: string | null, priority: number }
  busy: boolean
  error: string
}>()
const emit = defineEmits<{
  save: [details: { title: string, due_date: string | null, due_time: string | null, priority: number }]
  cancel: []
}>()
const title = ref(props.task.title)
const day = ref(props.task.due_date ?? '')
const time = ref(props.task.due_time ?? '')
const priority = ref(props.task.priority)
function setDay(offset: number) {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  day.value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
function save() {
  if (!title.value.trim() || props.busy) return
  emit('save', { title: title.value.trim(), due_date: day.value || null, due_time: day.value ? time.value || null : null, priority: priority.value })
}
</script>

<template>
  <form class="task-editor" @submit.prevent="save">
    <label class="task-editor-title">待办内容<input v-model="title" required maxlength="200" :disabled="busy" /></label>
    <div class="task-editor-fields">
      <label>截止日期<input v-model="day" type="date" :disabled="busy" @change="!day && (time = '')" /></label>
      <label>具体时间<input v-model="time" type="time" :disabled="busy || !day" /></label>
      <label>优先级<select v-model.number="priority" :disabled="busy"><option :value="0">普通</option><option :value="1">重要</option><option :value="2">紧急</option></select></label>
    </div>
    <div class="task-editor-actions">
      <button type="button" :disabled="busy" @click="setDay(0)">今天</button>
      <button type="button" :disabled="busy" @click="setDay(1)">明天</button>
      <button type="button" :disabled="busy" @click="day = ''; time = ''">不设日期</button>
      <span class="task-editor-spacer"></span>
      <button type="button" :disabled="busy" @click="emit('cancel')">取消</button>
      <button class="task-editor-save" :disabled="busy || !title.trim()">{{ busy ? '保存中…' : '保存修改' }}</button>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
  </form>
</template>

<style scoped>
.task-editor { flex-basis: 100%; min-width: 0; padding: 16px; background: #faf7f1; border: 1px solid #e8dfcf; border-radius: 12px; }
.task-editor label { display: grid; gap: 6px; color: #766c5f; font-size: 12px; }
.task-editor input, .task-editor select { box-sizing: border-box; width: 100%; min-width: 0; padding: 10px; border: 1px solid #e5dccd; border-radius: 8px; background: white; color: #302d28; font: inherit; font-size: 14px; }
.task-editor-fields { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 12px 0; }
.task-editor-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.task-editor-spacer { flex: 1; }
.task-editor button { padding: 8px 10px; border: 1px solid #e5dccd; border-radius: 8px; background: white; color: #675640; cursor: pointer; }
.task-editor button.task-editor-save { background: #98630e; color: white; border-color: #98630e; }
.task-editor button:disabled { opacity: .5; cursor: default; }
.task-editor p { color: #a23831; font-size: 13px; }
@media (max-width: 520px) { .task-editor-fields { grid-template-columns: 1fr; } }
</style>
