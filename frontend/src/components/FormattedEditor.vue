<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps<{ disabled: boolean, label: string }>()
const emit = defineEmits<{ shortcut: [event: KeyboardEvent], resizeWidth: [width: number] }>()
const model = defineModel<string>({ required: true })
const host = ref<HTMLElement | null>(null)
const editorHeight = ref<number>()
let resizeOrigin: { x: number, y: number, width: number, height: number } | undefined
function startResize(event: PointerEvent) {
  const bounds = host.value?.getBoundingClientRect()
  const surface = host.value?.closest('.split-note-reader, dialog')
  if (!bounds || !surface || event.button !== 0) return
  resizeOrigin = { x: event.clientX, y: event.clientY, width: surface.getBoundingClientRect().width, height: bounds.height }
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}
function resizeEditor(event: PointerEvent) {
  if (!resizeOrigin) return
  const viewportWidth = document.documentElement.clientWidth
  emit('resizeWidth', Math.min(viewportWidth - 24, Math.max(360, resizeOrigin.width + event.clientX - resizeOrigin.x)))
  editorHeight.value = Math.max(150, resizeOrigin.height + event.clientY - resizeOrigin.y)
}
function endResize() { resizeOrigin = undefined }
const active = ref(0)
const error = ref('')
const past = ref<string[]>([])
const future = ref<string[]>([])
let expected: string | undefined
watch(model, value => {
  if (value !== expected) {
    past.value = []
    future.value = []
  }
  expected = undefined
})
function write(value: string) {
  expected = value
  model.value = value
}
async function replay(redo = false) {
  const source = redo ? future.value : past.value
  const target = redo ? past.value : future.value
  const value = source.pop()
  if (value === undefined) return
  target.push(model.value)
  write(value)
  error.value = ''
  await nextTick()
  focusLine(Math.min(active.value, lines.value.length - 1))
}
const lines = computed(() => model.value.split('\n').map(line => {
  const prefix = /^(?:#{1,6} |[0-9]{1,9}\. |> |[-*] \[[ xX]\] |[-*] )/.exec(line)?.[0] ?? ''
  return { prefix, text: line.slice(prefix.length) }
}))

function isNumbered(prefix: string) { return /^\d+\./.test(prefix) }
function sameFormat(left: string, right: string) {
  return left === right || (isNumbered(left) && isNumbered(right))
}
function marker(prefix: string) {
  if (!prefix || prefix.startsWith('#') || prefix === '> ') return undefined
  if (isNumbered(prefix)) return prefix.trim()
  if (prefix.includes('[')) return prefix.includes('[ ]') ? '☐' : '☑'
  return '•'
}
const replaceOpen = ref(false)
const findText = ref('')
const replacementText = ref('')
const replaceNotice = ref('')
const findInput = ref<HTMLInputElement | null>(null)
const matchCount = computed(() => {
  if (!findText.value) return 0
  return lines.value.reduce((count, row) => count + row.text.split(findText.value).length - 1, 0)
})
async function showReplace() {
  replaceOpen.value = !replaceOpen.value
  replaceNotice.value = ''
  await nextTick()
  if (replaceOpen.value) findInput.value?.focus()
  else focus()
}
function replaceAll() {
  const count = matchCount.value
  if (!count) return
  const rows = lines.value.map(row => row.prefix + row.text.replaceAll(findText.value, () => replacementText.value))
  if (update(0, lines.value.length, rows)) replaceNotice.value = '已替换 ' + count + ' 处。'
  else replaceNotice.value = ''
}
function field(index: number) {
  return host.value?.querySelector<HTMLElement>('[data-line="' + index + '"]')
}
function caret(element: HTMLElement) {
  const selection = window.getSelection()
  if (!selection?.rangeCount || !element.contains(selection.anchorNode) || !element.contains(selection.focusNode)) {
    return [element.textContent?.length ?? 0, element.textContent?.length ?? 0] as const
  }
  const range = selection.getRangeAt(0)
  const offset = (node: Node, index: number) => {
    const start = document.createRange()
    start.selectNodeContents(element)
    start.setEnd(node, index)
    return start.toString().length
  }
  return [offset(range.startContainer, range.startOffset), offset(range.endContainer, range.endOffset)] as const
}
function selectedRows() {
  const selection = window.getSelection()
  if (!selection?.rangeCount || selection.isCollapsed) return
  const range = selection.getRangeAt(0)
  const point = (node: Node, offset: number) => {
    const element = (node instanceof HTMLElement ? node : node.parentElement)?.closest<HTMLElement>('[data-line]')
    if (!element || !host.value?.contains(element)) return
    const prefix = document.createRange()
    prefix.selectNodeContents(element)
    prefix.setEnd(node, offset)
    return { index: Number(element.dataset.line), offset: prefix.toString().length }
  }
  const from = point(range.startContainer, range.startOffset)
  const to = point(range.endContainer, range.endOffset)
  if (from && to) return { from, to }
}
function selectRows(first: number, last: number, start = 0, end?: number) {
  const left = field(first)
  const right = field(last)
  if (!left || !right) return
  const range = document.createRange()
  range.setStart(left.firstChild ?? left, left.firstChild ? start : 0)
  range.setEnd(right.firstChild ?? right, right.firstChild ? end ?? right.textContent!.length : 0)
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(range)
}
function focusLine(index: number, offset?: number) {
  const element = field(index)
  if (!element) return
  if (document.activeElement !== host.value) host.value?.focus({ preventScroll: true })
  active.value = index
  const selection = window.getSelection()
  const range = document.createRange()
  if (element.firstChild?.nodeType === Node.TEXT_NODE && offset !== undefined) {
    range.setStart(element.firstChild, Math.min(offset, element.firstChild.textContent?.length ?? 0))
  } else {
    range.selectNodeContents(element)
    range.collapse(false)
  }
  selection?.removeAllRanges()
  selection?.addRange(range)
  const editor = host.value
  const caretBounds = range.getBoundingClientRect()
  const bounds = editor?.getBoundingClientRect()
  if (editor && bounds && caretBounds.height) {
    if (caretBounds.bottom > bounds.bottom - 12) editor.scrollTop += caretBounds.bottom - bounds.bottom + 24
    else if (caretBounds.top < bounds.top + 8) editor.scrollTop -= bounds.top + 12 - caretBounds.top
  }
}
function focus() { focusLine(active.value); if (!field(active.value)) focusLine(0) }

async function focusBelow(event: MouseEvent) {
  if (props.disabled || event.target !== host.value || window.getSelection()?.isCollapsed === false) return
  const last = lines.value.length - 1
  const row = field(last)
  const bounds = row?.getBoundingClientRect()
  const editorBounds = host.value?.getBoundingClientRect()
  if (!bounds || !editorBounds || event.clientY < bounds.bottom) return
  if (event.clientX > editorBounds.right - 18 && event.clientY > editorBounds.bottom - 18) return
  const lineHeight = parseFloat(getComputedStyle(host.value!).lineHeight) || 24
  const blankLines = 1 + Math.floor((event.clientY - bounds.bottom) / lineHeight)
  if (update(last + 1, 0, Array<string>(blankLines).fill(''))) {
    await nextTick()
    focusLine(last + blankLines, 0)
  }
}

function update(index: number, count: number, replacement: string[]) {
  const source = model.value.split('\n')
  source.splice(index, count, ...replacement)
  const next = source.join('\n')
  if (next.length > 10000) { error.value = '正文最多 10000 字符。'; return false }
  error.value = ''
  if (next !== model.value) {
    past.value.push(model.value)
    if (past.value.length > 100) past.value.shift()
    future.value = []
    write(next)
  }
  return true
}
async function format(prefix: string) {
  const selection = selectedRows()
  if (selection && selection.from.index !== selection.to.index) {
    const { from, to } = selection
    const last = to.offset === 0 ? to.index - 1 : to.index
    const rows = lines.value.slice(from.index, last + 1)
    const applied = rows.every(row => sameFormat(row.prefix, prefix)) ? '' : prefix
    if (update(from.index, rows.length, rows.map((row, index) => (isNumbered(applied) ? (index + 1) + '. ' : applied) + row.text))) {
      await nextTick()
      selectRows(from.index, to.index, from.offset, to.offset)
    }
    return
  }
  const index = Math.min(active.value, lines.value.length - 1)
  const line = lines.value[index]!
  const element = field(index)
  const offset = element ? caret(element)[1] : line.text.length
  if (update(index, 1, [(sameFormat(line.prefix, prefix) ? '' : prefix) + line.text])) {
    await nextTick()
    focusLine(index, offset)
  }
}
async function insertText(index: number, element: HTMLElement, text: string) {
  const selection = selectedRows()
  if (selection && selection.from.index !== selection.to.index) {
    const { from, to } = selection
    const first = lines.value[from.index]!
    const last = lines.value[to.index]!
    const pieces = text.replace(/\r\n?/g, '\n').split('\n')
    const left = first.text.slice(0, from.offset)
    const right = last.text.slice(to.offset)
    const tail = pieces.length - 1
    const replacement = pieces.map((piece, i) => (i === 0 ? first.prefix + left : '') + piece + (i === tail ? right : ''))
    if (update(from.index, to.index - from.index + 1, replacement)) {
      await nextTick()
      focusLine(from.index + tail, pieces[tail]!.length + (tail === 0 ? left.length : 0))
    }
    return
  }
  const line = lines.value[index]!
  const [start, end] = caret(element)
  const input = text.replace(/\r\n?/g, '\n').split('\n')
  const last = input.length - 1
  const offset = input[last]!.length + (last === 0 ? start : 0)
  const continuation = line.prefix.startsWith('#') ? '' : line.prefix.includes('[') ? '- [ ] ' : line.prefix
  const replacement = input.map((part, i) => {
    const prefix = i === 0 ? line.prefix + line.text.slice(0, start) : isNumbered(continuation) ? Math.min(999999999, Number.parseInt(continuation, 10) + i) + '. ' : continuation
    return prefix + part + (i === last ? line.text.slice(end) : '')
  })
  if (update(index, 1, replacement)) { await nextTick(); focusLine(index + last, offset) }
}
async function syncLine(event: Event, index: number, element: HTMLElement) {
  if ((event as InputEvent).isComposing) return
  const text = element.textContent ?? ''
  const line = lines.value[index]!
  if (text === line.text) return
  const offset = caret(element)[1]
  const accepted = update(index, 1, [line.prefix + text])
  if (!accepted) element.textContent = line.text
  await nextTick()
  if (document.activeElement === host.value) focusLine(index, offset)
}
function copyRows(event: ClipboardEvent, index: number, element: HTMLElement, cut = false) {
  const selection = selectedRows()
  if (!selection || selection.from.index === selection.to.index || !event.clipboardData) return
  const { from, to } = selection
  const text = lines.value.slice(from.index, to.index + 1).map((row, i) =>
    row.text.slice(i === 0 ? from.offset : 0, i === to.index - from.index ? to.offset : undefined)
  ).join('\n')
  event.clipboardData.setData('text/plain', text)
  event.preventDefault()
  if (cut) void insertText(index, element, '')
}
function beforeTyping(event: InputEvent, index: number, element: HTMLElement) {
  if (event.isComposing || !event.cancelable) return
  if (event.inputType === 'insertText' && event.data !== null) {
    event.preventDefault()
    void insertText(index, element, event.data)
  }
}
async function keys(event: KeyboardEvent, index: number, element: HTMLElement) {
  if (event.isComposing) return
  const key = event.key.toLowerCase()
  if ((event.ctrlKey || event.metaKey) && !event.altKey && (key === 'z' || key === 'y')) {
    event.preventDefault()
    await replay(key === 'y' || event.shiftKey)
    return
  }
  if ((event.ctrlKey || event.metaKey) && key === 'a') {
    event.preventDefault()
    selectRows(0, lines.value.length - 1)
    return
  }
  const selection = selectedRows()
  if ((key === 'backspace' || key === 'delete') && selection && selection.from.index !== selection.to.index) {
    event.preventDefault()
    await insertText(index, element, '')
    return
  }
  if (event.key === 'Enter') {
    event.preventDefault()
    if (event.ctrlKey || event.metaKey) emit('shortcut', event)
    else if (!lines.value[index]?.text && lines.value[index]?.prefix) await format(lines.value[index]!.prefix)
    else await insertText(index, element, '\n')
  }
  if (event.key === 'Delete' && index < lines.value.length - 1 &&
      caret(element).every(offset => offset === lines.value[index]!.text.length)) {
    event.preventDefault()
    const line = lines.value[index]!
    if (update(index, 2, [line.prefix + line.text + lines.value[index + 1]!.text])) {
      await nextTick()
      focusLine(index, line.text.length)
    }
    return
  }
  if (event.key === 'Backspace' && caret(element).every(offset => offset === 0)) {
    const line = lines.value[index]!
    if (line.prefix) {
      event.preventDefault()
      if (update(index, 1, [line.text])) {
        await nextTick()
        focusLine(index, 0)
      }
      return
    }
    if (index === 0) return
    event.preventDefault()
    const previous = lines.value[index - 1]!
    if (update(index - 1, 2, [previous.prefix + previous.text + lines.value[index]!.text])) {
      await nextTick()
      focusLine(index - 1, previous.text.length)
    }
  }
}
function withActiveLine(action: (index: number, element: HTMLElement) => void) {
  const node = window.getSelection()?.anchorNode
  const row = (node instanceof HTMLElement ? node : node?.parentElement)?.closest<HTMLElement>('[data-line]')
  const index = row && host.value?.contains(row) ? Number(row.dataset.line) : active.value
  const element = field(index)
  if (!element) return
  active.value = index
  action(index, element)
}
async function appendOutline(text: string) {
  if (props.disabled) return false
  const current = model.value.split('\n')
  const outline = text.split('\n')
  const hasContent = Boolean(model.value.trim())
  const start = hasContent ? current.length : 0
  const rows = hasContent && current.at(-1)?.trim() ? ['', ...outline] : outline
  if (!update(start, hasContent ? 0 : current.length, rows)) return false
  await nextTick()
  focusLine(start + rows.length - 1, 0)
  return true
}
defineExpose({ focus, format, replay, showReplace, appendOutline, canUndo: computed(() => past.value.length > 0), canRedo: computed(() => future.value.length > 0) })
</script>

<template>
  <div class="formatted-editor-frame">
  <div ref="host" class="formatted-editor" :style="editorHeight ? { height: editorHeight + 'px' } : undefined" :aria-label="label" role="textbox" aria-multiline="true"
    :contenteditable="disabled ? 'false' : 'plaintext-only'"
    @click="focusBelow"
    @mouseup="withActiveLine(() => {})"
    @beforeinput="withActiveLine((index, element) => beforeTyping($event, index, element))"
    @input="withActiveLine((index, element) => syncLine($event, index, element))"
    @compositionend="withActiveLine((index, element) => syncLine($event, index, element))"
    @keydown="withActiveLine((index, element) => keys($event, index, element))"
    @copy="withActiveLine((index, element) => copyRows($event, index, element))"
    @cut="withActiveLine((index, element) => copyRows($event, index, element, !disabled))"
    @paste.prevent="withActiveLine((index, element) => insertText(index, element, $event.clipboardData?.getData('text/plain') ?? ''))">
    <div v-for="(line, index) in lines" :key="index" :data-line="index" class="formatted-row"
      :class="{ 'heading-one': line.prefix === '# ', 'heading-two': line.prefix.startsWith('##'), 'quote-row': line.prefix === '> ' }"
      :data-marker="marker(line.prefix)" v-text="line.text"></div>
  </div>
  <span class="editor-resizer" title="拖动调整正文宽度和高度" aria-hidden="true" @pointerdown.prevent="startResize"
    @pointermove="resizeEditor" @pointerup="endResize" @lostpointercapture="endResize"></span>
  </div>
  <div v-if="replaceOpen" class="replace-panel" role="group" aria-label="查找替换" @keydown.esc.stop.prevent="showReplace">
    <label>查找<input ref="findInput" v-model="findText" :disabled="disabled" maxlength="10000" @input="replaceNotice = ''" @keydown.enter.prevent /></label>
    <label>替换为<input v-model="replacementText" :disabled="disabled" maxlength="10000" @keydown.enter.prevent /></label>
    <button type="button" :disabled="disabled || !matchCount" @click="replaceAll">全部替换</button>
    <button type="button" @click="showReplace">关闭</button>
    <span role="status">{{ replaceNotice || (findText ? '找到 ' + matchCount + ' 处' : '') }}</span>
  </div>
  <p v-if="error" class="formatted-error" role="status">{{ error }}</p>
</template>

<style scoped>
.formatted-editor-frame { position: relative; width: 100%; max-width: 100%; margin-top: 8px; }
.formatted-editor { box-sizing: border-box; height: clamp(170px, 43dvh, 350px); max-height: max(150px, 68dvh); overflow: auto; overscroll-behavior: contain; scrollbar-gutter: stable; line-height: 24px; padding: 12px 12px 48px; border: 1px solid #e8e5de; border-radius: 9px; background: #faf9f6; }
.formatted-editor:focus-visible { outline: none; }
.editor-resizer { position: absolute; right: 0; bottom: 0; width: 24px; height: 24px; cursor: nwse-resize; touch-action: none; }
.editor-resizer::after { content: ''; position: absolute; right: 6px; bottom: 6px; width: 10px; height: 10px; background: repeating-linear-gradient(135deg, transparent 0 3px, #aaa092 3px 4px); clip-path: polygon(100% 0, 100% 100%, 0 100%); }
.formatted-editor:focus-within { transition: border-color 140ms ease; }
.formatted-editor:focus-within { border-color: #a56d19; }
.formatted-row { position: relative; min-height: 1.65em; white-space: pre-wrap; overflow-wrap: anywhere; color: #45413b; line-height: 1.65; }
.heading-one { font-size: 25px; font-weight: 700; }
.heading-two { font-size: 19px; font-weight: 650; }
.formatted-row[data-marker] { padding-inline-start: 24px; }
.formatted-row[data-marker]::before { position: absolute; inset-inline-start: 0; content: attr(data-marker); color: #846236; user-select: none; }
.formatted-error { color: #a23831; font-size: 12px; }
.quote-row { border-inline-start: 3px solid #c8b48d; padding-inline-start: 10px; color: #6e5d44; }
.replace-panel { display: flex; flex-wrap: wrap; align-items: end; gap: 8px; margin-top: 10px; padding: 10px; background: #f5f2eb; border-radius: 8px; }
.replace-panel label { display: grid; gap: 3px; flex: 1 1 120px; min-width: 0; font-size: 12px; }
.replace-panel input { min-width: 0; padding: 7px; border: 1px solid #ded8cb; border-radius: 6px; }
.replace-panel button { padding: 7px 10px; border: 1px solid #e5dfd2; border-radius: 6px; background: white; color: #736044; }
.replace-panel span { font-size: 12px; width: 100%; }
.replace-panel span:empty { display: none; }
</style>
