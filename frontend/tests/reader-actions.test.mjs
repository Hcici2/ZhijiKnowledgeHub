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
await state.openSavedSearchForm()
assert.equal(state.savedSearchName.value, '2026-10-09')
assert.ok(state.savedSearchPreview.value.includes('日期：2026-10-09'))
state.activeKeyword.value = '交付'
state.selectedTag.value = '跟进'
await state.openSavedSearchForm()
assert.equal(state.savedSearchName.value, '交付 · 跟进')
assert.ok(state.savedSearchPreview.value.includes('关键词：交付'))
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
assert.deepEqual(state.activeLibraryFilters.value, [{ key: 'tag', label: '标签：跟进' }])
state.activeKeyword.value = '关键词测试'
state.appliedDateFrom.value = '2026-11-01'
state.selectedCategory.value = '工作经验'
await state.removeLibraryFilter('keyword')
filter = new URLSearchParams(calls.findLast(call => call.url.startsWith('/api/records/search?')).url.split('?')[1])
assert.equal(filter.has('q'), false)
assert.equal(filter.get('tag'), '跟进')
assert.equal(filter.get('category'), '工作经验')
assert.equal(filter.get('date_from'), '2026-11-01')
await state.removeLibraryFilter('date')
assert.equal(state.appliedDateFrom.value, '')
assert.equal(state.selectedTag.value, '跟进')
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
state.savedSearches.value = [1, 2, 3, 4].map(id => ({ id, name: '筛选 ' + id, view: 'library', category: '工作经验', keyword: '', tag: '跟进' }))
const storage = new Map()
globalThis.localStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) }
assert.deepEqual(state.quickSavedSearches.value.map(search => search.id), [4, 3, 2])
await state.applySavedSearch(1)
assert.equal(state.savedSearchId.value, 1)
assert.deepEqual(state.quickSavedSearches.value.map(search => search.id), [1, 4, 3])
assert.equal(state.selectedTag.value, '跟进')
assert.equal(state.selectedCategory.value, '工作经验')
assert.equal(state.libraryMode.value, 'list')
await state.applySavedSearch(2)
assert.deepEqual(state.quickSavedSearches.value.map(search => search.id), [2, 1, 4])
const reloaded = load('../src/App.vue')
reloaded.savedSearches.value = [...state.savedSearches.value]
assert.deepEqual(reloaded.quickSavedSearches.value.map(search => search.id), [2, 1, 4])
reloaded.savedSearches.value = reloaded.savedSearches.value.filter(search => search.id !== 2)
assert.deepEqual(reloaded.quickSavedSearches.value.map(search => search.id), [1, 4, 3])
await state.applySavedSearch(3)
state.toggleSavedSearchPin()
await state.applySavedSearch(4)
assert.equal(state.quickSavedSearches.value[0].id, 3)
const withPins = load('../src/App.vue')
withPins.savedSearches.value = [...state.savedSearches.value]
assert.deepEqual(withPins.visibleSavedSearchPins.value, [3])
assert.equal(withPins.quickSavedSearches.value[0].id, 3)
withPins.savedSearchId.value = 3
withPins.toggleSavedSearchPin()
assert.equal(withPins.quickSavedSearches.value[0].id, 4)
console.log('PASS: reader actions, filter reset and saved search shortcuts')
