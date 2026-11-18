import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'
function load(file, props = {}, emit = () => {}) {
  const { descriptor } = parse(fs.readFileSync(new URL(file, import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: 'test', genDefaultAs: 'component' }).content
  const code = ts.transpileModule(script, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  const component = new Function('require', 'exports', code.replace('import.meta.env.DEV', 'true') + '\nreturn component')(
    name => name === 'vue' ? { ...vue, onMounted() {}, onUnmounted() {} } : { default: '' }, {})
  return component.setup(props, { expose() {}, emit })
}


const calls = []
globalThis.fetch = async (url, options) => {
  calls.push({ url, options })
  return { ok: true, status: 200, json: async () => ({ success: true, records: [], total: 0, page: 1, days: {}, content: '' }) }
}
const state = load('../src/App.vue')
state.authState.value = 'ready'
state.activeView.value = 'pinned'
state.activeKeyword.value = '旧关键词'
state.selectedCategory.value = '旧分类'
const record = {
  id: 12, title: '笔记', pinned: false, deletedAt: null,
  noteDate: '2026-10-09', createdDay: '2026-11-18',
}
state.linkedRecord.value = record
await state.togglePin(record)
assert.equal(state.linkedRecord.value.pinned, true)
assert.deepEqual(JSON.parse(calls[0].options.body), { pinned: true })
await state.viewNoteDay(record)
assert.equal(state.activeView.value, 'library')
assert.equal(state.libraryMode.value, 'calendar')
assert.equal(state.selectedDay.value, '2026-10-09')
const search = calls.findLast(call => call.url.startsWith('/api/records/search?'))
const params = new URLSearchParams(search.url.split('?')[1])
assert.equal(params.get('date_from'), '2026-10-09')
assert.equal(params.get('date_to'), '2026-10-09')
assert.equal(params.has('q'), false)
assert.equal(params.has('category'), false)
await state.viewNoteDay({ ...record, noteDate: null })
assert.equal(state.selectedDay.value, '2026-11-18')
await state.openView('library', { category: '工作经验' })
assert.equal(state.libraryMode.value, 'list')
let filter = new URLSearchParams(calls.findLast(call => call.url.startsWith('/api/records/search?')).url.split('?')[1])
assert.equal(filter.get('category'), '工作经验')
assert.equal(filter.has('date_from'), false)
await state.openView('library', { tag: '跟进' })
filter = new URLSearchParams(calls.findLast(call => call.url.startsWith('/api/records/search?')).url.split('?')[1])
assert.equal(filter.get('tag'), '跟进')
assert.equal(filter.has('category'), false)
assert.deepEqual(state.activeLibraryFilters.value, ['标签：跟进'])
state.activeKeyword.value = '关键词测试'
state.appliedDateFrom.value = '2026-11-01'
await state.clearLibraryFilters()
filter = new URLSearchParams(calls.findLast(call => call.url.startsWith('/api/records/search?')).url.split('?')[1])
assert.equal(filter.has('tag'), false)
assert.equal(filter.has('q'), false)
assert.equal(filter.has('date_from'), false)
assert.deepEqual(state.activeLibraryFilters.value, [])
await state.viewNoteDay(record)
state.selectedTag.value = '跟进'
await state.clearLibraryFilters()
assert.equal(state.selectedDay.value, '2026-10-09')
assert.equal(state.libraryMode.value, 'calendar')
console.log('PASS: pin updates open detail and date, category and tag open the correct library view')
