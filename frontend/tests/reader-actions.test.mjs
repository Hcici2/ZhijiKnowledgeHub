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
await state.applySavedSearch(4)
state.toggleSavedSearchPin()
state.moveSavedSearchPin(-1)
assert.deepEqual(state.visibleSavedSearchPins.value, [4, 3])
state.moveSavedSearchPin(-1)
assert.deepEqual(state.visibleSavedSearchPins.value, [4, 3])
const reordered = load('../src/App.vue')
reordered.savedSearches.value = [...state.savedSearches.value]
assert.deepEqual(reordered.quickSavedSearches.value.map(search => search.id).slice(0, 2), [4, 3])
reordered.savedSearchId.value = 4
reordered.moveSavedSearchPin(1)
assert.deepEqual(reordered.visibleSavedSearchPins.value, [3, 4])
globalThis.HTMLElement = class {}
let shortcutHandled = false
let captureOpened = false
state.captureDialog.value = { get open() { return captureOpened }, showModal() { captureOpened = true } }
const shortcut = { ctrlKey: true, altKey: true, code: 'KeyN', target: null, preventDefault() { shortcutHandled = true } }
await state.shortcutNewNote({ ...shortcut, isComposing: true })
assert.equal(captureOpened, false)
await state.shortcutNewNote(shortcut)
assert.equal(shortcutHandled, true)
assert.equal(captureOpened, true)
globalThis.fetch = async (url, options) => {
  calls.push({ url, options })
  const data = url.startsWith('/api/attachments?name=')
    ? { id: 'a'.repeat(32), name: '设计稿.pdf', size: 4 }
    : { success: true, records: [], total: 0, page: 1, categories: [], days: {} }
  return { ok: true, status: 200, json: async () => data }
}
state.captureDialog.value.close = () => { captureOpened = false }
state.message.value = '带附件的正文'
const uploadedFile = new File(['test'], '设计稿.pdf')
await state.uploadNoteAttachments({ target: { files: [uploadedFile], value: 'picked' } })
assert.equal(calls.at(-1).options.body, uploadedFile)
assert.equal(state.captureAttachments.value.length, 1)
await state.addRecord()
const create = calls.findLast(call => call.url === '/api/records' && call.options?.method === 'POST')
assert.deepEqual(JSON.parse(create.options.body).attachment_ids, ['a'.repeat(32)])
assert.equal(state.captureAttachments.value.length, 0)
state.attachmentLibrary.value = [{ name: '设计稿.pdf' }, { name: '设计稿.png' }, { name: '其他.pdf' }]
state.attachmentQuery.value = '设计'
state.attachmentKind.value = 'PDF'
assert.deepEqual(state.visibleAttachments.value.map(file => file.name), ['设计稿.pdf'])
globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => ({ detail: 'Not Found' }) })
const storageRead = state.loadAttachmentStorage()
assert.equal(state.attachmentStorageLabel.value, '正在读取…')
await storageRead
assert.equal(state.attachmentStorageLabel.value, '未能读取')
assert.match(state.attachmentStorageStatus.value, /未提供附件接口/)
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ path: 'D:/知己附件', default_path: 'C:/知己附件' }) })
await state.loadAttachmentStorage()
assert.equal(state.attachmentStorageLabel.value, 'D:/知己附件')
assert.equal(state.attachmentStorageStatus.value, '')
assert.equal(state.attachmentPathInput.value, '')
const chosenFolder = 'E:\\知己资料'
globalThis.fetch = async url => {
  const query = new URL(url, 'http://localhost')
  assert.equal(query.pathname, '/api/settings/attachment-folders')
  const path = query.searchParams.get('path') ?? ''
  const folders = path ? [] : [{ name: '知己资料', path: chosenFolder }]
  return { ok: true, status: 200, json: async () => ({ path, parent: '', folders }) }
}
state.toggleAttachmentFolderPicker()
await new Promise(resolve => setImmediate(resolve))
assert.equal(state.attachmentFolderPickerOpen.value, true)
assert.equal(state.attachmentFolderList.value.folders[0].path, chosenFolder)
await state.browseAttachmentFolders(chosenFolder)
state.selectAttachmentFolder()
assert.equal(state.attachmentPathInput.value, chosenFolder)
assert.equal(state.attachmentFolderPickerOpen.value, false)
globalThis.fetch = async (url, options) => {
  assert.equal(url, '/api/settings/attachment-storage')
  assert.equal(options.method, 'PUT')
  assert.deepEqual(JSON.parse(options.body), { path: chosenFolder })
  return { ok: true, status: 200, json: async () => ({ path: 'E:\\知己资料' }) }
}
await state.changeAttachmentStorage()
assert.equal(state.attachmentStorageLabel.value, 'E:\\知己资料')
assert.equal(state.attachmentPathInput.value, '')
assert.equal(state.attachmentInlineKind('图片.JPG'), 'image')
assert.equal(state.attachmentInlineKind('录屏.mp4'), 'video')
assert.equal(state.attachmentInlineKind('说明.pdf'), undefined)
assert.equal(state.attachmentUrl({ id: 'abc' }, true), '/api/attachments/abc/file?preview=true')
const trashFile = { id: 'abc', name: '图片.jpg' }
let confirmed = false
const confirmations = []
const attachmentCalls = []
globalThis.window = { ...globalThis.window, confirm(message) { confirmations.push(message); return confirmed } }
globalThis.fetch = async (url, options) => {
  attachmentCalls.push([url, options?.method])
  return { ok: true, status: 200, json: async () => ({ attachments: [trashFile] }) }
}
state.linkedAttachments.value = [trashFile]
await state.changeAttachmentTrash(trashFile, 'trash')
assert.equal(attachmentCalls.length, 0)
confirmed = true
await state.changeAttachmentTrash(trashFile, 'trash')
assert.deepEqual(state.linkedAttachments.value, [])
await state.toggleAttachmentTrash()
assert.equal(state.activeView.value, 'trash')
assert.equal(state.attachmentTrashVisible.value, true)
state.attachmentKind.value = ''
state.attachmentQuery.value = ''
state.toggleAllTrashAttachments()
assert.deepEqual(state.selectedTrashAttachments.value, ['abc'])
assert.equal(state.attachmentUrl(trashFile, true, true), '/api/attachments/abc/file?preview=true&trash=true')
confirmed = false
await state.changeAttachmentsTrash(state.visibleSelectedAttachments.value, 'purge')
assert.equal(state.attachmentLibrary.value.length, 1)
confirmed = true
await state.changeAttachmentTrash(trashFile, 'purge')
assert.equal(state.attachmentLibrary.value.length, 0)
assert.deepEqual(state.selectedTrashAttachments.value, [])
assert.deepEqual(attachmentCalls, [
  ['/api/attachments/abc/trash', 'POST'],
  ['/api/attachments?trash=true', undefined],
  ['/api/attachments/abc', 'DELETE'],
])
assert.match(confirmations.at(-1), /无法恢复/)
state.attachmentLibrary.value = [trashFile, { id: 'def', name: '文档.pdf' }]
state.toggleAllTrashAttachments()
await state.changeAttachmentsTrash(state.visibleSelectedAttachments.value, 'restore')
assert.deepEqual(attachmentCalls.slice(-2), [
  ['/api/attachments/abc/restore', 'POST'],
  ['/api/attachments/def/restore', 'POST'],
])
assert.equal(state.attachmentLibrary.value.length, 0)
console.log('PASS: reader actions, filter reset and saved search shortcuts')
