<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
const props = defineProps<{ disabled: boolean }>()
interface Template { id?: number, name: string, title: string, category: string, content: string }
const custom = ref<Template[]>([])
const query = ref('')
const importPreview = ref<Template[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const matches = (item: Template) => (item.name + ' ' + item.title + ' ' + item.content).toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase())
const matchingCount = computed(() => templates.value.filter(matches).length)
const importCounts = computed(() => {
  const names = new Set(custom.value.map(item => item.name))
  let skipped = 0
  for (const item of importPreview.value) { if (names.has(item.name)) skipped++; else names.add(item.name) }
  return { imported: importPreview.value.length - skipped, skipped }
})
async function exportTemplates() {
  if (busy.value || props.disabled) return
  busy.value = true
  try {
    await load()
    if (!custom.value.length) { notice.value = '还没有自建模板可导出。'; return }
    const payload = { format: 'zhiji-templates', version: 1, templates: custom.value.map(({ name, title, content }) => ({ name, title, content })) }
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url; link.download = '知己-我的模板.json'
    document.body.appendChild(link); link.click(); link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    notice.value = `已导出 ${custom.value.length} 个自建模板。`
  } catch (error) { notice.value = String(error) } finally { busy.value = false }
}
async function prepareImport(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || busy.value || props.disabled) return
  busy.value = true
  importPreview.value = []
  notice.value = ''
  try {
    if (file.size > 5 * 1024 * 1024) throw new Error('文件不能超过 5 MB。')
    const data = JSON.parse((await file.text()).replace(/^\uFEFF/, ''))
    if (data.format !== 'zhiji-templates' || data.version !== 1 || !Array.isArray(data.templates) || !data.templates.length || data.templates.length > 100) throw new Error('请选择知己导出的模板文件，每次支持 1–100 个模板。')
    const items = data.templates.map((item: Record<string, unknown>) => {
      if (!item || typeof item.name !== 'string' || !item.name.trim() || item.name.length > 50 || typeof item.title !== 'string' || item.title.length > 200 || typeof item.content !== 'string' || !item.content.trim() || item.content.length > 10000) throw new Error('文件中有无效模板，本次未导入任何内容。')
      return { name: item.name.trim(), title: item.title, content: item.content, category: '待整理' }
    })
    await load()
    importPreview.value = items
  } catch (error) { notice.value = String(error) } finally { busy.value = false }
}
async function confirmImport() {
  if (busy.value || props.disabled || !importPreview.value.length) return
  busy.value = true
  try {
    const response = await fetch('/api/templates/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ templates: importPreview.value }) })
    if (!response.ok) throw new Error('导入失败，请确认登录状态后重试。')
    const result = await response.json()
    importPreview.value = []
    notice.value = `已导入 ${result.imported} 个，跳过同名 ${result.skipped} 个。已有模板未被覆盖。`
    await load()
  } catch (error) { notice.value = String(error) } finally { busy.value = false }
}

const editor = ref<Template | null>(null)
const panel = ref<HTMLDetailsElement | null>(null)
const nameInput = ref<HTMLInputElement | null>(null)
const originalEditor = ref('')
async function beginTemplate(source?: { title: string, content: string, name?: string }) {
  if (busy.value || props.disabled) return false
  if (editor.value && JSON.stringify(editor.value) !== originalEditor.value && !window.confirm('放弃尚未保存的模板修改？')) return false
  editor.value = { name: source?.name || '', title: source?.title || '', category: '待整理', content: source?.content || '' }
  originalEditor.value = JSON.stringify(editor.value)
  notice.value = ''
  if (panel.value) panel.value.open = true
  await nextTick()
  nameInput.value?.focus()
  return true
}
function copyTemplate() {
  const item = templates.value[selected.value]
  if (item) void beginTemplate({ ...item, name: item.name + '（副本）' })
}
function collapse() {
  if (panel.value) panel.value.open = false
}
defineExpose({ beginTemplate, collapse })
function newTemplate() { void beginTemplate() }
function editTemplate() { const item = templates.value[selected.value]; if (item?.id) { editor.value = { ...item }; originalEditor.value = JSON.stringify(editor.value) } }
function cancelEditor() {
  if (busy.value) return
  if (editor.value && JSON.stringify(editor.value) !== originalEditor.value && !window.confirm('放弃尚未保存的模板修改？')) return
  editor.value = null
}
const busy = ref(false)
const notice = ref('')
const templates = computed<Template[]>(() => [...builtins, ...custom.value])
async function load() {
  const response = await fetch('/api/templates')
  if (!response.ok) throw new Error('无法读取模板，请确认已经登录并重试。')
  custom.value = (await response.json()).templates
}
async function opened(event: Event) {
  if (!(event.target as HTMLDetailsElement).open || busy.value) return
  try { await load() } catch (error) { notice.value = String(error) }
}
async function save() {
  const draft = editor.value
  if (busy.value || props.disabled || !draft?.name.trim() || !draft.content.trim()) return
  busy.value = true
  notice.value = ''
  try {
    const response = await fetch('/api/templates' + (draft.id ? '/' + draft.id : ''), {
      method: draft.id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(draft)
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '保存模板失败。')
    const saved = { ...draft, id: draft.id || result.id, name: draft.name.trim() }
    const index = custom.value.findIndex(item => item.id === saved.id)
    if (index >= 0) custom.value[index] = saved
    else custom.value.push(saved)
    selected.value = templates.value.findIndex(item => item.id === saved.id)
    editor.value = null
    notice.value = '模板已保存，可以直接使用。'
  } catch (error) { notice.value = String(error) } finally { busy.value = false }
}
async function remove() {
  const current = templates.value[selected.value]
  if (!current?.id || busy.value || props.disabled || !window.confirm('删除这个自建模板？笔记和当前草稿不会被删除。')) return
  busy.value = true
  try {
    const response = await fetch('/api/templates/' + current.id, { method: 'DELETE' })
    if (!response.ok) throw new Error('删除失败，请重试。')
    await load()
    selected.value = 0
    notice.value = '模板已删除，笔记和草稿仍然保留。'
  } catch (error) { notice.value = String(error) } finally { busy.value = false }
}
const emit = defineEmits<{ apply: [template: { title: string, category: string, content: string }], editing: [active: boolean], busy: [active: boolean] }>()
watch(editor, value => emit('editing', !!value), { flush: 'sync' })
watch(busy, value => emit('busy', value), { flush: 'sync' })
const selected = ref(0)
const builtins: Template[] = [
  { name: '会议记录', title: '会议记录', category: '工作经验', content: '会议主题：\n时间 / 参与人：\n\n讨论要点\n• \n\n决定与结论\n• \n\n后续行动\n• 事项：\n  负责人：\n  截止日期：' },
  { name: '工作计划', title: '工作计划', category: '工作经验', content: '今天最重要的三件事\n1. \n2. \n3. \n\n时间安排\n• \n\n需要协作 / 等待回复\n• \n\n完成后的回顾\n进展：\n下一步：' },
  { name: '学习笔记', title: '学习笔记', category: '学习心得', content: '学习主题：\n资料来源：\n\n关键知识\n1. \n2. \n3. \n\n用自己的话解释\n\n\n实践与例子\n\n\n还没弄懂的问题\n• ' },
  { name: '灵感收集', title: '一个新想法', category: '个人灵感', content: '我的想法\n\n\n它能解决什么问题\n\n\n可以如何实现\n• \n\n最小的下一步\n• ' },
  { name: '每周回顾', title: '每周回顾', category: '生活记录', content: '这一周的收获\n• \n\n完成了什么\n• \n\n遇到的困难\n• \n\n值得保留的经验\n• \n\n下周的重点\n1. \n2. \n3. ' }
]
function apply() {
  const template = templates.value[selected.value]
  if (!template) return
  emit('apply', template)
}
</script>
<template>
  <details ref="panel" class="capture-templates" :class="{ 'is-editing': editor }" @toggle="opened">
    <summary>从模板开始 <span>会议 · 计划 · 学习 · 灵感 · 回顾</span></summary>
    <div v-if="!editor" class="template-tools">
      <input v-model="query" type="search" aria-label="搜索模板" placeholder="搜索模板名称或内容" @keydown.enter.prevent />
      <button type="button" :disabled="busy || disabled" @click="exportTemplates">导出我的模板</button>
      <button type="button" :disabled="busy || disabled" @click="fileInput?.click()">导入模板</button>
      <input ref="fileInput" type="file" accept=".json,application/json" hidden @change="prepareImport" />
    </div>
    <div v-if="importPreview.length && !editor" class="import-preview">
      <strong>确认导入：新增 {{ importCounts.imported }} 个，同名跳过 {{ importCounts.skipped }} 个</strong>
      <ul><li v-for="(item, index) in importPreview" :key="index">{{ item.name }}</li></ul>
      <button type="button" :disabled="busy || disabled" @click="confirmImport">确认导入</button>
      <button type="button" :disabled="busy" @click="importPreview = []">取消</button>
    </div>
    <p v-if="query && !editor" class="template-help">找到 {{ matchingCount }} 个模板</p>
    <div class="template-options" role="group" aria-label="笔记模板">
      <button v-for="(template, index) in builtins" v-show="matches(template)" :key="template.name" type="button" :disabled="disabled || busy || !!editor"
        :aria-pressed="!editor && selected === index" @click="selected = index">{{ template.name }}</button>
      <button type="button" class="new-template" :disabled="disabled || busy || !!editor" :aria-expanded="!!editor" @click="newTemplate">＋ 新建模板</button>
      <button v-for="(template, index) in custom" v-show="matches(template)" :key="template.id" type="button" :disabled="disabled || busy || !!editor"
        :aria-pressed="!editor && selected === builtins.length + index" @click="selected = builtins.length + index">我的 · {{ template.name }}</button>
    </div>
    <div v-if="editor" class="template-editor" @keydown.enter.stop="($event.target as HTMLElement).tagName !== 'TEXTAREA' && $event.preventDefault()" @keydown.esc.stop.prevent="cancelEditor">
      <h3>{{ editor.id ? '编辑模板' : '新建模板' }}</h3>
      <label>模板名称<input ref="nameInput" v-model="editor.name" maxlength="50" placeholder="例如：客户沟通记录" :disabled="busy || disabled" /></label>
      <label>笔记标题（选填）<input v-model="editor.title" maxlength="200" placeholder="套用后作为笔记标题，可留空" :disabled="busy || disabled" /></label>
      <label>模板内容<textarea v-model="editor.content" rows="7" maxlength="10000" placeholder="直接在这里编写模板，例如：沟通目标、讨论内容、下一步行动…" :disabled="busy || disabled"></textarea></label>
      <div class="template-footer"><span>模板只保存名称、标题和正文。笔记分类在使用时选择。</span>
        <button type="button" :disabled="busy" @click="cancelEditor">返回笔记</button>
        <button type="button" :disabled="busy || disabled || !editor.name.trim() || !editor.content.trim()" @click="save">{{ busy ? '保存中…' : '保存模板' }}</button></div>
    </div>
    <template v-else-if="templates[selected] && matches(templates[selected]!)">
      <pre>{{ templates[selected]?.content }}</pre>
      <div class="template-footer"><span>先填入草稿，修改后再保存。行动条目不会自动生成待办。</span>
        <button type="button" :disabled="disabled || busy" @click="apply">使用这个模板</button></div>
      <div class="template-footer">
        <button type="button" :disabled="disabled || busy" @click="copyTemplate">另存为我的模板</button>
        <span>可基于内置或已有模板修改，原模板保持不变。</span>
      </div>
      <div v-if="templates[selected]?.id" class="template-footer">
        <button type="button" :disabled="disabled || busy" @click="editTemplate">编辑此模板</button>
        <button type="button" :disabled="disabled || busy" @click="remove">删除此模板</button>
      </div>
    </template>
    <p v-if="notice" class="template-help" role="status">{{ notice }}</p>
  </details>
</template>
<style scoped>
.template-tools { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.template-tools input[type="search"] { min-width: 140px; }
.template-tools input[hidden] { display: none; }
.import-preview { padding: 12px; margin-top: 12px; border: 1px solid #e5dfd2; border-radius: 8px; background: #fff; font-size: 12px; }
.import-preview ul { max-height: 140px; overflow: auto; }
.import-preview button { margin-right: 8px; }

.capture-templates.is-editing { border: 0; padding: 0; background: transparent; margin-top: 0; }
.is-editing > summary, .is-editing > .template-options { display: none; }
.template-editor { padding-top: 8px; }
.template-editor > label { margin-top: 8px; }

.template-editor { display: grid; gap: 12px; }
.template-editor h3 { margin: 0; font-size: 15px; }
.template-editor label { display: grid; gap: 5px; font-size: 12px; color: #736044; }
.template-editor input, .template-editor textarea { width: 100%; flex: none; box-sizing: border-box; border: 1px solid #e5dfd2; background: white; color: #403a30; border-radius: 8px; padding: 10px; font: inherit; font-size: 14px; }
.template-editor textarea { resize: vertical; line-height: 1.7; }
.new-template { border-style: dashed; }

.capture-templates { margin: 16px 0; border: 1px solid #e8e5de; border-radius: 11px; padding: 12px; background: #faf9f6; }
input { flex: 1 1 180px; min-width: 0; padding: 9px; border: 1px solid #e5dfd2; border-radius: 7px; font: inherit; }
.template-help { color: #80796e; font-size: 12px; margin-top: 10px; }
summary { cursor: pointer; color: #554b3c; font-size: 13px; }
summary span { margin-left: 8px; color: #80796e; font-size: 12px; }
.template-options { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
button { min-height: 36px; padding: 6px 10px; border: 1px solid #e5dfd2; border-radius: 7px; background: white; color: #736044; cursor: pointer; }
button[aria-pressed="true"] { background: #efe2c8; border-color: #d4bd91; color: #654719; }
button:disabled { opacity: .5; cursor: default; }
pre { max-height: 180px; overflow: auto; margin: 0; padding: 12px; border-radius: 8px; background: white; font: inherit; font-size: 13px; line-height: 1.8; white-space: pre-wrap; color: #676158; }
.template-footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; margin-top: 10px; }
.template-footer span { color: #80796e; font-size: 12px; flex: 1 1 160px; }
@media(max-width: 520px) { summary span { display: block; margin: 4px 0 0; } }
</style>
