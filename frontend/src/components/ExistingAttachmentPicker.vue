<script setup lang="ts">
import { computed, ref } from 'vue'

type AttachmentChoice = { id: string; name: string; size: number }
const props = defineProps<{
  load: () => Promise<AttachmentChoice[]>
  excluded: readonly string[]
  disabled: boolean
}>()
const emit = defineEmits<{ pick: [files: AttachmentChoice[]] }>()

const panel = ref<HTMLDetailsElement | null>(null)
const files = ref<AttachmentChoice[]>([])
const selected = ref<string[]>([])
const query = ref('')
const loading = ref(false)
const error = ref('')
const visible = computed(() => files.value.filter(file =>
  !props.excluded.includes(file.id) && file.name.toLowerCase().includes(query.value.trim().toLowerCase())
))
const picked = computed(() => files.value.filter(file =>
  selected.value.includes(file.id) && !props.excluded.includes(file.id)
))

async function loadChoices() {
  if (loading.value || props.disabled) return
  loading.value = true
  error.value = ''
  try {
    files.value = await props.load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法读取附件库。'
  } finally {
    loading.value = false
  }
}

function onToggle() {
  if (!panel.value?.open) return
  selected.value = []
  query.value = ''
  void loadChoices()
}

function apply() {
  if (props.disabled || loading.value || error.value || !picked.value.length) return
  emit('pick', picked.value)
  if (panel.value) panel.value.open = false
}
</script>

<template>
  <details ref="panel" class="existing-attachment-picker" @toggle="onToggle">
    <summary>从附件库选择</summary>
    <div class="picker-body">
      <p v-if="loading" role="status">正在读取附件…</p>
      <template v-else-if="error">
        <p role="alert">{{ error }}</p>
        <button type="button" :disabled="disabled" @click="loadChoices">重试</button>
      </template>
      <template v-else>
        <input v-model="query" type="search" aria-label="搜索未关联附件" placeholder="搜索未关联附件" />
        <ul v-if="visible.length">
          <li v-for="file in visible" :key="file.id">
            <label><input v-model="selected" type="checkbox" :disabled="disabled" :value="file.id" />{{ file.name }}</label>
          </li>
        </ul>
        <p v-else>{{ query.trim() ? '没有匹配的附件。' : '没有可选的未关联附件。' }}</p>
        <button type="button" :disabled="disabled || !picked.length" @click="apply">添加所选附件{{ picked.length ? '（' + picked.length + '）' : '' }}</button>
      </template>
    </div>
  </details>
</template>

<style scoped>
.existing-attachment-picker { width: 100%; font-size: 13px; }
summary { width: fit-content; cursor: pointer; padding: 6px 0; }
.picker-body { padding: 8px; border: 1px solid var(--note-border); border-radius: 8px; }
.picker-body input[type="search"] { width: 100%; }
ul { max-height: min(16dvh, 145px); overflow: auto; list-style: none; padding: 0; margin: 6px 0; }
li label { display: flex; align-items: baseline; gap: 8px; padding: 4px; overflow-wrap: anywhere; }
p { margin: 6px 0; }
</style>
