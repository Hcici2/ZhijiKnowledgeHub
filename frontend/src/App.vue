
<script setup lang="ts">

import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import bookIcon from './assets/zhiji-book.png'
import CategoryPicker from './components/CategoryPicker.vue'
import NoteCalendar from './components/NoteCalendar.vue'
import TaskEditor from './components/TaskEditor.vue'
import WritingPreview from './components/WritingPreview.vue'
import FormattedEditor from './components/FormattedEditor.vue'
import AppIcon from './components/AppIcon.vue'
import { reviewMarkdown, reviewPlainText } from './reviewExport'
import { adjacentCalendarDay } from './calendarDay'
import CaptureTemplates from './components/CaptureTemplates.vue'
import AttachmentPreview from './components/AttachmentPreview.vue'
import ExistingAttachmentPicker from './components/ExistingAttachmentPicker.vue'

interface ApiRecord {
  id: number
  content: string
  category: string
  created_at: string
  title?: string
  summary?: string
  tags?: string
  pinned?: number | boolean
  deleted_at?: string | null
  note_date?: string | null
}

interface KnowledgeRecord {
  id: number
  title: string
  customTitle: string
  summary: string
  content: string
  tags: string[]
  url: string | null
  pinned: boolean
  deletedAt: string | null
  noteDate: string | null
  createdDay: string
  category: string
  time: string
}

const isDevelopmentPreview = import.meta.env.DEV
const message = ref('')
const captureTitle = ref('')
const captureNoteDate = ref('')
const captureDateMenu = ref<HTMLDetailsElement | null>(null)
const captureDateCaption = computed(() => !captureNoteDate.value || captureNoteDate.value === taskToday.value ? '今天' : captureNoteDate.value.replaceAll('-', ' / '))
const captureCategory = ref('待整理')
const captureBusy = ref(false)
const captureDialog = ref<HTMLDialogElement | null>(null)
const captureBody = ref<InstanceType<typeof FormattedEditor> | null>(null)
const captureWindowWidth = ref<number>()
const editWindowWidth = ref<number>()
const captureError = ref('')
const exportError = ref('')
const exportBusy = ref(false)
const exportFormat = ref<'md' | 'docx' | 'json' | 'xlsx'>('docx')
const exportScope = ref<'all' | 'current'>('all')
const recordOrder = ref<'newest' | 'oldest'>('newest')

function captureShortcut(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && !event.isComposing) {
    event.preventDefault()
    void addRecord()
  }
}

async function downloadRecords() {
  if (exportBusy.value) return
  exportBusy.value = true
  exportError.value = ''
  try {
    const format = exportFormat.value
    const params = exportScope.value === 'current' ? currentRecordParams() : new URLSearchParams()
    params.set('format', format)
    await downloadFile('/api/records/export?' + params.toString(), '知己知识库.' + format)
  } catch {
    if (authState.value === 'ready') exportError.value = '导出失败，请重试。'
  } finally {
    exportBusy.value = false
  }
}
async function downloadFile(path: string, fallback: string) {
  const response = await recordsRequest(path)
  if (!response.ok) throw new Error()
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  const filename = response.headers.get('Content-Disposition')?.split("filename*=UTF-8''")[1]
  link.href = url
  link.download = filename ? decodeURIComponent(filename) : fallback
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const backupBusy = ref(false)
const backupMessage = ref('')
const backupError = ref('')

async function downloadDatabaseBackup() {
  if (backupBusy.value) return
  backupBusy.value = true
  backupMessage.value = ''
  backupError.value = ''
  try {
    await downloadFile('/api/settings/backup', '知己数据备份.sqlite3')
    if (authState.value === 'ready') backupMessage.value = '备份已生成，请在浏览器下载列表中查看。'
  } catch {
    if (authState.value === 'ready') backupError.value = '备份失败，请重试。'
  } finally {
    backupBusy.value = false
  }
}

const authState = ref<'loading' | 'setup' | 'login' | 'ready' | 'offline'>('loading')
const password = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changingPassword = ref(false)
const authBusy = ref(false)
const authError = ref('')

function resetAuthForm() {
  password.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  authError.value = ''
}

function showLogin() {
  ++latestRequest
  records.value = []
  message.value = ''
  captureTitle.value = ''
  captureNoteDate.value = ''
  captureCategory.value = '待整理'
  captureError.value = ''
  captureDialog.value?.close()
  captureAttachments.value = []
  editAttachmentQueue.value = {}
  attachmentUploadStatus.value = ''
  attachmentLibrary.value = []
  linkedAttachments.value = []
  reviewDialog.value?.close()
  exportError.value = ''
  exportScope.value = 'all'
  recordOrder.value = 'newest'
  resetDates()
  currentPage.value = 1
  totalRecords.value = 0
  selectedTag.value = ''
  resetBatchMove()
  dailyReviewDrafts.value = {}
  dailyReviewSaved.value = {}
  batchIds.value = []
  batchCategory.value = ''
  batchStatus.value = ''
  knownCategories.value = []
  linkDialog.value?.close()
  resetLinkDialog()
  historyDialog.value?.close()
  clearHistory()
  backupMessage.value = ''
  backupError.value = ''
  resetImport()
  allTasks.value = []
  tasksLoadError.value = ''
  taskPageError.value = ''
  settingsOverview.value = null
  settingsCategory.value = ''
  renameFrom.value = ''
  categorySettingsNotice.value = ''
  categorySettingsError.value = ''
  trashPolicyEnabled.value = null
  trashPolicyError.value = ''
  recordActionStatus.value = ''
  recordActionError.value = ''
  searchQuery.value = ''
  activeKeyword.value = ''
  selectedCategory.value = ''
  activeView.value = 'library'
  libraryMode.value = 'list'
  calendarCounts.value = {}
  savedSearches.value = []
  savedSearchId.value = null
  resetSavedSearchForm()
  cancelEdit()
  changingPassword.value = false
  resetAuthForm()
  authState.value = 'login'
}

async function recordsRequest(url: string, options?: RequestInit) {
  const response = await fetch(url, options)
  if (response.status === 401) {
    showLogin()
    throw new Error('登录已过期，请重新登录。')
  }
  return response
}

async function checkAuth() {
  authState.value = 'loading'
  try {
    const response = await fetch('/api/auth/status')
    if (!response.ok) throw new Error()
    const status = await response.json()
    authState.value = status.authenticated ? 'ready' : status.needs_setup ? 'setup' : 'login'
    if (status.authenticated) await Promise.all([loadRecords(), loadSavedSearches(), loadCategories()])
  } catch {
    authState.value = 'offline'
  }
}

async function authAction(action: 'setup' | 'login' | 'logout' | 'password') {
  if (authBusy.value) return
  authError.value = ''
  if (action === 'setup' && password.value !== confirmPassword.value ||
      action === 'password' && newPassword.value !== confirmPassword.value) {
    authError.value = '两次输入的密码不一致。'
    return
  }

  authBusy.value = true
  try {
    const response = await fetch('/api/auth/' + action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: password.value, new_password: newPassword.value })
    })
    if (action === 'setup' && response.status === 409) {
      showLogin()
      return
    }
    if (action === 'password' && response.status === 401) {
      const result = await response.clone().json()
      if (result.detail === '请先登录。') {
        showLogin()
        return
      }
    }
    const result = await response.json()
    if (!response.ok) {
      throw new Error(typeof result.detail === 'string' ? result.detail : '请检查密码长度后重试。')
    }
    resetAuthForm()
    if (action === 'logout') {
      clearStoredCaptureDraft()
      showLogin()
      clearAllEditDrafts()
    } else if (action === 'password') {
      changingPassword.value = false
    } else {
      authState.value = 'ready'
      await Promise.all([loadRecords(), loadSavedSearches(), loadCategories()])
    }
  } catch (error) {
    authError.value = error instanceof Error && !(error instanceof TypeError)
      ? error.message
      : '无法连接知己，请稍后重试。'
  } finally {
    authBusy.value = false
  }
}

// 搜索关键词
const searchQuery = ref('')

// 搜索状态
const activeKeyword = ref('')
const selectedCategory = ref('')
const selectedTag = ref('')

function filterByTag(tag: string) {
  selectedTag.value = tag
  savedSearchId.value = null
  return restartList()
}
const views = [
  { id: 'inbox', label: '收集箱', icon: '▣', empty: '收集箱是空的。新记录默认放在这里。' },
  { id: 'library', label: '我的知识库', icon: '▤', empty: '暂时没有记录，写下你的第一条信息吧。' },
  { id: 'web', label: '网站与工具', icon: '◎', empty: '还没有收藏。粘贴一个完整的网址即可保存。' },
  { id: 'pinned', label: '置顶', icon: '✦', empty: '还没有置顶记录。点击记录上的「置顶」，方便下次找回。' },
  { id: 'recent', label: '最近 7 天', icon: '◷', empty: '最近 7 天还没有记录。' },
  { id: 'trash', label: '回收站', icon: '🗑︎', empty: '回收站是空的。删除的记录会留在这里，随时可以恢复。' },
  { id: 'attachments', label: '附件库', icon: '▧', empty: '' },
  { id: 'tasks', label: '待办事项', icon: '✓', empty: '' },
  { id: 'settings', label: '设置', icon: '⚙', empty: '' }
] as const
type RecordView = typeof views[number]['id']
const sidebarViews = views.filter(view => view.id !== 'recent')

interface SavedSearch {
  id: number
  name: string
  view: RecordView
  category: string
  keyword: string
  tag?: string
  date_from?: string | null
  date_to?: string | null
}

const savedSearches = ref<SavedSearch[]>([])
const savedSearchId = ref<number | null>(null)
const savedSearchRecencyKey = 'zhiji-saved-search-recency-v1'
const savedSearchPinsKey = 'zhiji-saved-search-pins-v1'
function readSavedSearchIds(key: string, limit: number): number[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? '[]')
    if (Array.isArray(value)) return [...new Set(value.filter((id): id is number => Number.isSafeInteger(id) && id > 0))].slice(0, limit)
  } catch { /* Browser storage is optional. */ }
  return []
}
const savedSearchRecency = ref(readSavedSearchIds(savedSearchRecencyKey, 20))
const savedSearchPins = ref(readSavedSearchIds(savedSearchPinsKey, 3))
const visibleSavedSearchPins = computed(() => savedSearchPins.value.filter(id => savedSearches.value.some(search => search.id === id)))
const selectedSavedSearchPinned = computed(() => savedSearchId.value !== null && visibleSavedSearchPins.value.includes(savedSearchId.value))
const selectedSavedSearchPinIndex = computed(() => savedSearchId.value === null ? -1 : visibleSavedSearchPins.value.indexOf(savedSearchId.value))
function updateSavedSearchPins(ids: number[]) {
  savedSearchPins.value = ids
  try { localStorage.setItem(savedSearchPinsKey, JSON.stringify(ids)) } catch { /* Keep the current session pins. */ }
}
function toggleSavedSearchPin() {
  const id = savedSearchId.value
  if (id === null || !savedSearches.value.some(search => search.id === id)) return
  const pins = visibleSavedSearchPins.value
  if (pins.includes(id)) updateSavedSearchPins(pins.filter(pin => pin !== id))
  else if (pins.length < 3) updateSavedSearchPins([...pins, id])
}
function moveSavedSearchPin(direction: -1 | 1) {
  const index = selectedSavedSearchPinIndex.value
  const pins = [...visibleSavedSearchPins.value]
  const destination = index + direction
  if (index < 0 || destination < 0 || destination >= pins.length) return
  const [id] = pins.splice(index, 1)
  if (id === undefined) return
  pins.splice(destination, 0, id)
  updateSavedSearchPins(pins)
}
function updateSavedSearchRecency(ids: number[]) {
  savedSearchRecency.value = ids.slice(0, 20)
  try { localStorage.setItem(savedSearchRecencyKey, JSON.stringify(savedSearchRecency.value)) } catch { /* Keep the current session order. */ }
}
const quickSavedSearches = computed(() => {
  const byId = new Map(savedSearches.value.map(search => [search.id, search]))
  const ids = new Set([...visibleSavedSearchPins.value, ...savedSearchRecency.value, ...savedSearches.value.map(search => search.id).reverse()])
  return [...ids].map(id => byId.get(id)).filter((search): search is SavedSearch => search !== undefined).slice(0, 3)
})
const savedSearchName = ref('')
const showSavedSearchForm = ref(false)
const savedSearchNameInput = ref<HTMLInputElement | null>(null)

const savedSearchPreview = computed(() => [
  '范围：' + viewDetails.value.label,
  ...activeLibraryFilters.value.map(filter => filter.label),
  ...(calendarVisible.value ? ['日期：' + selectedDay.value] : []),
])

async function openSavedSearchForm() {
  const parts = [activeKeyword.value, selectedTag.value, selectedCategory.value ? categoryLabel(selectedCategory.value) : ''].filter(Boolean)
  if (!parts.length) parts.push(calendarVisible.value ? selectedDay.value : viewDetails.value.label)
  savedSearchName.value = parts.join(' · ').slice(0, 40).replace(/[\uD800-\uDBFF]$/, '')
  savedSearchError.value = ''
  showSavedSearchForm.value = true
  await nextTick()
  savedSearchNameInput.value?.select()
}
const savedSearchError = ref('')
const savingSearch = ref(false)

function resetSavedSearchForm() {
  showSavedSearchForm.value = false
  savedSearchName.value = ''
  savedSearchError.value = ''
}

async function loadSavedSearches() {
  try {
    const response = await recordsRequest('/api/saved-searches')
    if (!response.ok) throw new Error()
    const result = await response.json() as { searches: SavedSearch[] }
    if (authState.value === 'ready') savedSearches.value = result.searches
  } catch {
    if (authState.value === 'ready') savedSearchError.value = '无法读取常用搜索，请刷新页面后重试。'
  }
}

function applySavedSearch(id = savedSearchId.value) {
  const saved = savedSearches.value.find(search => search.id === id)
  if (!saved || batchMoveBusy.value || batchBusy.value) return
  if (detailOpen.value && !closeActiveReader()) return
  resetBatchMove()
  savedSearchId.value = saved.id
  updateSavedSearchRecency([saved.id, ...savedSearchRecency.value.filter(id => id !== saved.id)])
  activeView.value = saved.view
  libraryMode.value = 'list'
  selectedCategory.value = saved.category
  selectedTag.value = saved.tag ?? ''
  appliedDateFrom.value = dateFromInput.value = saved.date_from ?? ''
  appliedDateTo.value = dateToInput.value = saved.date_to ?? ''
  datesOpen.value = Boolean(appliedDateFrom.value || appliedDateTo.value)
  dateError.value = ''
  searchQuery.value = saved.keyword
  activeKeyword.value = saved.keyword
  resetSavedSearchForm()
  cancelEdit()
  return restartList()
}

async function saveCurrentSearch() {
  const name = savedSearchName.value.trim()
  const dateParams = currentRecordParams()
  const from = dateParams.get('date_from')
  const to = dateParams.get('date_to')
  if (!name || savingSearch.value) return
  savedSearchError.value = ''
  savingSearch.value = true
  try {
    const response = await recordsRequest('/api/saved-searches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        view: activeView.value,
        category: selectedCategory.value,
        keyword: activeKeyword.value,
        tag: selectedTag.value,
        date_from: from,
        date_to: to
      })
    })
    const result = await response.json()
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '无法保存常用搜索。')
    if (authState.value === 'ready') {
      savedSearches.value.push(result as SavedSearch)
      if (result.view === activeView.value && result.category === selectedCategory.value &&
          result.keyword === activeKeyword.value && (result.tag ?? '') === selectedTag.value &&
          (result.date_from ?? null) === from && (result.date_to ?? null) === to) savedSearchId.value = result.id
      resetSavedSearchForm()
    }
  } catch (error) {
    if (authState.value === 'ready') {
      savedSearchError.value = error instanceof Error && !(error instanceof TypeError)
        ? error.message : '无法保存常用搜索，请重试。'
    }
  } finally {
    savingSearch.value = false
  }
}

async function removeSavedSearch() {
  const id = savedSearchId.value
  const search = savedSearches.value.find(item => item.id === id)
  if (!search || savingSearch.value || !window.confirm('移除常用搜索「' + search.name + '」？')) return
  savingSearch.value = true
  savedSearchError.value = ''
  try {
    const response = await recordsRequest('/api/saved-searches/' + id, { method: 'DELETE' })
    if (!response.ok && response.status !== 404) throw new Error()
    savedSearches.value = savedSearches.value.filter(item => item.id !== id)
    updateSavedSearchRecency(savedSearchRecency.value.filter(used => used !== id))
    updateSavedSearchPins(savedSearchPins.value.filter(pin => pin !== id))
    if (savedSearchId.value === id) savedSearchId.value = null
  } catch {
    if (authState.value === 'ready') savedSearchError.value = '无法移除常用搜索，请重试。'
  } finally {
    savingSearch.value = false
  }
}

function categoryChanged() {
  savedSearchId.value = null
  return restartList()
}
const activeView = ref<RecordView>('library')
const viewDetails = computed(() => views.find(view => view.id === activeView.value) ?? views[1])

function openView(view: RecordView, noteFilter?: { day: string } | { category: string } | { tag: string }, showAttachmentTrash = false) {
  if (batchMoveBusy.value) return
  if (taskBatchBusy.value || activeTaskRequests.value.size) return
  if (!detailOpen.value && editingTaskId.value !== null && !window.confirm('待办还有未保存的修改，确定离开吗？')) return
  if (detailOpen.value && !closeActiveReader()) return
  editingTaskId.value = null
  resetBatchMove()
  batchIds.value = []
  batchCategory.value = ''
  batchStatus.value = ''
  savedSearchId.value = null
  activeView.value = view
  attachmentTrashVisible.value = view === 'trash' && showAttachmentTrash
  selectedTrashAttachments.value = []
  if (view !== 'library') libraryMode.value = 'list'
  resetDates()
  currentPage.value = 1
  recordActionStatus.value = ''
  recordActionError.value = ''
  resetSavedSearchForm()
  selectedTag.value = ''
  selectedCategory.value = ''
  cancelEdit()
  if (view === 'library' && noteFilter) {
    searchQuery.value = ''
    activeKeyword.value = ''
    if ('day' in noteFilter) {
      todayKey.value = localDateKey()
      if (noteFilter.day.slice(0, 7) !== selectedDay.value.slice(0, 7)) calendarCounts.value = {}
      selectedDay.value = noteFilter.day
      libraryMode.value = 'calendar'
    } else {
      libraryMode.value = 'list'
      if ('category' in noteFilter) selectedCategory.value = noteFilter.category
      else selectedTag.value = noteFilter.tag
    }
  }
  if (view === 'attachments' || attachmentTrashVisible.value) {
    ++latestRequest
    attachmentActionMessage.value = ''
    return loadAttachmentLibrary()
  }
  if (view === 'tasks') {
    ++latestRequest
    return loadTasks()
  }
  if (view === 'settings') {
    ++latestRequest
    return Promise.all([loadTrashPolicy(), loadCategories(), loadSettingsOverview(), loadAttachmentStorage()])
  }
  return view === 'trash'
    ? Promise.all([loadRecords(), loadTrashPolicy()])
    : loadRecords()
}
const isLoading = ref(true)
const listError = ref('')
let latestRequest = 0

const defaultCategories = [
  '待整理',
  '工作经验',
  '学习笔记',
  'AI工具',
  '网站收藏',
  '个人灵感',
  '生活记录',
  '商业想法'
]
const knownCategories = ref<string[]>([])
const categories = computed(() => [...new Set([...defaultCategories, ...knownCategories.value])])
const batchCategoryOptions = computed(() => categories.value.filter(category => category !== '待整理'))

async function loadCategories() {
  try {
    const response = await recordsRequest('/api/categories')
    if (!response.ok) throw new Error()
    const data = await response.json() as { categories: string[] }
    if (authState.value === 'ready') knownCategories.value = data.categories
  } catch {
    // The form still accepts an explicit category when the list is unavailable.
  }
}

const batchIds = ref<number[]>([])
const batchCategory = ref('')
const batchBusy = ref(false)
const batchStatus = ref('')
const batchError = ref('')
const captureRecommendation = computed(() => recommendCategory(message.value))
const editRecommendation = computed(() => recommendCategory(editContent.value))

async function applyBatchCategory() {
  const ids = [...batchIds.value]
  const category = batchCategory.value.trim()
  if (!ids.length || !category || category === '待整理' || batchBusy.value) return
  batchBusy.value = true
  batchError.value = ''
  batchStatus.value = ''
  try {
    const response = await recordsRequest('/api/records/classify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids, category })
    })
    if (response.status === 409) {
      await loadRecords()
      batchError.value = '所选记录已发生变化，列表已刷新，请重新选择。'
      return
    }
    if (!response.ok) throw new Error()
    batchIds.value = []
    batchCategory.value = ''
    batchStatus.value = '已归类 ' + ids.length + ' 条记录。'
    await Promise.all([loadRecords(), loadCategories()])
  } catch {
    if (authState.value === 'ready') batchError.value = '归类失败，请重试。'
  } finally {
    batchBusy.value = false
  }
}

const categoryLabel = (category: string) => category === 'AI工具' ? 'AI 工具' : category

// 保存从数据库读取的记录
const records = ref<KnowledgeRecord[]>([])

// 实时统计记录数量
const recordCount = computed(() => records.value.length)

// 当前正在编辑的记录编号
const editingId = ref<number | null>(null)

// 编辑时使用的内容和分类
const editContent = ref('')
const editBody = ref<InstanceType<typeof FormattedEditor> | null>(null)
const writingTools = [
  { label: '有序列表', prefix: '1. ', icon: 'numbered-list' },
  { label: '引用', prefix: '> ', icon: 'quote' },
  { label: '清除格式', prefix: '', icon: 'clear-format' },
  { label: '章节', prefix: '# ', icon: 'heading' },
  { label: '小节', prefix: '## ', icon: 'subheading' },
  { label: '列表', prefix: '- ', icon: 'list' },
  { label: '行动项', prefix: '- [ ] ', icon: 'tasks' },
]
function insertWritingTool(target: 'capture' | 'edit', tool: typeof writingTools[number]) {
  const field = target === 'capture' ? captureBody.value : editBody.value
  if (target === 'capture' ? !captureBusy.value : !isSavingEdit.value) void field?.format(tool.prefix)
}

const editCategory = ref('待整理')
const editTags = ref<string[]>([])
const editTitle = ref('')
const editNoteDate = ref('')
const suggestion = ref<{ title: string, category: string, tags: string[] } | null>(null)

const organizationRules = [
  { category: '工作经验', tag: '工作', pattern: /会议|纪要|客户|需求|交付|复盘/ },
  { category: '学习笔记', tag: '学习', pattern: /学习|教程|课程|读书|读书笔记|练习/ },
  { category: 'AI工具', tag: 'AI工具', pattern: /人工智能|大模型|ChatGPT|Codex|Ollama/i },
  { category: '个人灵感', tag: '灵感', pattern: /灵感|脑洞|创意/ },
  { category: '生活记录', tag: '生活', pattern: /旅行|食谱|运动|健康|日记/ },
  { category: '商业想法', tag: '商业', pattern: /商业模式|定价|创业|竞品/ }
]

function recommendCategory(content: string): string {
  if (recordUrl(content)) return '网站收藏'
  const custom = knownCategories.value.filter(category =>
    !defaultCategories.includes(category) && category.length > 1 && content.includes(category)
  )
  if (custom.length) return custom.length === 1 ? custom[0] ?? '' : ''
  const rules = organizationRules.filter(rule => rule.pattern.test(content))
  return rules.length === 1 ? rules[0]?.category ?? '' : ''
}

function suggestOrganization(record: KnowledgeRecord) {
  startEdit(record)
  const rules = organizationRules.filter(rule => rule.pattern.test(record.content))
  const domain = record.url ? new URL(record.url).hostname : ''
  const firstLine = record.content.trim().split(/\r?\n/)[0]?.trim() ?? ''
  const title = domain || Array.from(firstLine).slice(0, 32).join('')
  const category = recommendCategory(record.content)
  const tags = domain ? ['网站', ...rules.map(rule => rule.tag)] : rules.map(rule => rule.tag)
  suggestion.value = {
    title: title === editTitle.value ? '' : title,
    category: category === editCategory.value ? '' : category,
    tags: tags.filter(tag => !editTags.value.includes(tag))
  }
}
const newTag = ref('')

function addTag() {
  const tag = newTag.value.trim()
  if (tag && !editTags.value.includes(tag)) editTags.value.push(tag)
  newTag.value = ''
}

// 编辑状态及错误提示
const isSavingEdit = ref(false)
const editError = ref('')

// 格式化时间
function formatTime(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 将数据库记录转换为首页展示格式
function parseTags(value?: string): string[] {
  if (!value) return []
  try {
    const tags: unknown = JSON.parse(value)
    return Array.isArray(tags) ? [...new Set(tags.filter((tag): tag is string => typeof tag === 'string'))] : []
  } catch {
    return []
  }
}

function recordUrl(content: string): string | null {
  const value = content.trim()
  if (!/^https?:[/][/]/i.test(value) || /[\s\\]/.test(value)) return null
  try {
    const url = new URL(value)
    return url.href
  } catch {
    return null
  }
}

function notePreviewText(content: string) {
  return content.split(/\r?\n/).map(line => line
    .replace(/^\s*(?:#{1,6}\s+|>\s+|[-*+]\s+|\d{1,9}\.\s+)/, '')
    .replace(/^\[[ xX]\]\s+/, '')
    .replace(/\s+/g, ' ')
    .trim()).filter(Boolean)
}

function displayNoteTitle(note: { title?: string, content: string }) {
  return note.title?.trim() || notePreviewText(note.content)[0] || '无标题笔记'
}

function formatRecord(item: ApiRecord): KnowledgeRecord {
  return {
    id: item.id,
    title: displayNoteTitle(item),
    customTitle: item.title ?? '',
    summary: item.summary ?? '',
    content: item.content,
    tags: parseTags(item.tags),
    url: recordUrl(item.content),
    pinned: Boolean(item.pinned),
    deletedAt: item.deleted_at ?? null,
    noteDate: item.note_date ?? null,
    createdDay: item.created_at.slice(0, 10),
    category: item.category,
    time: formatTime(item.created_at)
  }
}

function matches(text: string) {
  if (!activeKeyword.value) return -1
  return text.toLowerCase().indexOf(activeKeyword.value.toLowerCase())
}

function highlight(text: string) {
  const index = matches(text)
  if (index < 0) return [{ text, matched: false }]
  const end = index + activeKeyword.value.length
  return [
    { text: text.slice(0, index), matched: false },
    { text: text.slice(index, end), matched: true },
    { text: text.slice(end), matched: false }
  ]
}

function excerpt(record: KnowledgeRecord) {
  const lines = notePreviewText(record.content)
  if (!activeKeyword.value) {
    const preview = (lines[0] === record.title ? lines.slice(1) : lines).join(' ')
    const characters = Array.from(preview)
    return characters.length > 120 ? characters.slice(0, 120).join('') + '…' : preview
  }
  const source = matches(record.content) < 0 && matches(record.summary) >= 0
    ? record.summary
    : record.content
  const normalized = notePreviewText(source).join(' ')
  const text = matches(normalized) >= 0 ? normalized : source.replace(/\s+/g, ' ').trim()
  const index = Math.max(0, matches(text))
  const start = Math.max(0, index - 30)
  const end = Math.min(text.length, index + activeKeyword.value.length + 50)
  return (start ? '…' : '') + text.slice(start, end) + (end < text.length ? '…' : '')
}

// 始终按当前已提交的关键词和所选分类刷新列表。
const pageSize = 25
const currentPage = ref(1)
const totalRecords = ref(0)
const pageCount = computed(() => Math.max(1, Math.ceil(totalRecords.value / pageSize)))
const datesOpen = ref(false)
const dateFromInput = ref('')
const dateToInput = ref('')
const appliedDateFrom = ref('')
const appliedDateTo = ref('')
const dateError = ref('')

function resetDates() {
  datesOpen.value = false
  appliedDateFrom.value = dateFromInput.value = ''
  appliedDateTo.value = dateToInput.value = ''
  dateError.value = ''
}

function applyDates() {
  if (dateFromInput.value && dateToInput.value && dateFromInput.value > dateToInput.value) {
    dateError.value = '开始日期不能晚于结束日期。'
    return
  }
  appliedDateFrom.value = dateFromInput.value
  appliedDateTo.value = dateToInput.value
  dateError.value = ''
  savedSearchId.value = null
  return restartList()
}

function filterLastSevenDays() {
  const end = new Date()
  const start = new Date(end)
  start.setDate(start.getDate() - 6)
  dateFromInput.value = localDateKey(start)
  dateToInput.value = localDateKey(end)
  return applyDates()
}

function clearDates() {
  resetDates()
  savedSearchId.value = null
  return restartList()
}

const recordScrollRegion = ref<HTMLElement | null>(null)

function restartList() {
  currentPage.value = 1
  if (recordScrollRegion.value) recordScrollRegion.value.scrollTop = 0
  return loadRecords()
}

function changePage(page: number) {
  if (isLoading.value || page < 1 || page > pageCount.value) return
  currentPage.value = page
  if (recordScrollRegion.value) recordScrollRegion.value.scrollTop = 0
  cancelEdit()
  return loadRecords()
}

function localDateKey(date = new Date()) {
  return String(date.getFullYear()).padStart(4, '0') + '-' + String(date.getMonth() + 1).padStart(2, '0') +
    '-' + String(date.getDate()).padStart(2, '0')
}

const libraryMode = ref<'list' | 'calendar'>('list')
const calendarVisible = computed(() => activeView.value === 'library' && libraryMode.value === 'calendar')
const todayKey = ref(localDateKey())
const selectedDay = ref(localDateKey())
const calendarCounts = ref<Record<string, number>>({})
const calendarLoading = ref(false)
const calendarError = ref(false)
const selectedDayLabel = computed(() =>
  new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })
    .format(new Date(selectedDay.value + 'T12:00:00'))
)
let latestCalendarRequest = 0

async function loadCalendarCounts() {
  const month = selectedDay.value.slice(0, 7)
  const request = ++latestCalendarRequest
  calendarLoading.value = true
  calendarError.value = false
  try {
    const response = await recordsRequest('/api/records/calendar?' + new URLSearchParams({ month }))
    if (!response.ok) throw new Error()
    const result = await response.json() as { month: string, days: Record<string, number> }
    if (request === latestCalendarRequest && calendarVisible.value && result.month === selectedDay.value.slice(0, 7)) {
      calendarCounts.value = result.days
    }
  } catch {
    if (request === latestCalendarRequest && calendarVisible.value) calendarError.value = true
  } finally {
    if (request === latestCalendarRequest) calendarLoading.value = false
  }
}

function changeLibraryMode(mode: 'list' | 'calendar') {
  if (libraryMode.value === mode || (detailOpen.value && !closeActiveReader())) return
  resetBatchMove()
  libraryMode.value = mode
  todayKey.value = localDateKey()
  savedSearchId.value = null
  return restartList()
}

function selectCalendarToday() {
  todayKey.value = localDateKey()
  return selectCalendarDay(todayKey.value)
}

function stepCalendarDay(direction: -1 | 1) {
  const day = adjacentCalendarDay(selectedDay.value, direction)
  if (day) return selectCalendarDay(day)
}

function jumpToCalendarDate(event: Event) {
  const input = event.currentTarget as HTMLInputElement
  const requested = input.value
  if (/^\d{4}-\d{2}-\d{2}$/.test(requested) && input.validity.valid) void selectCalendarDay(requested)
  input.value = selectedDay.value
  const menu = input.closest('details')
  if (menu && requested === selectedDay.value) {
    menu.open = false
    menu.querySelector('summary')?.focus()
  }
}

function selectCalendarDay(day: string, source: 'calendar' | 'review' = 'calendar') {
  if (batchMoveBusy.value || dailyReviewBusy.value || (reviewDialog.value?.open && source !== 'review')) return
  if (detailOpen.value && !splitReader.value && !closeActiveReader()) return
  if (day.slice(0, 7) !== selectedDay.value.slice(0, 7)) calendarCounts.value = {}
  if (day !== selectedDay.value) resetBatchMove()
  selectedDay.value = day
  savedSearchId.value = null
  return restartList()
}

const dailyReviewDrafts = ref<Record<string, string>>({})
const dailyReviewSaved = ref<Record<string, string>>({})
const dailyReviewLoading = ref(false)
const dailyReviewBusy = ref(false)
const dailyReviewStatus = ref('')
const dailyReviewError = ref('')
const reviewDialog = ref<HTMLDialogElement | null>(null)
const reviewBody = ref<InstanceType<typeof FormattedEditor> | null>(null)
const reviewWindowWidth = ref<number>()
const reviewEditing = ref(false)
function browseDailyReview(direction: -1 | 0 | 1) {
  if (dailyReviewBusy.value || !reviewDialog.value?.open) return
  todayKey.value = localDateKey()
  const day = direction === 0 ? todayKey.value : adjacentCalendarDay(selectedDay.value, direction)
  if (!day || day === selectedDay.value) return
  reviewEditing.value = false
  reviewOutlineMenu.value?.removeAttribute('open')
  return selectCalendarDay(day, 'review')
}
const reviewOutlines = [
  { name: '简短回顾', headings: ['今天完成了什么', '记下一个收获', '明天先做什么'] },
  { name: '工作复盘', headings: ['进展与成果', '遇到的问题', '下一步行动'] },
  { name: '学习复盘', headings: ['今天学到的', '值得再练的', '下次学习计划'] },
]
const selectedReviewOutline = ref(0)
const reviewOutlineMenu = ref<HTMLDetailsElement | null>(null)

async function insertReviewOutline() {
  const outline = reviewOutlines[selectedReviewOutline.value]
  if (!outline) return
  const inserted = await reviewBody.value?.appendOutline(outline.headings.map(title => '## ' + title).join('\n\n\n') + '\n')
  if (inserted && reviewOutlineMenu.value) reviewOutlineMenu.value.open = false
}

async function openDailyReview() {
  reviewEditing.value = false
  if (!(selectedDay.value in dailyReviewSaved.value) && !dailyReviewLoading.value) {
    void loadDailyReview(selectedDay.value)
  }
  if (reviewDialog.value && !reviewDialog.value.open) reviewDialog.value.showModal()
  await nextTick()
  if (!dailyReviewLoading.value) reviewBody.value?.focus()
}

async function editDailyReview() {
  reviewEditing.value = true
  dailyReviewStatus.value = ''
  await nextTick()
  reviewBody.value?.focus()
}

async function copyDailyReview(markdown = false) {
  const content = dailyReviewSaved.value[selectedDay.value] ?? ''
  const text = markdown ? reviewMarkdown(selectedDay.value, content)?.text : plainNoteText(content)
  if (text === undefined) return
  try {
    await navigator.clipboard.writeText(text)
    dailyReviewStatus.value = markdown ? '已复制 Markdown。' : '已复制回顾纯文本。'
  } catch {
    dailyReviewStatus.value = '无法访问剪贴板，可选中文字手动复制。'
  }
}

function downloadDailyReview(format: 'markdown' | 'text') {
  const content = dailyReviewSaved.value[selectedDay.value] ?? ''
  const review = format === 'markdown' ? reviewMarkdown(selectedDay.value, content) : reviewPlainText(selectedDay.value, plainNoteText(content))
  if (!review) return
  try {
    const url = URL.createObjectURL(new Blob([review.text], { type: `text/${format === 'markdown' ? 'markdown' : 'plain'};charset=utf-8` }))
    try {
      const link = document.createElement('a')
      link.href = url
      link.download = review.filename
      link.click()
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }
    dailyReviewStatus.value = format === 'markdown' ? '已发起 Markdown 下载。' : '已发起纯文本下载。'
  } catch {
    dailyReviewStatus.value = '无法下载回顾，请重试。'
  }
}

async function reviewToNote() {
  const day = selectedDay.value
  const content = dailyReviewSaved.value[day]
  if (!content || dailyReviewBusy.value || captureBusy.value || templateBusy.value) return
  restoreCaptureDraft()
  if (hasCaptureDraft.value && !window.confirm('新建笔记已有草稿。用这篇回顾替换草稿吗？替换后可以撤销。')) return
  const before = currentCapture()
  const applied = { title: day + ' 每日回顾', category: '待整理', content }
  templateUndo.value = { before, applied, previousDate: captureNoteDate.value, appliedDate: day }
  setCaptureDraft(applied)
  captureNoteDate.value = day
  templateNotice.value = '已将回顾带入草稿，可选分类后保存为笔记。'
  reviewDialog.value?.close()
  await openCapture()
}
const reviewDraftPrefix = 'zhiji-review-draft-v1:'
function storeReviewDraft(day: string, content: string) {
  try {
    if (content.trim() === dailyReviewSaved.value[day]) sessionStorage.removeItem(reviewDraftPrefix + day)
    else sessionStorage.setItem(reviewDraftPrefix + day, content)
  } catch { /* The draft remains available until the page closes. */ }
}
const dailyReviewText = computed({
  get: () => dailyReviewDrafts.value[selectedDay.value] ?? '',
  set: (value: string) => {
    const day = selectedDay.value
    dailyReviewDrafts.value[day] = value
    dailyReviewStatus.value = ''
    storeReviewDraft(day, value)
  }
})
const dailyReviewExists = computed(() => Boolean(dailyReviewSaved.value[selectedDay.value]))
const dailyReviewChanged = computed(() =>
  dailyReviewText.value.trim() !== (dailyReviewSaved.value[selectedDay.value] ?? '')
)
const canEditDailyReview = computed(() => !dailyReviewLoading.value && selectedDay.value in dailyReviewSaved.value)
const showReviewEditor = computed(() => canEditDailyReview.value && (reviewEditing.value || !dailyReviewExists.value || dailyReviewChanged.value))
let latestReviewRequest = 0

async function loadDailyReview(day: string) {
  const request = ++latestReviewRequest
  dailyReviewLoading.value = true
  dailyReviewStatus.value = ''
  dailyReviewError.value = ''
  try {
    const response = await recordsRequest('/api/daily-reviews/' + day)
    if (!response.ok) throw new Error()
    const result = await response.json() as { content: string }
    if (typeof result.content !== 'string') throw new Error()
    if (request !== latestReviewRequest || authState.value !== 'ready') return
    const draft = dailyReviewDrafts.value[day]
    if (draft === undefined || draft === dailyReviewSaved.value[day]) {
      let stored: string | null = null
      try { stored = sessionStorage.getItem(reviewDraftPrefix + day) } catch { /* Storage is optional. */ }
      dailyReviewDrafts.value[day] = stored ?? result.content
    }
    dailyReviewSaved.value[day] = result.content
  } catch {
    if (request === latestReviewRequest && authState.value === 'ready') dailyReviewError.value = '无法读取每日回顾。'
  } finally {
    if (request === latestReviewRequest) dailyReviewLoading.value = false
  }
}

async function saveReviewForDay() {
  if (!(selectedDay.value in dailyReviewSaved.value) || !dailyReviewChanged.value || dailyReviewBusy.value || dailyReviewLoading.value) return
  const day = selectedDay.value
  const content = dailyReviewText.value.trim()
  dailyReviewBusy.value = true
  dailyReviewError.value = ''
  dailyReviewStatus.value = ''
  try {
    const response = await recordsRequest('/api/daily-reviews/' + day, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    })
    if (!response.ok) throw new Error()
    if (authState.value === 'ready') {
      dailyReviewSaved.value[day] = content
      dailyReviewDrafts.value[day] = content
      storeReviewDraft(day, content)
      if (content) reviewEditing.value = false
      if (calendarVisible.value && selectedDay.value === day) dailyReviewStatus.value = '回顾已保存。'
    }
  } catch {
    if (calendarVisible.value && selectedDay.value === day && authState.value === 'ready') {
      dailyReviewError.value = '保存回顾失败，请重试。'
    }
  } finally {
    dailyReviewBusy.value = false
  }
}

function discardReviewDraft() {
  const saved = dailyReviewSaved.value[selectedDay.value]
  if (saved === undefined || dailyReviewLoading.value || dailyReviewBusy.value || !dailyReviewChanged.value) return
  if (!window.confirm('放弃这一天未保存的回顾修改？')) return
  dailyReviewText.value = saved
  dailyReviewStatus.value = '已恢复上次保存的回顾。'
  dailyReviewError.value = ''
}

function reviewShortcut(event: KeyboardEvent) {
  if (event.isComposing || !(event.ctrlKey || event.metaKey)) return
  event.preventDefault()
  void saveReviewForDay()
}

watch([calendarVisible, selectedDay], ([visible, day]) => {
  if (visible && authState.value === 'ready') void loadDailyReview(day)
  else ++latestReviewRequest
})

const batchMoveIsActive = ref(false)
const batchMoveDate = ref('')
const batchMovedTo = ref('')
const batchMoveStatus = ref('')
const batchMoveError = ref('')
const batchMoveBusy = ref(false)
const batchOrganizeCategory = ref('')
const batchOrganizeTag = ref('')

function resetBatchMove() {
  batchMoveIsActive.value = false
  batchOrganizeCategory.value = ''
  batchOrganizeTag.value = ''
  batchIds.value = []
  batchMoveDate.value = ''
  batchMovedTo.value = ''
  batchMoveStatus.value = ''
  batchMoveError.value = ''
}

async function organizeSelectedRecords() {
  const ids = records.value.filter(record => batchIds.value.includes(record.id)).map(record => record.id)
  const category = batchOrganizeCategory.value.trim()
  const tag = batchOrganizeTag.value.trim()
  if (!batchMoveIsActive.value || batchMoveBusy.value || isLoading.value || !ids.length || !(category || tag)) return
  batchMoveBusy.value = true
  batchMoveStatus.value = ''
  batchMoveError.value = ''
  batchMovedTo.value = ''
  try {
    const response = await recordsRequest('/api/records/organize', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids, category, tag }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '批量整理失败。若刚更新知己，请重启预览后重试。')
    batchMoveStatus.value = result.updated ? `已整理 ${result.updated} 条笔记。` : '所选笔记已符合这些条件。'
    batchIds.value = []
    batchOrganizeCategory.value = ''
    batchOrganizeTag.value = ''
    await Promise.all([loadRecords(), loadCategories(), linkedRecord.value ? loadLinkRecord(linkedRecord.value.id, true) : undefined])
  } catch (error) {
    if (authState.value === 'ready') batchMoveError.value = error instanceof Error ? error.message : '批量整理失败。'
  } finally {
    batchMoveBusy.value = false
  }
}

function toggleBatchMove() {
  if (batchMoveBusy.value) return
  if (batchMoveIsActive.value) resetBatchMove()
  else {
    resetBatchMove()
    batchMoveIsActive.value = true
  }
}

function toggleBatchRecord(id: number) {
  if (batchMoveBusy.value || isLoading.value) return
  batchIds.value = batchIds.value.includes(id)
    ? batchIds.value.filter(selected => selected !== id)
    : [...batchIds.value, id]
}

async function trashSelectedRecords(action: boolean | 'purge' = false) {
  const restore = action === true
  const purge = action === 'purge'
  const ids = records.value.filter(record => batchIds.value.includes(record.id) && (!purge || record.deletedAt)).map(record => record.id)
  if (!(restore || purge ? activeView.value === 'trash' : batchMoveIsActive.value) || batchMoveBusy.value || isLoading.value || !ids.length) return
  if (purge && !window.confirm(`永久删除选中的 ${ids.length} 条笔记？删除后无法恢复。`)) return
  if (action === false && !window.confirm(`将选中的 ${ids.length} 条笔记移入回收站？`)) return
  batchMoveBusy.value = true
  batchMoveStatus.value = ''
  batchMoveError.value = ''
  batchMovedTo.value = ''
  const moved = new Set<number>()
  try {
    for (const id of ids) {
      if (authState.value !== 'ready') break
      try {
        const response = await recordsRequest('/api/records/' + id + (restore ? '/restore' : purge ? '/trash' : ''), { method: restore ? 'POST' : 'DELETE' })
        if (response.ok) moved.add(id)
      } catch { /* Keep unconfirmed records selected for retry. */ }
    }
    if (authState.value !== 'ready') return
    batchIds.value = batchIds.value.filter(id => !moved.has(id))
    if (purge && linkedRecord.value && moved.has(linkedRecord.value.id)) closeActiveReader()
    if (moved.size) batchMoveStatus.value = restore ? `已恢复 ${moved.size} 条笔记。` : purge ? `已永久删除 ${moved.size} 条笔记。` : `已将 ${moved.size} 条笔记移入回收站。`
    if (moved.size < ids.length) batchMoveError.value = `有 ${ids.length - moved.size} 条笔记操作未完成，请检查列表后重试。`
    await loadRecords()
  } finally {
    batchMoveBusy.value = false
  }
}

async function moveBatchToDate() {
  const ids = [...batchIds.value]
  const noteDate = batchMoveDate.value
  if (!ids.length || !noteDate || batchMoveBusy.value) return
  batchMoveBusy.value = true
  batchMoveStatus.value = ''
  batchMoveError.value = ''
  try {
    const response = await recordsRequest('/api/records/move-date', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids, note_date: noteDate })
    })
    const result = await response.json() as { updated: number, unchanged: number, detail?: string }
    if (!response.ok) {
      if (response.status === 409) await loadRecords()
      throw new Error(result.detail || '批量移动失败，请重试。')
    }
    if (authState.value !== 'ready') return
    resetBatchMove()
    batchMoveStatus.value = '已移动 ' + result.updated + ' 条笔记。'
    if (result.unchanged) batchMoveStatus.value += ' 另有 ' + result.unchanged + ' 条已在该日期。'
    if (result.updated) batchMovedTo.value = noteDate
    await loadRecords()
  } catch (error) {
    if (authState.value === 'ready') batchMoveError.value = error instanceof Error && !(error instanceof TypeError)
      ? error.message : '批量移动失败，请重试。'
  } finally {
    batchMoveBusy.value = false
  }
}

function viewBatchDestination() {
  const destination = batchMovedTo.value
  if (!destination) return
  if (!calendarVisible.value) void changeLibraryMode('calendar')
  return selectCalendarDay(destination)
}

function currentRecordParams() {
  const params = new URLSearchParams()
  if (activeKeyword.value) params.set('q', activeKeyword.value)
  if (selectedTag.value) params.set('tag', selectedTag.value)
  const category = activeView.value === 'inbox' ? '待整理' : selectedCategory.value
  if (category) params.set('category', category)
  if (activeView.value === 'web' || activeView.value === 'recent' || activeView.value === 'pinned' || activeView.value === 'trash') params.set('view', activeView.value)
  if (recordOrder.value === 'oldest') params.set('order', 'oldest')
  const from = calendarVisible.value ? selectedDay.value : appliedDateFrom.value
  const to = calendarVisible.value ? selectedDay.value : appliedDateTo.value
  if (from) params.set('date_from', from)
  if (to) params.set('date_to', to)
  return params
}

async function loadRecords() {
  if (calendarVisible.value) void loadCalendarCounts()
  const request = ++latestRequest
  const params = currentRecordParams()
  params.set('page', String(currentPage.value))
  params.set('page_size', String(pageSize))

  isLoading.value = true
  listError.value = ''
  try {
    const response = await recordsRequest('/api/records/search?' + params.toString())
    if (!response.ok) throw new Error('读取记录失败')

    const data = await response.json() as {
      success: boolean
      records: ApiRecord[]
      page: number
      total: number
    }
    if (!data.success) throw new Error('读取记录失败')

    // 只使用最近一次请求的结果。
    if (request === latestRequest) {
      records.value = data.records.map(formatRecord)
      currentPage.value = data.page
      totalRecords.value = data.total
      const visible = new Set(data.records.map(record => record.id))
      batchIds.value = batchIds.value.filter(id => visible.has(id))
    }
  } catch {
    if (request === latestRequest) {
      listError.value = '读取记录失败，请检查后台服务后重试。'
    }
  } finally {
    if (request === latestRequest) isLoading.value = false
  }
}

function searchRecords() {
  savedSearchId.value = null
  activeKeyword.value = searchQuery.value.trim()
  return restartList()
}

function clearSearch() {
  savedSearchId.value = null
  searchQuery.value = ''
  activeKeyword.value = ''
  return restartList()
}

type LibraryFilter = 'keyword' | 'category' | 'tag' | 'date'
const activeLibraryFilters = computed(() => {
  const filters: { key: LibraryFilter, label: string }[] = []
  if (activeKeyword.value) filters.push({ key: 'keyword', label: '关键词：' + activeKeyword.value })
  if (selectedCategory.value && activeView.value !== 'inbox') filters.push({ key: 'category', label: '分类：' + categoryLabel(selectedCategory.value) })
  if (selectedTag.value) filters.push({ key: 'tag', label: '标签：' + selectedTag.value })
  if (!calendarVisible.value && (appliedDateFrom.value || appliedDateTo.value)) {
    filters.push({ key: 'date', label: '日期：' + (appliedDateFrom.value || '不限') + ' 至 ' + (appliedDateTo.value || '不限') })
  }
  return filters
})

function removeLibraryFilter(filter: LibraryFilter) {
  if (batchMoveBusy.value || batchBusy.value) return
  savedSearchId.value = null
  if (filter === 'keyword') return clearSearch()
  if (filter === 'category') selectedCategory.value = ''
  if (filter === 'tag') selectedTag.value = ''
  if (filter === 'date') resetDates()
  return restartList()
}

function clearLibraryFilters() {
  if (batchMoveBusy.value || batchBusy.value) return
  selectedCategory.value = ''
  selectedTag.value = ''
  resetDates()
  resetSavedSearchForm()
  return clearSearch()
}

type CaptureDraft = { title: string, category: string, content: string }
interface NoteAttachment {
  id: string
  name: string
  size: number
  record_id?: number | null
  record_title?: string | null
  deleted_at?: string | null
}
const captureAttachments = ref<NoteAttachment[]>([])
const editAttachmentQueue = ref<Record<number, NoteAttachment[]>>({})
const attachmentUploadBusy = ref(false)
const attachmentUploadStatus = ref('')
const attachedEditFiles = computed(() => editAttachmentQueue.value[editingId.value ?? -1] ?? [])
const attachmentLibrary = ref<NoteAttachment[]>([])
const linkedAttachments = ref<NoteAttachment[]>([])
const libraryAttachmentsLoading = ref(false)
const libraryAttachmentsError = ref('')
const attachmentTrashVisible = ref(false)
const selectedTrashAttachments = ref<string[]>([])
const attachmentActionBusy = ref(false)
const attachmentActionMessage = ref('')
const linkedAttachmentsError = ref('')
const attachmentQuery = ref('')
const attachmentKind = ref('')
const onlyUnlinkedAttachments = ref(false)
const attachmentStoragePath = ref('')
const attachmentDefaultPath = ref('')
const attachmentPathInput = ref('')
type AttachmentFolderList = { path: string; parent: string; folders: { name: string; path: string }[] }
const attachmentFolderPickerOpen = ref(false)
const attachmentFolderList = ref<AttachmentFolderList | null>(null)
const attachmentFoldersLoading = ref(false)
const attachmentFoldersError = ref('')
const attachmentStorageBusy = ref(false)
const attachmentStorageLoading = ref(false)
const attachmentStorageStatus = ref('')
const attachmentStorageLabel = computed(() =>
  attachmentStorageLoading.value ? '正在读取…' : attachmentStoragePath.value || '未能读取'
)

function attachmentType(name: string) {
  if (/\.(png|jpe?g|gif|webp)$/i.test(name)) return '图片'
  if (/\.pdf$/i.test(name)) return 'PDF'
  if (/\.(mp4|webm|mov|mkv|avi|m4v)$/i.test(name)) return '视频'
  return '其他文件'
}
function attachmentCanPreview(name: string) { return /\.(png|jpe?g|gif|webp|pdf|mp4|webm)$/i.test(name) }
function attachmentInlineKind(name: string) {
  if (attachmentType(name) === '图片') return 'image'
  if (/\.(mp4|webm)$/i.test(name)) return 'video'
  return undefined
}
function attachmentSize(size: number) {
  return size < 1024 ? size + ' B' : size < 1048576 ? (size / 1024).toFixed(1) + ' KB' : (size / 1048576).toFixed(1) + ' MB'
}
const visibleAttachments = computed(() => attachmentLibrary.value.filter(file =>
  (attachmentTrashVisible.value || !onlyUnlinkedAttachments.value || !file.record_id) &&
  (!attachmentKind.value || attachmentType(file.name) === attachmentKind.value) &&
  file.name.toLowerCase().includes(attachmentQuery.value.trim().toLowerCase())
))
function attachmentUrl(file: NoteAttachment, preview = false, trash = false) {
  const query = new URLSearchParams()
  if (preview) query.set('preview', 'true')
  if (trash) query.set('trash', 'true')
  return '/api/attachments/' + encodeURIComponent(file.id) + '/file' + (query.size ? '?' + query : '')
}
async function attachmentRequest(url: string, options?: RequestInit) {
  const response = await recordsRequest(url, options)
  if (!response.ok) {
    const result = await response.json().catch(() => ({}))
    if (response.status === 404 && result.detail === 'Not Found') {
      throw new Error('当前后台未提供附件接口。请重启知己预览后重试。')
    }
    throw new Error(typeof result.detail === 'string' ? result.detail : '附件操作失败，请重试。')
  }
  return response.json()
}

async function loadUnlinkedAttachments(): Promise<NoteAttachment[]> {
  const result = await attachmentRequest('/api/attachments')
  return result.attachments.filter((file: NoteAttachment) => !file.record_id)
}

function queueExistingAttachments(files: NoteAttachment[], noteId: number | null = null) {
  const queue = noteId === null ? captureAttachments.value : (editAttachmentQueue.value[noteId] ??= [])
  const unique = new Map(queue.map(file => [file.id, file]))
  for (const file of files) {
    if (!file.record_id) unique.set(file.id, file)
  }
  if (unique.size > 50) {
    attachmentUploadStatus.value = '一次最多关联 50 个附件，请减少选择。'
    return
  }
  if (noteId === null) captureAttachments.value = [...unique.values()]
  else editAttachmentQueue.value[noteId] = [...unique.values()]
  attachmentUploadStatus.value = '保存笔记后，所选附件会关联到这篇笔记。'
}

async function uploadNoteAttachments(event: Event, noteId: number | null = null) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (!files.length || attachmentUploadBusy.value) return
  const queue = noteId === null ? captureAttachments.value : (editAttachmentQueue.value[noteId] ??= [])
  if (files.length > 50 - queue.length) {
    attachmentUploadStatus.value = '一次最多关联 50 个附件，请减少选择。'
    return
  }
  attachmentUploadBusy.value = true
  const failures: string[] = []
  try {
    for (const [index, file] of files.entries()) {
      if (authState.value !== 'ready') break
      attachmentUploadStatus.value = '正在上传 ' + (index + 1) + ' / ' + files.length + '：' + file.name
      try {
        if (file.size > 250 * 1024 * 1024) throw new Error('超过 250 MB')
        const uploaded = await attachmentRequest('/api/attachments?name=' + encodeURIComponent(file.name), { method: 'POST', body: file })
        queue.push(uploaded)
      } catch (error) {
        failures.push(file.name + '：' + (error instanceof Error ? error.message : '上传失败'))
      }
    }
    attachmentUploadStatus.value = failures.length ? failures.join('；') : '附件已保存，保存笔记后会完成关联。'
  } finally {
    attachmentUploadBusy.value = false
  }
}

async function loadAttachmentLibrary() {
  const trash = attachmentTrashVisible.value
  libraryAttachmentsLoading.value = true
  libraryAttachmentsError.value = ''
  try {
    const result = await attachmentRequest(trash ? '/api/attachments?trash=true' : '/api/attachments')
    if (authState.value === 'ready' && trash === attachmentTrashVisible.value) attachmentLibrary.value = result.attachments
  } catch (error) {
    libraryAttachmentsError.value = error instanceof Error ? error.message : '无法读取附件库。'
  } finally { libraryAttachmentsLoading.value = false }
}
function toggleAttachmentTrash() {
  return openView('trash', undefined, !attachmentTrashVisible.value)
}
const visibleSelectedAttachments = computed(() =>
  visibleAttachments.value.filter(file => selectedTrashAttachments.value.includes(file.id))
)
const allVisibleTrashAttachmentsSelected = computed(() =>
  visibleAttachments.value.length > 0 && visibleSelectedAttachments.value.length === visibleAttachments.value.length
)
function toggleAllTrashAttachments() {
  selectedTrashAttachments.value = allVisibleTrashAttachmentsSelected.value ? [] : visibleAttachments.value.map(file => file.id)
}
async function changeAttachmentTrash(file: NoteAttachment, action: 'trash' | 'restore' | 'purge') {
  return changeAttachmentsTrash([file], action)
}
async function changeAttachmentsTrash(files: NoteAttachment[], action: 'trash' | 'restore' | 'purge') {
  if (attachmentActionBusy.value || !files.length) return
  const label = files.length === 1 ? '「' + files[0]!.name + '」' : files.length + ' 个附件'
  if (action === 'trash' && !window.confirm('将附件 ' + label + ' 移入回收站？')) return
  if (action === 'purge' && !window.confirm('永久删除附件 ' + label + '？删除后无法恢复。')) return
  attachmentActionBusy.value = true
  attachmentActionMessage.value = ''
  try {
    const completed = new Set<string>()
    let failure = ''
    for (const file of files) {
      const url = '/api/attachments/' + encodeURIComponent(file.id)
      try {
        await attachmentRequest(action === 'purge' ? url : url + '/' + action, { method: action === 'purge' ? 'DELETE' : 'POST' })
        completed.add(file.id)
      } catch (error) {
        failure ||= error instanceof Error ? error.message : '附件操作失败。'
        if (authState.value !== 'ready') break
      }
    }
    const remaining = (item: NoteAttachment) => !completed.has(item.id)
    attachmentLibrary.value = attachmentLibrary.value.filter(remaining)
    linkedAttachments.value = linkedAttachments.value.filter(remaining)
    selectedTrashAttachments.value = selectedTrashAttachments.value.filter(id => !completed.has(id))
    const verb = action === 'trash' ? '移入回收站' : action === 'restore' ? '恢复' : '永久删除'
    attachmentActionMessage.value = `已${verb} ${completed.size} 个附件。` +
      (failure ? ` ${files.length - completed.size} 个未完成。${failure}` : '')
  } finally {
    attachmentActionBusy.value = false
  }
}
async function loadAttachmentStorage() {
  if (attachmentStorageLoading.value || attachmentStorageBusy.value) return
  attachmentStorageLoading.value = true
  attachmentStorageStatus.value = ''
  try {
    const result = await attachmentRequest('/api/settings/attachment-storage')
    attachmentStoragePath.value = result.path
    attachmentDefaultPath.value = result.default_path
  } catch (error) {
    attachmentStorageStatus.value = error instanceof Error ? error.message : '无法读取存储设置。'
  } finally {
    attachmentStorageLoading.value = false
  }
}
async function browseAttachmentFolders(path = '') {
  if (attachmentFoldersLoading.value) return
  attachmentFoldersLoading.value = true
  attachmentFoldersError.value = ''
  try {
    const query = path ? '?' + new URLSearchParams({ path }) : ''
    attachmentFolderList.value = await attachmentRequest('/api/settings/attachment-folders' + query)
  } catch (error) {
    attachmentFoldersError.value = error instanceof Error ? error.message : '无法读取文件夹。'
  } finally {
    attachmentFoldersLoading.value = false
  }
}
function toggleAttachmentFolderPicker() {
  attachmentFolderPickerOpen.value = !attachmentFolderPickerOpen.value
  if (attachmentFolderPickerOpen.value) void browseAttachmentFolders()
}
function selectAttachmentFolder() {
  const folder = attachmentFolderList.value?.path
  if (!folder || attachmentFoldersLoading.value) return
  attachmentPathInput.value = folder
  attachmentFolderPickerOpen.value = false
}
async function changeAttachmentStorage(useDefault = false, organizeNames = false) {
  const path = organizeNames ? attachmentStoragePath.value : attachmentPathInput.value.trim()
  if (attachmentStorageBusy.value || attachmentStorageLoading.value || !attachmentStoragePath.value || (!useDefault && !path)) return
  attachmentStorageBusy.value = true
  attachmentStorageStatus.value = organizeNames ? '正在整理现有附件的文件名…' : '正在复制和校验附件，请保持窗口打开…'
  try {
    const result = await attachmentRequest('/api/settings/attachment-storage', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: useDefault ? '' : path }),
    })
    attachmentStoragePath.value = result.path
    attachmentPathInput.value = ''
    attachmentFolderPickerOpen.value = false
    attachmentStorageStatus.value = result.cleanup_remaining
      ? `附件已保存，但有 ${result.cleanup_remaining} 个旧附件副本未能清理。请检查原目录 ${result.previous_path} 和当前目录。`
      : organizeNames ? '整理完成，附件文件名已保留原名和扩展名。' : '已切换到该目录，原目录中的附件已清理。'
  } catch (error) {
    attachmentStorageStatus.value = error instanceof Error ? error.message : '无法更改存储目录。'
  } finally { attachmentStorageBusy.value = false }
}

const captureDraftKey = 'zhiji-capture-draft-v1'
const hasCaptureDraft = computed(() => !!(captureTitle.value.trim() || message.value.trim() || captureAttachments.value.length))
const hasStoredCaptureDraft = ref(false)
const restoredCaptureDraft = ref(false)
function clearStoredCaptureDraft() {
  try { sessionStorage.removeItem(captureDraftKey) } catch { /* Storage can be disabled. */ }
  hasStoredCaptureDraft.value = false
  restoredCaptureDraft.value = false
}
function restoreCaptureDraft() {
  if (authState.value !== 'ready' || hasCaptureDraft.value) return
  try {
    const raw = sessionStorage.getItem(captureDraftKey)
    if (!raw) return
    const draft = JSON.parse(raw)
    if (!draft || typeof draft.title !== 'string' || typeof draft.content !== 'string' || typeof draft.category !== 'string') return
    setCaptureDraft({ title: draft.title, content: draft.content, category: draft.category || '待整理' })
    captureNoteDate.value = typeof draft.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(draft.date) ? draft.date : ''
    if (Array.isArray(draft.attachments)) captureAttachments.value = draft.attachments.filter((file: NoteAttachment) =>
      file && typeof file.id === 'string' && /^[a-f0-9]{32}$/.test(file.id) && typeof file.name === 'string' && typeof file.size === 'number').slice(0, 50)
    restoredCaptureDraft.value = true
  } catch { /* A broken or unavailable draft should not prevent writing. */ }
}
watch([message, captureTitle, captureCategory, captureNoteDate, captureAttachments], () => {
  if (authState.value !== 'ready') return
  try {
    if (hasCaptureDraft.value) {
      sessionStorage.setItem(captureDraftKey, JSON.stringify({ ...currentCapture(), date: captureNoteDate.value, attachments: captureAttachments.value }))
      hasStoredCaptureDraft.value = true
    }
    else clearStoredCaptureDraft()
  } catch { /* The in-memory draft remains usable. */ }
}, { deep: true })
function discardCaptureDraft() {
  if (captureBusy.value || !hasCaptureDraft.value || !window.confirm('放弃这份未保存的笔记草稿？')) return
  setCaptureDraft({ title: '', content: '', category: '待整理' })
  captureAttachments.value = []
  captureNoteDate.value = calendarVisible.value ? selectedDay.value : ''
  templateUndo.value = null
  templateNotice.value = ''
  captureError.value = ''
  clearStoredCaptureDraft()
}
const templateUndo = ref<{ before: CaptureDraft, applied: CaptureDraft, previousDate?: string, appliedDate?: string } | null>(null)
const templateNotice = ref('')
function loadReadingPreferences() {
  try {
    const saved = JSON.parse(localStorage.getItem('zhiji-reading') || '{}')
    return { size: [14, 16, 18, 20].includes(saved.size) ? saved.size : 16, spacious: saved.spacious !== false }
  } catch { return { size: 16, spacious: true } }
}
const readingPreferences = ref(loadReadingPreferences())
watch(readingPreferences, value => {
  try { localStorage.setItem('zhiji-reading', JSON.stringify(value)) } catch { /* Reading still works without browser storage. */ }
}, { deep: true })
const readingCharacters = computed(() => Array.from(linkedRecord.value?.content.replace(/\s/g, '') || '').length)
const readingMinutes = computed(() => Math.max(1, Math.ceil(readingCharacters.value / 400)))
function resetReadingPreferences() { readingPreferences.value = { size: 16, spacious: true } }
const templateEditing = ref(false)
const templateBusy = ref(false)
const templatePicker = ref<InstanceType<typeof CaptureTemplates> | null>(null)
const captureLength = computed(() => Array.from(message.value).length)
function currentCapture(): CaptureDraft {
  return { title: captureTitle.value, category: captureCategory.value, content: message.value }
}
function setCaptureDraft(draft: CaptureDraft) {
  captureTitle.value = draft.title
  captureCategory.value = draft.category
  message.value = draft.content
}
async function applyCaptureTemplate(template: CaptureDraft) {
  if (captureBusy.value) return
  if ((message.value.trim() || captureTitle.value.trim()) && !window.confirm('使用模板将替换当前标题和正文，保留笔记分类。确定继续吗？替换后可撤销。')) return
  templateUndo.value = { before: currentCapture(), applied: { title: template.title, category: captureCategory.value, content: template.content } }
  setCaptureDraft({ ...template, category: captureCategory.value })
  templatePicker.value?.collapse()
  templateNotice.value = '模板已填入草稿，可自由修改；笔记日期保持不变。'
  await nextTick()
  captureBody.value?.focus()
}
function undoCaptureTemplate() {
  const undo = templateUndo.value
  if (!undo || captureBusy.value) return
  const changed = JSON.stringify(currentCapture()) !== JSON.stringify(undo.applied) || (undo.appliedDate !== undefined && captureNoteDate.value !== undo.appliedDate)
  if (changed && !window.confirm('当前草稿已有后续修改。仍要撤销并恢复原草稿吗？')) return
  setCaptureDraft(undo.before)
  if (undo.previousDate !== undefined) captureNoteDate.value = undo.previousDate
  templateUndo.value = null
  templateNotice.value = '已恢复使用模板前的草稿。'
}
watch(authState, state => {
  if (state !== 'ready') { templateUndo.value = null; templateNotice.value = ''; templateEditing.value = false; templateBusy.value = false }
})

async function templateFromRecord(record: KnowledgeRecord) {
  if (record.deletedAt || captureBusy.value || templateBusy.value) return
  if (detailOpen.value && !closeActiveReader()) return
  if (captureDialog.value && !captureDialog.value.open) captureDialog.value.showModal()
  await nextTick()
  await templatePicker.value?.beginTemplate({ title: record.customTitle || record.title, content: record.content, name: (record.customTitle || record.title).slice(0, 50) })
}

async function openCapture() {
  restoreCaptureDraft()
  if (captureDateMenu.value) captureDateMenu.value.open = false
  captureError.value = ''
  if (!hasCaptureDraft.value) {
    captureNoteDate.value = calendarVisible.value ? selectedDay.value : ''
  }
  if (captureDialog.value && !captureDialog.value.open) captureDialog.value.showModal()
  await nextTick()
  captureBody.value?.focus()
}

function preventClosingCapture(event: Event) {
  if (captureBusy.value || templateBusy.value) event.preventDefault()
}

async function addRecord() {
  const content = message.value.trim()
  if (!content || captureBusy.value || templateEditing.value || attachmentUploadBusy.value) return

  const noteDate = captureNoteDate.value || null
  captureBusy.value = true
  captureError.value = ''
  try {
    const response = await recordsRequest('/api/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, title: captureTitle.value.trim(), category: captureCategory.value, note_date: noteDate, ...(captureAttachments.value.length ? { attachment_ids: captureAttachments.value.map(file => file.id) } : {}) })
    })
    if (!response.ok) throw new Error()

    clearStoredCaptureDraft()
    captureAttachments.value = []
    attachmentUploadStatus.value = ''
    message.value = ''
    captureTitle.value = ''
    templateUndo.value = null
    templateNotice.value = ''
    captureNoteDate.value = ''
    captureCategory.value = '待整理'
    captureDialog.value?.close()
    recordActionStatus.value = '笔记已保存。'
    if (calendarVisible.value) {
      todayKey.value = localDateKey()
      selectedDay.value = noteDate ?? todayKey.value
    }
    if (activeView.value === 'settings') await Promise.all([loadSettingsOverview(), loadCategories()])
    else await Promise.all([restartList(), loadCategories()])
  } catch {
    if (authState.value === 'ready') captureError.value = '保存失败，请检查本地服务后重试。'
  } finally {
    captureBusy.value = false
  }
}

const editDraftPrefix = 'zhiji-edit-draft-v1:'
const editDraftIds = ref(new Set<number>())
watch(authState, state => {
  editDraftIds.value.clear()
  hasStoredCaptureDraft.value = false
  if (state !== 'ready') return
  try {
    hasStoredCaptureDraft.value = sessionStorage.getItem(captureDraftKey) !== null
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i)
      if (!key?.startsWith(editDraftPrefix)) continue
      const id = Number(key.slice(editDraftPrefix.length))
      if (Number.isSafeInteger(id) && id > 0) editDraftIds.value.add(id)
    }
  } catch { /* Storage is optional. */ }
})
const editDraftBase = ref('')
const restoredEditDraft = ref(false)
function editDraftFields() {
  return { title: editTitle.value, content: editContent.value, category: editCategory.value,
    date: editNoteDate.value, tags: [...editTags.value], pendingTag: newTag.value }
}
function clearAllEditDrafts() {
  editDraftIds.value.clear()
  try {
    for (let i = sessionStorage.length - 1; i >= 0; i--) {
      const key = sessionStorage.key(i)
      if (key && (key.startsWith(editDraftPrefix) || key.startsWith(reviewDraftPrefix))) sessionStorage.removeItem(key)
    }
  } catch { /* Storage is optional. */ }
}
function clearEditDraft(id: number) {
  try { sessionStorage.removeItem(editDraftPrefix + id) } catch { /* Storage is optional. */ }
  editDraftIds.value.delete(id)
}
function persistEditDraft() {
  if (editingId.value === null || !editDraftBase.value || authState.value !== 'ready') return false
  try {
    const fields = editDraftFields()
    if (JSON.stringify(fields) === editDraftBase.value) clearEditDraft(editingId.value)
    else {
      sessionStorage.setItem(editDraftPrefix + editingId.value, JSON.stringify({ ...fields, base: editDraftBase.value }))
      editDraftIds.value.add(editingId.value)
    }
    return true
  } catch { return false }
}
watch([editTitle, editContent, editCategory, editNoteDate, editTags, newTag], persistEditDraft, { deep: true })

function startEdit(record: KnowledgeRecord, recover = true) {
  editingId.value = record.id
  suggestion.value = null
  editTitle.value = record.customTitle
  editNoteDate.value = record.noteDate ?? ''
  editContent.value = record.content
  editTags.value = [...record.tags]
  newTag.value = ''
  editCategory.value = record.category
  editError.value = ''
  restoredEditDraft.value = false
  editDraftBase.value = JSON.stringify(editDraftFields())
  if (!recover) return
  try {
    const raw = sessionStorage.getItem(editDraftPrefix + record.id)
    if (!raw) return
    const draft = JSON.parse(raw)
    if (!draft || typeof draft.title !== 'string' || typeof draft.content !== 'string' || typeof draft.category !== 'string' || typeof draft.date !== 'string' || typeof draft.pendingTag !== 'string' || !Array.isArray(draft.tags) || !draft.tags.every((tag: unknown) => typeof tag === 'string')) return
    if (draft.base !== editDraftBase.value && !window.confirm('已保存的笔记在草稿之后有过更新。仍要载入这份草稿吗？')) {
      clearEditDraft(record.id)
      return
    }
    editTitle.value = draft.title
    editContent.value = draft.content
    editCategory.value = draft.category
    editNoteDate.value = draft.date
    editTags.value = draft.tags
    newTag.value = draft.pendingTag
    restoredEditDraft.value = true
  } catch { /* A damaged draft should not block editing. */ }
}

// 取消编辑
function cancelEdit() {
  persistEditDraft()
  editingId.value = null
  editDraftBase.value = ''
  restoredEditDraft.value = false
  suggestion.value = null
  editTitle.value = ''
  editNoteDate.value = ''
  editContent.value = ''
  editCategory.value = '待整理'
  editTags.value = []
  newTag.value = ''
  editError.value = ''
}

function discardEditDraft(record: KnowledgeRecord) {
  if (isSavingEdit.value || !window.confirm('放弃这篇笔记的未保存修改？')) return
  clearEditDraft(record.id)
  startEdit(record, false)
}

// 保存修改
async function saveEdit(recordId: number) {
  if (isSavingEdit.value || attachmentUploadBusy.value) return
  const content = editContent.value.trim()

  if (!content) {
    editError.value = '记录内容不能为空'
    return
  }

  addTag()
  isSavingEdit.value = true
  editError.value = ''

  try {
    const response = await recordsRequest(
      `/api/records/${recordId}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content,
          title: editTitle.value.trim(),
          note_date: editNoteDate.value || null,
          category: editCategory.value.trim() || '待整理',
          tags: editTags.value,
          ...(editAttachmentQueue.value[recordId]?.length ? { attachment_ids: editAttachmentQueue.value[recordId]!.map(file => file.id) } : {})
        })
      }
    )

    const data = await response.json()

    if (!response.ok || !data.success) {
      throw new Error(data.detail || data.message || '修改失败')
    }

    delete editAttachmentQueue.value[recordId]
    cancelEdit()
    clearEditDraft(recordId)
    const detail = linkedRecord.value?.id === recordId ? loadLinkRecord(recordId) : undefined
    await Promise.all([loadRecords(), loadCategories(), detail])

  } catch (error) {
    editError.value = error instanceof Error
      ? error.message
      : '修改失败，请检查后台服务'

  } finally {
    isSavingEdit.value = false
  }
}

// 删除记录
const pinRequests = ref(new Set<number>())

async function togglePin(record: KnowledgeRecord) {
  if (record.deletedAt || pinRequests.value.has(record.id)) return
  const pinned = !record.pinned
  pinRequests.value.add(record.id)
  try {
    const response = await recordsRequest('/api/records/' + record.id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned })
    })
    if (!response.ok) throw new Error()
    if (linkedRecord.value?.id === record.id) linkedRecord.value.pinned = pinned
    await loadRecords()
  } catch {
    if (authState.value === 'ready') window.alert('更新置顶状态失败，请重试。')
  } finally {
    pinRequests.value.delete(record.id)
  }
}

function viewNoteDay(record: KnowledgeRecord) {
  const day = record.noteDate || record.createdDay
  if (!record.deletedAt && /^\d{4}-\d{2}-\d{2}$/.test(day)) return openView('library', { day })
}

const settingsOverview = ref<{ active: number, inbox: number, pinned: number, trash: number } | null>(null)
const settingsOverviewError = ref(false)
const settingsCategory = ref('')
const renameFrom = ref('')
const categorySettingsBusy = ref(false)
const categorySettingsNotice = ref('')
const categorySettingsError = ref('')
const customCategories = computed(() => knownCategories.value.filter(category => !defaultCategories.includes(category)))

function loadDensity(): 'comfortable' | 'compact' {
  try {
    return localStorage.getItem('zhiji-list-density') === 'compact' ? 'compact' : 'comfortable'
  } catch {
    return 'comfortable'
  }
}
const listDensity = ref(loadDensity())

function saveDensity() {
  try {
    localStorage.setItem('zhiji-list-density', listDensity.value)
  } catch {
    // The chosen density still applies to the current page.
  }
}

async function loadSettingsOverview() {
  settingsOverviewError.value = false
  try {
    const response = await recordsRequest('/api/settings/overview')
    if (!response.ok) throw new Error()
    const result = await response.json()
    if (authState.value === 'ready') settingsOverview.value = result
  } catch {
    if (authState.value === 'ready') settingsOverviewError.value = true
  }
}

async function saveCategorySetting() {
  const name = settingsCategory.value.trim()
  const previous = renameFrom.value
  if (!name || categorySettingsBusy.value) return
  categorySettingsBusy.value = true
  categorySettingsNotice.value = ''
  categorySettingsError.value = ''
  try {
    const response = await recordsRequest('/api/categories' + (previous ? '/rename' : ''), {
      method: previous ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(previous ? { name, previous } : { name })
    })
    const data = await response.json()
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '无法保存分类。')
    if (authState.value === 'ready') {
      settingsCategory.value = ''
      renameFrom.value = ''
      categorySettingsNotice.value = previous ? '分类已改名，相关记录与常用搜索已同步。' : '分类已创建。'
      await Promise.all([loadCategories(), loadSavedSearches()])
    }
  } catch (error) {
    if (authState.value === 'ready') categorySettingsError.value = error instanceof Error && !(error instanceof TypeError)
      ? error.message : '无法保存分类，请重试。'
  } finally {
    categorySettingsBusy.value = false
  }
}

const trashPolicyEnabled = ref<boolean | null>(null)
const trashPolicySaving = ref(false)
const trashPolicyError = ref('')

async function loadTrashPolicy() {
  trashPolicyError.value = ''
  try {
    const response = await recordsRequest('/api/trash/policy')
    if (!response.ok) throw new Error()
    const policy = await response.json() as { enabled: boolean }
    if (authState.value === 'ready') trashPolicyEnabled.value = policy.enabled
  } catch {
    if (authState.value === 'ready') trashPolicyError.value = '无法读取自动清理设置。'
  }
}

async function toggleTrashPolicy() {
  if (trashPolicyEnabled.value === null || trashPolicySaving.value) return
  const enabled = !trashPolicyEnabled.value
  if (enabled && !window.confirm('开启后，在回收站满 30 天的记录会被永久删除，已经满 30 天的记录也会清理。确认开启吗？')) return
  trashPolicySaving.value = true
  trashPolicyError.value = ''
  try {
    const response = await recordsRequest('/api/trash/policy', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    })
    if (!response.ok) throw new Error()
    if (authState.value === 'ready') {
      trashPolicyEnabled.value = enabled
      await loadSettingsOverview()
    }
  } catch {
    if (authState.value === 'ready') trashPolicyError.value = '无法保存自动清理设置，请重试。'
  } finally {
    trashPolicySaving.value = false
  }
}

function trashExpiryLabel(deletedAt: string) {
  const deleted = Date.parse(deletedAt)
  if (Number.isNaN(deleted)) return ''
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium' }).format(deleted + 30 * 86400000)
}

const recordActionStatus = ref('')
const recordActionError = ref('')
const pendingRecordActions = ref(new Set<number>())

async function changeTrashState(record: KnowledgeRecord, action: boolean | 'purge') {
  const restore = action === true
  const purge = action === 'purge'
  if (batchMoveBusy.value || pendingRecordActions.value.has(record.id)) return
  if (purge && (!record.deletedAt || !window.confirm(`永久删除笔记「${record.title}」？删除后无法恢复。`))) return
  pendingRecordActions.value.add(record.id)
  recordActionStatus.value = ''
  recordActionError.value = ''
  try {
    const url = '/api/records/' + record.id + (restore ? '/restore' : purge ? '/trash' : '')
    const response = await recordsRequest(url, { method: restore ? 'POST' : 'DELETE' })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(typeof data.detail === 'string' ? data.detail : '操作失败，请重试。')
    }
    if (editingId.value === record.id) cancelEdit()
    if (purge && linkedRecord.value?.id === record.id) closeActiveReader()
    if (purge) batchIds.value = batchIds.value.filter(id => id !== record.id)
    recordActionStatus.value = restore ? '已恢复到原分类。' : purge ? '笔记已永久删除。' : '已移到回收站。'
    await loadRecords()
  } catch (error) {
    if (authState.value === 'ready') {
      recordActionError.value = error instanceof Error && !(error instanceof TypeError)
        ? error.message : '操作失败，请重试。'
    }
  } finally {
    pendingRecordActions.value.delete(record.id)
  }
}

interface NoteLink {
  id: number
  title?: string
  content: string
  category: string
  direction: 'incoming' | 'outgoing'
}

const linkDialog = ref<HTMLDialogElement | null>(null)
const readerHost = ref<HTMLElement | null>(null)
const detailOpen = ref(false)
const wideScreen = ref(false)
const splitReader = computed(() => wideScreen.value && detailOpen.value && activeView.value !== 'settings' && activeView.value !== 'tasks' && activeView.value !== 'attachments')
const splitCalendarControls = ref<'calendar' | 'filters' | null>(null)
watch(splitReader, () => { splitCalendarControls.value = null })
const showNoteLinks = ref(false)
const linkedRecord = ref<KnowledgeRecord | null>(null)


const readerListIndex = computed(() => records.value.findIndex(record => record.id === linkedRecord.value?.id))

async function browseAdjacentNote(direction: -1 | 1) {
  const index = readerListIndex.value
  if (index < 0 || editingId.value !== null || linkLoading.value || batchMoveIsActive.value) return
  const target = records.value[index + direction]
  if (!target) return
  const opening = openLinks(target)
  await nextTick()
  if (linkedRecord.value?.id === target.id) {
    const region = recordScrollRegion.value
    const row = region?.querySelector<HTMLElement>(`[data-record-id="${target.id}"]`)
    if (splitReader.value && region && row && region.scrollHeight > region.clientHeight) {
      const bounds = region.getBoundingClientRect()
      const rowBounds = row.getBoundingClientRect()
      if (rowBounds.top < bounds.top) region.scrollTop += rowBounds.top - bounds.top
      else if (rowBounds.bottom > bounds.bottom) region.scrollTop += rowBounds.bottom - bounds.bottom
    }
    if (splitReader.value && readerHost.value) readerHost.value.scrollTop = 0
    else if (linkDialog.value) linkDialog.value.scrollTop = 0
  }
  await opening
}
const readerFindOpen = ref(false)
const readerQuery = ref('')
const readerMatch = ref(0)
const readerSearch = ref<HTMLInputElement | null>(null)
const readerText = ref<HTMLElement | null>(null)
const readerParts = computed(() => {
  const content = linkedRecord.value?.content ?? ''
  const query = readerQuery.value.trim()
  if (!readerFindOpen.value || !query) return [{ text: content, match: -1 }]
  const literal = Array.from(query, character => /[\^$.*+?()[\]{}|]/.test(character) || character === String.fromCharCode(92) ? String.fromCharCode(92) + character : character).join('')
  const parts: { text: string, match: number }[] = []
  let offset = 0
  let match = 0
  for (const hit of content.matchAll(new RegExp(literal, 'giu'))) {
    parts.push({ text: content.slice(offset, hit.index), match: -1 }, { text: hit[0], match: match++ })
    offset = hit.index + hit[0].length
  }
  parts.push({ text: content.slice(offset), match: -1 })
  return parts
})
const readerOutline = computed(() => {
  const headings: { offset: number, level: number, title: string }[] = []
  let offset = 0
  let fence = ''
  for (const line of (linkedRecord.value?.content ?? '').split('\n')) {
    const marker = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line)
    if (marker && !fence) fence = marker[1]!
    else if (marker && marker[1]![0] === fence[0] && marker[1]!.length >= fence.length && !marker[2]!.trim()) fence = ''
    else if (!fence) {
      const heading = /^ {0,3}(#{1,6})\s+(\S.*?)\s*$/.exec(line)
      if (heading) headings.push({ offset, level: heading[1]!.length, title: heading[2]!.replace(/\s+#+$/, '') })
    }
    offset += line.length + 1
  }
  return headings
})
const readerChunks = computed(() => {
  const headings = readerOutline.value
  const chunks: { text: string, match: number, anchor?: number }[] = []
  let offset = 0
  let index = 0
  for (const part of readerParts.value) {
    const end = offset + part.text.length
    let cursor = offset
    while (index < headings.length && headings[index]!.offset < end) {
      const boundary = headings[index++]!.offset
      if (boundary > cursor) chunks.push({ text: part.text.slice(cursor - offset, boundary - offset), match: part.match })
      cursor = boundary
      chunks.push({ text: '', match: -1, anchor: boundary })
    }
    chunks.push({ text: part.text.slice(cursor - offset), match: part.match })
    offset = end
  }
  return chunks
})
function jumpToHeading(offset: number, event: MouseEvent) {
  const menu = (event.currentTarget as HTMLElement).closest('details')
  if (menu) menu.open = false
  const heading = readerText.value?.querySelector<HTMLElement>('[data-heading="' + offset + '"]')
  heading?.focus({ preventScroll: true })
  heading?.scrollIntoView({ block: 'start' })
}
const readerMatchCount = computed(() => readerParts.value.filter(part => part.match >= 0).length)
async function showReaderFind() {
  readerFindOpen.value = true
  await nextTick()
  readerSearch.value?.focus()
}
function closeReaderFind() {
  readerFindOpen.value = false
  readerQuery.value = ''
  readerMatch.value = 0
}
function revealReaderMatch() {
  readerText.value?.querySelector('[data-current-match]')?.scrollIntoView({ block: 'nearest' })
}
async function moveReaderMatch(step: number) {
  const total = readerMatchCount.value
  if (!total) return
  readerMatch.value = (readerMatch.value + step + total) % total
  await nextTick()
  revealReaderMatch()
}
watch(() => linkedRecord.value?.id, closeReaderFind)
watch(readerQuery, async () => {
  readerMatch.value = 0
  await nextTick()
  revealReaderMatch()
})

const noteLinks = ref<NoteLink[]>([])
const linkCandidates = ref<ApiRecord[]>([])
const previousLinkIds = ref<number[]>([])
const linkKeyword = ref('')
const linkError = ref('')
const linkLoading = ref(false)
const linkSearching = ref(false)
const linkSaving = ref(false)
const linkSearchText = ref('')
let linkPageVersion = 0
const outgoingLinks = computed(() => noteLinks.value.filter(link => link.direction === 'outgoing'))
const incomingLinks = computed(() => noteLinks.value.filter(link => link.direction === 'incoming'))

function linkDisplayTitle(note: { title?: string, content: string }) {
  return displayNoteTitle(note)
}

function resetLinkDialog() {
  editingTaskId.value = null
  taskEditError.value = ''
  detailOpen.value = false
  cancelEdit()
  showNoteLinks.value = false
  ++linkPageVersion
  linkedRecord.value = null
  linkedTasks.value = []
  taskTitle.value = ''
  taskDueDate.value = ''
  taskDueTime.value = ''
  taskPriority.value = 0
  taskModalError.value = ''
  noteLinks.value = []
  previousLinkIds.value = []
  linkCandidates.value = []
  linkKeyword.value = ''
  linkSearchText.value = ''
  linkError.value = ''
  linkLoading.value = false
  linkSearching.value = false
}

async function loadLinkRecord(id: number, keepVisible = false) {
  const version = ++linkPageVersion
  linkedAttachments.value = []
  linkedAttachmentsError.value = ''
  attachmentActionMessage.value = ''
  if (authState.value === 'ready') {
    void attachmentRequest('/api/attachments?record_id=' + id).then(result => {
      if (version === linkPageVersion) linkedAttachments.value = result.attachments ?? []
    }).catch(error => {
      if (version === linkPageVersion) linkedAttachmentsError.value = error instanceof Error ? error.message : '无法读取附件。'
    })
  }
  linkLoading.value = true
  if (!keepVisible) {
    linkedRecord.value = null
    linkedTasks.value = []
    taskTitle.value = ''
    taskDueDate.value = ''
  taskDueTime.value = ''
  taskPriority.value = 0
    taskModalError.value = ''
    noteLinks.value = []
  }
  linkSearching.value = false
  linkKeyword.value = ''
  linkCandidates.value = []
  linkSearchText.value = ''
  linkError.value = ''
  try {
    const result = await recordsRequest('/api/records/' + id + '/links')
    if (!result.ok) throw new Error()
    const data = await result.json() as { record: ApiRecord, links: NoteLink[], tasks?: NoteTask[] }
    if (version !== linkPageVersion || authState.value !== 'ready') return
    linkedRecord.value = formatRecord(data.record)
    noteLinks.value = data.links
    linkedTasks.value = data.tasks ?? []
  } catch {
    if (version === linkPageVersion && authState.value === 'ready') linkError.value = keepVisible ? '无法读取最新详情，正在显示列表中的内容。' : '无法打开这条记录。'
  } finally {
    if (version === linkPageVersion) linkLoading.value = false
  }
}

async function openLinks(record: KnowledgeRecord, mode: 'read' | 'edit' | 'suggest' | 'links' = 'read') {
  if (detailOpen.value && !allowReaderDismissal()) return
  resetLinkDialog()
  detailOpen.value = true
  recordActionStatus.value = ''
  recordActionError.value = ''
  linkedRecord.value = record
  showNoteLinks.value = mode === 'links'
  const dialog = linkDialog.value
  if (!splitReader.value && dialog && !dialog.open) dialog.showModal()
  await loadLinkRecord(record.id, true)
  const current = linkedRecord.value
  if (current?.id !== record.id || current.deletedAt || linkError.value) return
  if (mode === 'edit') startEdit(current)
  if (mode === 'suggest') suggestOrganization(current)
}

function openRecordFromRow(record: KnowledgeRecord, event: MouseEvent) {
  const target = event.target
  if (!(target instanceof Element) || target.closest('button, a, input, select, textarea, label, details')) return
  if (window.getSelection()?.toString()) return
  if (batchMoveIsActive.value) {
    toggleBatchRecord(record.id)
    return
  }
  void openLinks(record)
}

function closeMoreMenu(event: Event) {
  const menu = event.currentTarget
  if (!(menu instanceof HTMLDetailsElement) || !menu.open) return
  menu.open = false
  if (event instanceof KeyboardEvent) menu.querySelector('summary')?.focus()
}

function closeReviewExportAfterAction(event: MouseEvent) {
  if (event.target instanceof Element && event.target.closest('button')) closeMoreMenu(event)
}

function allowReaderDismissal() {
  if (isSavingEdit.value || taskCreating.value || activeTaskRequests.value.size) return false
  if ((editingTaskId.value !== null || taskTitle.value.trim()) && !window.confirm('待办还有未保存的内容，确定离开吗？')) return false
  const current = linkedRecord.value
  const dirty = editingId.value !== null && current && (
    editTitle.value !== current.customTitle || editContent.value !== current.content ||
    editCategory.value !== current.category || editNoteDate.value !== (current.noteDate ?? '') || JSON.stringify(editTags.value) !== JSON.stringify(current.tags) ||
    Boolean(newTag.value.trim())
  )
  return !dirty || persistEditDraft() || window.confirm('浏览器无法保留草稿。仍然关闭编辑吗？')
}

function closeActiveReader() {
  if (!allowReaderDismissal()) return false
  resetLinkDialog()
  linkDialog.value?.close()
  return true
}

function handleNoteDialogClosed() {
  if (!splitReader.value) resetLinkDialog()
}

function dismissNoteDialogOnEscape(event: Event) {
  event.preventDefault()
  closeActiveReader()
}

const backdropPresses = new WeakSet<HTMLDialogElement>()

function isBackdrop(event: MouseEvent, dialog: HTMLDialogElement) {
  if (event.target !== dialog) return false
  const { left, right, top, bottom } = dialog.getBoundingClientRect()
  return event.clientX < left || event.clientX >= right || event.clientY < top || event.clientY >= bottom
}

function trackBackdropPress(event: PointerEvent) {
  const dialog = event.currentTarget
  if (!(dialog instanceof HTMLDialogElement)) return
  backdropPresses.delete(dialog)
  if (isBackdrop(event, dialog)) backdropPresses.add(dialog)
}

function dismissBackdrop(event: MouseEvent, which: 'capture' | 'history' | 'note') {
  const dialog = event.currentTarget
  if (!(dialog instanceof HTMLDialogElement) || !backdropPresses.delete(dialog) || !isBackdrop(event, dialog)) return
  if (which === 'note') closeActiveReader()
  else if (which === 'capture' ? !captureBusy.value && !templateBusy.value : !historyBusy.value) dialog.close()
}

function closeMenusOutside(event: PointerEvent) {
  if (!(event.target instanceof Node)) return
  for (const menu of document.querySelectorAll<HTMLDetailsElement>('.export-menu[open], .record-more[open], .calendar-month-menu[open], .capture-date-menu[open], .reading-menu[open], .note-share-menu[open]')) {
    if (!menu.contains(event.target)) menu.open = false
  }
}

let readerMedia: MediaQueryList | undefined
function updateReaderWidth() {
  wideScreen.value = readerMedia?.matches ?? false
}

watch(wideScreen, async () => {
  await nextTick()
  if (!detailOpen.value) return
  const dialog = linkDialog.value
  if (!dialog) return
  if (splitReader.value && dialog.open) dialog.close()
  else if (!splitReader.value && !dialog.open) dialog.showModal()
})

function followLink(id: number) {
  if (linkedRecord.value) previousLinkIds.value.push(linkedRecord.value.id)
  return loadLinkRecord(id)
}

function goBackInLinks() {
  const id = previousLinkIds.value.pop()
  if (id !== undefined) return loadLinkRecord(id)
}

async function searchLinkCandidates() {
  const source = linkedRecord.value
  const keyword = linkKeyword.value.trim()
  if (!source || !keyword || linkSearching.value) return
  const version = linkPageVersion
  linkSearching.value = true
  linkError.value = ''
  linkSearchText.value = ''
  linkCandidates.value = []
  try {
    const response = await recordsRequest('/api/records/search?' + new URLSearchParams({ q: keyword }))
    if (!response.ok) throw new Error()
    const data = await response.json() as { records: ApiRecord[] }
    if (version !== linkPageVersion) return
    const existing = new Set(outgoingLinks.value.map(link => link.id))
    linkCandidates.value = data.records.filter(record => record.id !== source.id && !existing.has(record.id)).slice(0, 8)
    linkSearchText.value = keyword
  } catch {
    if (version === linkPageVersion && authState.value === 'ready') linkError.value = '无法查找可关联的记录。'
  } finally {
    if (version === linkPageVersion) linkSearching.value = false
  }
}

async function changeLink(target: number, method: 'PUT' | 'DELETE', direction: 'incoming' | 'outgoing' = 'outgoing') {
  const source = linkedRecord.value
  if (!source || linkSaving.value) return
  const version = linkPageVersion
  const sourceId = direction === 'incoming' ? target : source.id
  const targetId = direction === 'incoming' ? source.id : target
  linkSaving.value = true
  linkError.value = ''
  try {
    const response = await recordsRequest('/api/records/' + sourceId + '/links/' + targetId, { method })
    if (!response.ok) throw new Error()
    if (version === linkPageVersion) await loadLinkRecord(source.id)
  } catch {
    if (version === linkPageVersion && authState.value === 'ready') linkError.value = '无法更新这条关联。'
  } finally {
    linkSaving.value = false
  }
}

interface RecordVersion {
  id: number
  note_date?: string | null
  captured_at: string
  title: string
  content: string
  summary: string
  category: string
  tags: string
}

const historyDialog = ref<HTMLDialogElement | null>(null)
const historyRecord = ref<KnowledgeRecord | null>(null)
const versions = ref<RecordVersion[]>([])
const versionId = ref<number | null>(null)
const selectedVersion = computed(() => versions.value.find(version => version.id === versionId.value))
const historyLoading = ref(false)
const historyBusy = ref(false)
const historyError = ref('')
const historyStatus = ref('')
let historyRequest = 0

function clearHistory() {
  ++historyRequest
  historyRecord.value = null
  versions.value = []
  versionId.value = null
  historyError.value = ''
  historyStatus.value = ''
  historyLoading.value = false
}

async function loadHistory(recordId: number) {
  const request = ++historyRequest
  historyLoading.value = true
  historyError.value = ''
  try {
    const response = await recordsRequest('/api/records/' + recordId + '/versions')
    if (!response.ok) throw new Error()
    const data = await response.json() as { record: ApiRecord, versions: RecordVersion[] }
    if (request !== historyRequest || authState.value !== 'ready') return
    historyRecord.value = formatRecord(data.record)
    versions.value = data.versions
    versionId.value = data.versions[0]?.id ?? null
  } catch {
    if (request === historyRequest && authState.value === 'ready') historyError.value = '无法读取历史版本，请重试。'
  } finally {
    if (request === historyRequest) historyLoading.value = false
  }
}

function openHistory(record: KnowledgeRecord) {
  clearHistory()
  historyDialog.value?.showModal()
  return loadHistory(record.id)
}

async function restoreSelectedVersion() {
  const record = historyRecord.value
  const version = selectedVersion.value
  if (!record || !version || historyBusy.value) return
  if (!window.confirm('恢复选中的版本？恢复前会保存当前内容。')) return
  const request = historyRequest
  historyBusy.value = true
  historyError.value = ''
  historyStatus.value = ''
  try {
    const response = await recordsRequest('/api/records/' + record.id + '/versions/' + version.id + '/restore', { method: 'POST' })
    if (!response.ok) throw new Error()
    if (editingId.value === record.id) cancelEdit()
    if (request === historyRequest) {
      historyStatus.value = '已恢复，原来的内容仍可从历史中找回。'
      await loadHistory(record.id)
    }
    if (authState.value === 'ready') {
      const detail = linkedRecord.value?.id === record.id ? loadLinkRecord(record.id) : undefined
      await Promise.all([loadRecords(), loadCategories(), detail])
    }
  } catch {
    if (request === historyRequest && authState.value === 'ready') historyError.value = '恢复失败，请重试。'
  } finally {
    historyBusy.value = false
  }
}

async function copyRecordText(record: KnowledgeRecord) {
  recordActionStatus.value = ''
  recordActionError.value = ''
  try {
    await navigator.clipboard.writeText(record.content)
    recordActionStatus.value = '已复制原文。'
  } catch {
    recordActionError.value = '浏览器未允许访问剪贴板。你可以选中文字手动复制。'
  }
}

const noteShareStatus = ref('')
watch(() => linkedRecord.value?.id, () => { noteShareStatus.value = '' })

function plainNoteText(content: string) {
  let fence = ''
  return content.split('\n').map(line => {
    const token = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line)
    if (fence) {
      if (token && token[1]![0] === fence[0] && token[1]!.length >= fence.length && !token[2]!.trim()) {
        fence = ''
        return null
      }
      return line
    }
    if (token) { fence = token[1]!; return null }
    return line.replace(/^ {0,3}(?:#{1,6}|>)[ \t]+/, '')
      .replace(/^([-*])[ \t]+\[([ xX])\][ \t]*/, (_, _bullet, checked) => checked === ' ' ? '☐ ' : '☑ ')
      .replace(/^[-*][ \t]+/, '• ')
  }).filter(line => line !== null).join('\n')
}

async function shareNote(record: KnowledgeRecord, action: 'plain' | 'markdown' | 'text', event: MouseEvent) {
  const menu = (event.currentTarget as HTMLElement).closest('details')
  if (menu) menu.open = false
  const noteId = record.id
  noteShareStatus.value = ''
  const body = action === 'markdown' ? record.content : plainNoteText(record.content)
  try {
    if (action === 'plain') {
      await navigator.clipboard.writeText(body)
      if (linkedRecord.value?.id === noteId) noteShareStatus.value = '已复制正文纯文本。'
      return
    }
    const title = record.customTitle.trim().replace(/\s+/g, ' ')
    const text = title && title !== body.trim() ? (action === 'markdown' ? '# ' : '') + title + '\n\n' + body : body
    const filename = Array.from(record.title.replace(/[<>:"/\\|?*\u0000-\u001f]/g, ' ').replace(/[.\s]+$/, '').trim()).slice(0, 70).join('') || '知己笔记'
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = '知己-' + filename + (action === 'markdown' ? '.md' : '.txt')
    try { link.click() } finally { setTimeout(() => URL.revokeObjectURL(url), 1000) }
    noteShareStatus.value = '已发起文件下载。'
  } catch {
    if (linkedRecord.value?.id === noteId) noteShareStatus.value = action === 'plain' ? '无法访问剪贴板，可选中文字手动复制。' : '无法下载，请重试。'
  }
}

async function duplicateRecord(record: KnowledgeRecord) {
  if (pendingRecordActions.value.has(record.id)) return
  pendingRecordActions.value.add(record.id)
  recordActionStatus.value = ''
  recordActionError.value = ''
  try {
    const response = await recordsRequest('/api/records/' + record.id + '/duplicate', { method: 'POST' })
    if (!response.ok) throw new Error()
    const result = await response.json() as { title: string }
    if (authState.value === 'ready') {
      recordActionStatus.value = '已创建「' + result.title + '」。'
      await loadRecords()
    }
  } catch {
    if (authState.value === 'ready') recordActionError.value = '无法创建副本，请重试。'
  } finally {
    pendingRecordActions.value.delete(record.id)
  }
}

interface ImportFile {
  name: string
  title: string
  content: string
}
const maxImportFiles = 30
const importFiles = ref<ImportFile[]>([])
const importWarnings = ref<string[]>([])
const importTargetCategory = ref('待整理')
const importLoading = ref(false)
const importBusy = ref(false)
const importStatus = ref('')
const importError = ref('')
let importSelection = 0

function resetImport() {
  ++importSelection
  importFiles.value = []
  importWarnings.value = []
  importTargetCategory.value = '待整理'
  importLoading.value = false
  importStatus.value = ''
  importError.value = ''
}

async function prepareImport(event: Event) {
  const input = event.target as HTMLInputElement
  const chosen = Array.from(input.files ?? [])
  input.value = ''
  if (!chosen.length) return
  const version = ++importSelection
  importFiles.value = []
  importWarnings.value = []
  importStatus.value = ''
  importError.value = ''
  importLoading.value = true

  const decoder = new TextDecoder('utf-8', { fatal: true })
  const warnings: string[] = []
  const ready: ImportFile[] = []
  if (chosen.length > maxImportFiles) warnings.push('一次最多导入 30 个文件，已预读前 30 个。')

  for (const file of chosen.slice(0, maxImportFiles)) {
    if (version !== importSelection) return
    if (!/\.(md|txt)$/i.test(file.name)) {
      warnings.push(file.name + '：请选择 Markdown 或纯文本文件。')
      continue
    }
    if (file.size > 40003) {
      warnings.push(file.name + '：文件过长，请拆成多条笔记。')
      continue
    }
    try {
      const content = decoder.decode(await file.arrayBuffer()).trim()
      if (!content || Array.from(content).length > 10000) {
        warnings.push(file.name + (content ? '：正文超过 10,000 个字符。' : '：文件没有正文。'))
        continue
      }
      const heading = /\.md$/i.test(file.name) ? /^#\s+([^\r\n]+)/.exec(content)?.[1]?.trim() : ''
      const filename = file.name.replace(/\.(md|txt)$/i, '').trim()
      const title = Array.from(heading || filename).slice(0, 200).join('')
      ready.push({ name: file.name, title, content })
    } catch {
      warnings.push(file.name + '：无法读取，请保存为 UTF-8 编码后重试。')
    }
  }

  if (version === importSelection) {
    importFiles.value = ready
    importWarnings.value = warnings
    importLoading.value = false
  }
}

async function importNotes() {
  if (!importFiles.value.length || importLoading.value || importBusy.value) return
  const category = importTargetCategory.value.trim() || '待整理'
  importBusy.value = true
  importStatus.value = ''
  importError.value = ''
  try {
    const response = await recordsRequest('/api/records/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        records: importFiles.value.map(({ title, content }) => ({ title, content, category }))
      })
    })
    if (!response.ok) throw new Error()
    const result = await response.json() as { imported: number, skipped: number }
    if (authState.value !== 'ready') return
    importFiles.value = []
    importWarnings.value = []
    importStatus.value = '已导入 ' + result.imported + ' 条，跳过 ' + result.skipped + ' 条重复正文。'
    if (activeView.value === 'settings') await Promise.all([loadSettingsOverview(), loadCategories()])
    else await Promise.all([loadRecords(), loadCategories()])
  } catch {
    if (authState.value === 'ready') importError.value = '导入失败，请检查本地服务后重试。'
  } finally {
    importBusy.value = false
  }
}

const librarySearchInput = ref<HTMLInputElement | null>(null)

async function focusLibrarySearch(event: KeyboardEvent) {
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'k' || event.isComposing ||
      authState.value !== 'ready' || captureDialog.value?.open || linkDialog.value?.open || historyDialog.value?.open) return
  event.preventDefault()
  if (activeView.value !== 'library') void openView('library')
  else if (calendarVisible.value) void changeLibraryMode('list')
  await nextTick()
  librarySearchInput.value?.focus()
  librarySearchInput.value?.select()
}

async function shortcutNewNote(event: KeyboardEvent) {
  if (event.defaultPrevented || event.repeat || event.isComposing || event.getModifierState?.('AltGraph')) return
  if (!event.ctrlKey || !event.altKey || event.shiftKey || event.metaKey || event.code !== 'KeyN') return
  if (authState.value !== 'ready' || activeView.value !== 'library' || detailOpen.value || batchMoveIsActive.value ||
    changingPassword.value || captureDialog.value?.open || historyDialog.value?.open || reviewDialog.value?.open) return
  if (event.target instanceof HTMLElement && (event.target.isContentEditable || event.target.closest('input, textarea, select'))) return
  event.preventDefault()
  await openCapture()
}

interface NoteTask {
  id: number
  record_id: number
  title: string
  due_date: string | null
  due_time: string | null
  priority: number
  completed_at: string | null
  record_title: string
}

const allTasks = ref<NoteTask[]>([])
const linkedTasks = ref<NoteTask[]>([])
const taskTitle = ref('')
const taskDueDate = ref('')
const taskDueTime = ref('')
const taskPriority = ref(0)
watch(taskDueDate, day => { if (!day) taskDueTime.value = '' })
const taskClock = ref(new Date())
let taskClockTimer: ReturnType<typeof setInterval> | undefined
const taskToday = computed(() => localDateKey(taskClock.value))
const taskDay = ref(localDateKey())
const taskPeriod = ref<'all' | 'today' | 'week' | 'overdue' | 'unscheduled' | 'date'>('all')
const taskCalendarOpen = ref(false)
const taskSearch = ref('')
const taskBatchMode = ref(false)
const selectedTaskIds = ref<number[]>([])
const taskBatchBusy = ref(false)
const taskBatchDate = ref('')
const taskBatchTime = ref('')
const taskBatchNotice = ref('')
watch(taskBatchDate, day => { if (!day) taskBatchTime.value = '' })
const editingTaskId = ref<number | null>(null)
const taskEditError = ref('')
const taskCreating = ref(false)
const taskPageError = ref('')
const taskModalError = ref('')
const tasksLoading = ref(false)
const tasksLoadError = ref('')
const taskFilter = ref<'pending' | 'completed' | 'all'>('pending')
watch([taskFilter, taskPeriod, taskDay, taskSearch, activeView], () => {
  selectedTaskIds.value = []
  taskBatchNotice.value = ''
})
const pendingTasksCount = computed(() => allTasks.value.filter(task => !task.completed_at).length)
const taskCompletion = computed(() => allTasks.value.length ? Math.round((allTasks.value.length - pendingTasksCount.value) / allTasks.value.length * 100) : 0)
const overdueTasksCount = computed(() => allTasks.value.filter(isOverdue).length)
const statusTasks = computed(() => allTasks.value.filter(task =>
  (taskFilter.value === 'all' || Boolean(task.completed_at) === (taskFilter.value === 'completed')) &&
  (!taskSearch.value.trim() || (task.title + ' ' + task.record_title).toLocaleLowerCase().includes(taskSearch.value.trim().toLocaleLowerCase()))
))
const taskCalendarCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const task of statusTasks.value) {
    if (task.due_date?.startsWith(taskDay.value.slice(0, 7))) counts[task.due_date] = (counts[task.due_date] ?? 0) + 1
  }
  return counts
})
const displayedTasks = computed(() => statusTasks.value.filter(task => {
  if (taskPeriod.value === 'today') return task.due_date === taskToday.value
  if (taskPeriod.value === 'overdue') return isOverdue(task)
  if (taskPeriod.value === 'unscheduled') return !task.due_date
  if (taskPeriod.value === 'date') return task.due_date === taskDay.value
  if (taskPeriod.value === 'week') {
    const end = new Date(taskClock.value)
    end.setDate(end.getDate() + 6)
    return Boolean(task.due_date && task.due_date >= taskToday.value && task.due_date <= localDateKey(end))
  }
  return true
}))
function selectTaskDay(day: string) {
  taskDay.value = day
  taskPeriod.value = 'date'
}
function startTaskEdit(task: NoteTask) {
  if (editingTaskId.value !== null && editingTaskId.value !== task.id && !window.confirm('要放弃当前待办未保存的修改吗？')) return
  editingTaskId.value = task.id
  taskEditError.value = ''
}
async function applyTaskBatch(action: 'complete' | 'reopen' | 'reschedule', clearDate = false) {
  const visibleIds = new Set(displayedTasks.value.map(task => task.id))
  const ids = selectedTaskIds.value.filter(id => visibleIds.has(id))
  if (!ids.length || taskBatchBusy.value) return
  if (action === 'reschedule' && !clearDate && !taskBatchDate.value) {
    taskPageError.value = '请先选择要移到的日期。'
    return
  }
  if (action === 'reschedule' && !window.confirm(clearDate ? `取消这 ${ids.length} 项待办的日期和时间？` : `将这 ${ids.length} 项待办统一改到 ${taskBatchDate.value} ${taskBatchTime.value}？`)) return
  taskBatchBusy.value = true
  taskPageError.value = ''
  taskBatchNotice.value = ''
  try {
    const response = await recordsRequest('/api/tasks/batch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids, action, due_date: action === 'reschedule' && !clearDate ? taskBatchDate.value : null,
        due_time: action === 'reschedule' && !clearDate ? taskBatchTime.value || null : null })
    })
    if (!response.ok) {
      if (response.status === 409) throw new Error('部分待办已变化，本次没有修改任何待办，请刷新后重新选择。')
      throw new Error('批量操作失败，请重试。')
    }
    selectedTaskIds.value = []
    taskBatchNotice.value = `已${action === 'complete' ? '完成' : action === 'reopen' ? '恢复为待完成' : clearDate ? '取消日期' : '改期'} ${ids.length} 项待办。`
    await loadTasks()
    if (linkedRecord.value) await loadLinkRecord(linkedRecord.value.id, true)
  } catch (error) {
    if (authState.value === 'ready') taskPageError.value = error instanceof Error ? error.message : '批量操作失败，请重试。'
  } finally {
    taskBatchBusy.value = false
  }
}
async function saveTaskDetails(task: NoteTask, details: { title: string, due_date: string | null, due_time: string | null, priority: number }) {
  if (activeTaskRequests.value.has(task.id)) return
  activeTaskRequests.value.add(task.id)
  taskEditError.value = ''
  try {
    const response = await recordsRequest('/api/tasks/' + task.id, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(details)
    })
    if (!response.ok) throw new Error()
    editingTaskId.value = null
    await refreshTaskViews(task.record_id)
  } catch {
    taskEditError.value = '保存失败，修改内容已保留，请重试。'
  } finally {
    activeTaskRequests.value.delete(task.id)
  }
}
const activeTaskRequests = ref(new Set<number>())
let taskRequest = 0

function isOverdue(task: NoteTask) {
  if (task.completed_at || !task.due_date) return false
  if (task.due_date !== taskToday.value) return task.due_date < taskToday.value
  const clockTime = String(taskClock.value.getHours()).padStart(2, '0') + ':' + String(taskClock.value.getMinutes()).padStart(2, '0')
  return Boolean(task.due_time && task.due_time < clockTime)
}

async function loadTasks() {
  const request = ++taskRequest
  tasksLoading.value = true
  tasksLoadError.value = ''
  try {
    const response = await recordsRequest('/api/tasks')
    if (!response.ok) throw new Error()
    const result = await response.json() as { tasks: NoteTask[] }
    if (request === taskRequest && authState.value === 'ready') allTasks.value = result.tasks
  } catch {
    if (request === taskRequest && authState.value === 'ready') tasksLoadError.value = '无法读取待办事项。'
  } finally {
    if (request === taskRequest) tasksLoading.value = false
  }
}

async function openTaskSource(task: NoteTask) { return openSourceNote(task.record_id) }

async function openSourceNote(recordId: number) {
  if (detailOpen.value && !allowReaderDismissal()) return
  resetLinkDialog()
  detailOpen.value = true
  const dialog = linkDialog.value
  if (!splitReader.value && dialog && !dialog.open) dialog.showModal()
  await loadLinkRecord(recordId)
}

async function createTaskForNote() {
  const record = linkedRecord.value
  const title = taskTitle.value.trim()
  if (!record || record.deletedAt || !title || taskCreating.value) return
  taskCreating.value = true
  taskModalError.value = ''
  try {
    const response = await recordsRequest('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ record_id: record.id, title, due_date: taskDueDate.value || null,
        due_time: taskDueDate.value ? taskDueTime.value || null : null, priority: taskPriority.value })
    })
    if (!response.ok) throw new Error()
    if (linkedRecord.value?.id === record.id) {
      taskTitle.value = ''
      taskDueDate.value = ''
  taskDueTime.value = ''
  taskPriority.value = 0
    }
    await refreshTaskViews(record.id)
  } catch {
    if (authState.value === 'ready' && linkedRecord.value?.id === record.id) taskModalError.value = '添加待办失败，请重试。'
  } finally {
    taskCreating.value = false
  }
}

async function refreshTaskViews(recordId: number) {
  if (authState.value !== 'ready') return
  const tasks = activeView.value === 'tasks' ? loadTasks() : undefined
  const note = linkedRecord.value?.id === recordId ? loadLinkRecord(recordId, true) : undefined
  await Promise.all([tasks, note])
}

async function changeTask(task: NoteTask, remove = false) {
  if (activeTaskRequests.value.has(task.id)) return
  if (remove && !window.confirm('移除这项待办？原笔记仍会保留。')) return
  activeTaskRequests.value.add(task.id)
  taskPageError.value = ''
  taskModalError.value = ''
  try {
    const response = await recordsRequest('/api/tasks/' + task.id, remove ? { method: 'DELETE' } : {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ completed: !task.completed_at })
    })
    if (!response.ok) throw new Error()
    await refreshTaskViews(task.record_id)
  } catch {
    if (authState.value === 'ready') {
      if (activeView.value === 'tasks') taskPageError.value = '更新待办失败，请重试。'
      if (linkedRecord.value?.id === task.record_id) taskModalError.value = '更新待办失败，请重试。'
    }
  } finally {
    activeTaskRequests.value.delete(task.id)
  }
}

onMounted(() => {
  taskClockTimer = setInterval(() => { taskClock.value = new Date() }, 30000)
  readerMedia = window.matchMedia('(min-width: 1180px)')
  updateReaderWidth()
  readerMedia.addEventListener('change', updateReaderWidth)
  void checkAuth()
  window.addEventListener('keydown', focusLibrarySearch)
  window.addEventListener('keydown', shortcutNewNote)
  document.addEventListener('pointerdown', closeMenusOutside)
})
onUnmounted(() => {
  clearInterval(taskClockTimer)
  readerMedia?.removeEventListener('change', updateReaderWidth)
  window.removeEventListener('keydown', focusLibrarySearch)
  window.removeEventListener('keydown', shortcutNewNote)
  document.removeEventListener('pointerdown', closeMenusOutside)
})

</script>

<template>
  <main v-if="authState !== 'ready'" class="auth-screen">
    <section class="auth-card">
      <img class="brand-logo" :src="bookIcon" alt="" />
      <h1>{{ authState === 'setup' ? '设置知己密码' : '知己个人知识库' }}</h1>
      <p v-if="authState === 'loading'" role="status">正在连接知己…</p>
      <template v-else-if="authState === 'offline'">
        <p role="alert">无法连接本地服务，请重新启动知己后重试。</p>
        <button class="submit-button" @click="checkAuth">重试</button>
      </template>
      <form v-else @submit.prevent="authAction(authState === 'setup' ? 'setup' : 'login')">
        <label>
          密码
          <input v-model="password" type="password" required maxlength="128"
            :minlength="authState === 'setup' ? 8 : 1"
            :autocomplete="authState === 'setup' ? 'new-password' : 'current-password'" />
        </label>
        <label v-if="authState === 'setup'">
          确认密码（至少 8 个字符）
          <input v-model="confirmPassword" type="password" required minlength="8" maxlength="128" autocomplete="new-password" />
        </label>
        <p v-if="authError" class="search-error" role="alert">{{ authError }}</p>
        <button class="submit-button" :disabled="authBusy">
          {{ authState === 'setup' ? '设置密码并登录' : '登录' }}
        </button>
      </form>
    </section>
  </main>
  <div v-else class="app-shell" :class="{ 'compact-records': listDensity === 'compact' }">
    <!-- 左侧导航栏 -->
    <aside class="sidebar">
      <div class="brand">
        <img class="brand-logo" :src="bookIcon" alt="" />
        <div>
          <div class="brand-name">知己</div>
          <div class="brand-subtitle">个人知识空间</div>
        </div>
      </div>

      <div class="nav-caption">工作空间</div>

      <button
        v-for="view in sidebarViews"
        :key="view.id"
        type="button"
        class="nav-item view-button"
        :class="{ active: activeView === view.id }"
        :aria-current="activeView === view.id ? 'page' : undefined"
        :aria-label="view.label"
        :title="view.label"
        @click="openView(view.id)"
      >
        <AppIcon class="nav-icon" :name="view.id" />
        <span>{{ view.label }}</span>
      </button>
      <div class="sidebar-footnote">让想法有处安放</div>
    </aside>

    <!-- 右侧主工作区 -->
    <main class="main-area">
      <header class="topbar">
        <div class="breadcrumb">
          我的空间 <span>/</span> {{ viewDetails.label }}
        </div>
        <div class="topbar-right">
          <span v-if="isDevelopmentPreview" class="preview-label">开发预览</span>
          <button class="search-clear" :disabled="authBusy" @click="resetAuthForm(); changingPassword = !changingPassword">
            {{ changingPassword ? '取消修改' : '修改密码' }}
          </button>
          <button class="search-clear" :disabled="authBusy" @click="authAction('logout')">退出登录</button>
        </div>
      </header>

      <div class="content" :class="{ 'split-content': splitReader }">
        <form v-if="changingPassword" class="auth-card password-form" @submit.prevent="authAction('password')">
          <label>当前密码
            <input v-model="password" type="password" required maxlength="128" autocomplete="current-password" />
          </label>
          <label>新密码（至少 8 个字符）
            <input v-model="newPassword" type="password" required minlength="8" maxlength="128" autocomplete="new-password" />
          </label>
          <label>确认新密码
            <input v-model="confirmPassword" type="password" required minlength="8" maxlength="128" autocomplete="new-password" />
          </label>
          <button class="submit-button" :disabled="authBusy">保存密码</button>
        </form>
        <p v-if="authError" class="search-error" role="alert">{{ authError }}</p>
        <section v-if="activeView === 'settings'" class="recent-card settings-page">
          <h1>设置</h1>

          <section class="settings-section">
            <h2>数据概览</h2>
            <dl v-if="settingsOverview" class="settings-counts">
              <div><dt>知识库记录</dt><dd>{{ settingsOverview.active }}</dd></div>
              <div><dt>待整理</dt><dd>{{ settingsOverview.inbox }}</dd></div>
              <div><dt>已置顶</dt><dd>{{ settingsOverview.pinned }}</dd></div>
              <div><dt>回收站</dt><dd>{{ settingsOverview.trash }}</dd></div>
            </dl>
            <p v-if="settingsOverviewError" class="search-error" role="alert">无法读取数据概览。</p>
          </section>

          <section class="settings-section">
            <h2>分类管理</h2>
            <form class="settings-fields" @submit.prevent="saveCategorySetting">
              <select v-model="renameFrom" class="category-filter" aria-label="分类操作" :disabled="categorySettingsBusy">
                <option value="">新建分类</option>
                <option v-for="category in customCategories" :key="category" :value="category">重命名「{{ category }}」</option>
              </select>
              <input v-model="settingsCategory" class="category-filter" aria-label="分类名称" maxlength="50"
                :placeholder="renameFrom ? '输入新的分类名称' : '输入分类名称'" :disabled="categorySettingsBusy" />
              <button class="search-submit" :disabled="!settingsCategory.trim() || categorySettingsBusy">
                {{ renameFrom ? '保存名称' : '创建分类' }}
              </button>
            </form>
            <p v-if="categorySettingsNotice" class="search-result-tip" role="status">{{ categorySettingsNotice }}</p>
            <p v-if="categorySettingsError" class="search-error" role="alert">{{ categorySettingsError }}</p>
          </section>

          <section class="settings-section">
            <h2>列表显示</h2>
            <label class="settings-fields">
              列表密度
              <select v-model="listDensity" class="category-filter" @change="saveDensity">
                <option value="comfortable">舒展</option>
                <option value="compact">紧凑</option>
              </select>
            </label>
          </section>

          <section class="settings-section">
            <h2>导入笔记</h2>
            <p class="section-description">支持 UTF-8 的 Markdown（.md）和纯文本（.txt）。每个文件导入为一条笔记，一次最多 30 个。</p>
            <div class="settings-fields import-fields">
              <label class="import-file-label">
                <span>选择文件</span>
                <input type="file" multiple accept=".md,.txt" :disabled="importBusy" @change="prepareImport" />
              </label>
              <CategoryPicker v-if="importFiles.length" v-model="importTargetCategory" :categories="categories"
                label="导入分类" :disabled="importBusy" />
            </div>
            <p v-if="importLoading" class="section-description" role="status">正在读取文件…</p>
            <ul v-if="importWarnings.length" class="import-warnings">
              <li v-for="warning in importWarnings" :key="warning">{{ warning }}</li>
            </ul>
            <div v-if="importFiles.length" class="import-review">
              <p class="section-description">待导入 {{ importFiles.length }} 条，现有的相同正文会跳过。</p>
              <details v-for="(file, index) in importFiles" :key="index">
                <summary>{{ file.title || file.name }}</summary>
                <p>{{ file.content }}</p>
              </details>
              <button type="button" class="search-submit" :disabled="importBusy" @click="importNotes">
                {{ importBusy ? '正在导入…' : '导入这些笔记' }}
              </button>
              <button type="button" class="search-clear" :disabled="importBusy" @click="resetImport">清空待导入</button>
            </div>
            <p v-if="importStatus" class="search-result-tip" role="status">{{ importStatus }}</p>
            <p v-if="importError" class="search-error" role="alert">{{ importError }}</p>
          </section>

          <section class="settings-section">
            <h2>附件存储</h2>
            <p class="section-description">当前目录：{{ attachmentStorageLabel }}</p>
            <button v-if="!attachmentStoragePath && !attachmentStorageLoading && attachmentStorageStatus" type="button" class="search-clear" @click="loadAttachmentStorage">重新读取</button>
            <form class="settings-fields" @submit.prevent="changeAttachmentStorage()">
              <button type="button" class="search-clear" aria-controls="attachment-folder-picker" :aria-expanded="attachmentFolderPickerOpen"
                :disabled="attachmentStorageBusy || !attachmentStoragePath" @click="toggleAttachmentFolderPicker">选择文件夹</button>
              <button class="search-submit" :disabled="attachmentStorageBusy || attachmentFolderPickerOpen || !attachmentStoragePath || !attachmentPathInput || attachmentPathInput === attachmentStoragePath">迁移并切换</button>
              <button type="button" class="search-clear" :disabled="attachmentStorageBusy || !attachmentDefaultPath || attachmentDefaultPath === attachmentStoragePath" @click="changeAttachmentStorage(true)">使用默认目录</button>
              <button type="button" class="search-clear" :disabled="attachmentStorageBusy || !attachmentStoragePath" @click="changeAttachmentStorage(false, true)">整理现有文件名</button>
            </form>
            <p v-if="attachmentPathInput" class="section-description attachment-folder-path">已选择：{{ attachmentPathInput }}</p>
            <section v-if="attachmentFolderPickerOpen" id="attachment-folder-picker" class="attachment-folder-picker" aria-label="选择附件存放文件夹">
              <div class="settings-fields">
                <button v-if="attachmentFolderList?.path" type="button" class="search-clear" :disabled="attachmentFoldersLoading" @click="browseAttachmentFolders(attachmentFolderList.parent)">上一级</button>
                <strong class="attachment-folder-path">{{ attachmentFolderList?.path || '此电脑' }}</strong>
              </div>
              <p v-if="attachmentFoldersLoading" class="section-description" role="status">正在读取文件夹…</p>
              <p v-if="attachmentFoldersError" class="section-description" role="alert">{{ attachmentFoldersError }}</p>
              <ul v-if="attachmentFolderList?.folders.length" class="attachment-folder-list">
                <li v-for="folder in attachmentFolderList.folders" :key="folder.path">
                  <button type="button" class="search-clear" :disabled="attachmentFoldersLoading" @click="browseAttachmentFolders(folder.path)">{{ folder.name }} <span aria-hidden="true">›</span></button>
                </li>
              </ul>
              <p v-else-if="attachmentFolderList && !attachmentFoldersLoading && !attachmentFoldersError" class="section-description">没有子文件夹。</p>
              <button type="button" class="search-submit" :disabled="attachmentFoldersLoading || !attachmentFolderList?.path || attachmentFolderList.path === attachmentStoragePath" @click="selectAttachmentFolder">使用此文件夹</button>
            </section>
            <p v-if="attachmentStorageStatus" class="search-result-tip" role="status">{{ attachmentStorageStatus }}</p>
          </section>

          <section class="settings-section">
            <h2>本地备份</h2>
            <p class="section-description">下载含笔记、待办、每日回顾、历史版本和关联的 SQLite 数据库副本。</p>
            <button type="button" class="search-clear" :disabled="backupBusy" @click="downloadDatabaseBackup">
              {{ backupBusy ? '正在生成…' : '下载 SQLite 备份' }}
            </button>
            <a class="search-clear attachment-action" href="/api/settings/full-backup" target="_blank" rel="noopener">下载笔记与附件 ZIP</a>
            <p v-if="backupMessage" class="search-result-tip" role="status">{{ backupMessage }}</p>
            <p v-if="backupError" class="search-error" role="alert">{{ backupError }}</p>
          </section>

          <section class="settings-section">
            <h2>回收站</h2>
          <div class="trash-policy">
            <label>
              <input type="checkbox" :checked="trashPolicyEnabled === true"
                :disabled="trashPolicyEnabled === null || trashPolicySaving"
                @click.prevent="toggleTrashPolicy" />
              30 天后自动清理
            </label>
            <p>从移入回收站时算起，满 30 天后永久删除。</p>
            <p v-if="trashPolicyError" class="search-error" role="alert">{{ trashPolicyError }}</p>
          </div>
          </section>
        </section>

        <!-- 最近记录 -->
        <section v-else-if="activeView === 'attachments' || (activeView === 'trash' && attachmentTrashVisible)" class="recent-card attachment-page">
          <header class="recent-heading">
            <div class="library-heading"><h1>{{ attachmentTrashVisible ? '回收站' : '附件库' }}</h1><p class="section-description">{{ visibleAttachments.length }} 个文件</p></div>
            <div class="settings-fields">
              <button v-if="!attachmentTrashVisible" type="button" class="search-clear" :disabled="libraryAttachmentsLoading || attachmentActionBusy" @click="toggleAttachmentTrash">附件回收站</button>
              <button type="button" class="search-clear" :disabled="libraryAttachmentsLoading || attachmentActionBusy" @click="loadAttachmentLibrary">刷新</button>
            </div>
          </header>
          <nav v-if="attachmentTrashVisible" class="settings-fields attachment-filters" aria-label="回收站类型">
            <button type="button" class="search-clear" :disabled="attachmentActionBusy" @click="openView('trash')">笔记</button>
            <button type="button" class="search-submit" aria-current="page">附件</button>
          </nav>
          <div class="settings-fields attachment-filters">
            <input v-model="attachmentQuery" type="search" class="category-filter" aria-label="搜索附件文件名" placeholder="搜索文件名" />
            <select v-model="attachmentKind" class="category-filter" aria-label="附件类型">
              <option value="">全部类型</option><option>图片</option><option>PDF</option><option>视频</option><option>其他文件</option>
            </select>
            <label v-if="!attachmentTrashVisible" class="section-description"><input v-model="onlyUnlinkedAttachments" type="checkbox" /> 只看未关联</label>
          </div>
          <p v-if="attachmentActionMessage" role="status" class="section-description">{{ attachmentActionMessage }}</p>
          <div v-if="attachmentTrashVisible && !libraryAttachmentsLoading && !libraryAttachmentsError && visibleAttachments.length" class="settings-fields attachment-filters">
            <button type="button" class="search-clear" :disabled="attachmentActionBusy" @click="toggleAllTrashAttachments">{{ allVisibleTrashAttachmentsSelected ? '取消全选' : '全选' }}</button>
            <span class="section-description">已选 {{ visibleSelectedAttachments.length }} 个</span>
            <button type="button" class="search-clear" :disabled="attachmentActionBusy || !visibleSelectedAttachments.length" @click="changeAttachmentsTrash(visibleSelectedAttachments, 'restore')">恢复所选</button>
            <button type="button" class="search-clear" :disabled="attachmentActionBusy || !visibleSelectedAttachments.length" @click="changeAttachmentsTrash(visibleSelectedAttachments, 'purge')">永久删除所选</button>
          </div>
          <p v-if="libraryAttachmentsLoading" role="status" class="section-description">正在读取附件…</p>
          <p v-else-if="libraryAttachmentsError" role="alert" class="search-error">{{ libraryAttachmentsError }}</p>
          <p v-else-if="!visibleAttachments.length" class="empty-state">{{ attachmentLibrary.length ? '没有匹配的附件。' : attachmentTrashVisible ? '附件回收站是空的。' : '还没有附件。新建或编辑笔记时可以添加。' }}</p>
          <ul v-else class="attachment-list">
            <li v-for="file in visibleAttachments" :key="file.id" class="attachment-row">
              <input v-if="attachmentTrashVisible" v-model="selectedTrashAttachments" type="checkbox" :value="file.id"
                :aria-label="'选择附件 ' + file.name" :disabled="attachmentActionBusy" />
              <div class="attachment-file-info"><strong>{{ file.name }}</strong>
                <span class="section-description">{{ attachmentType(file.name) }} · {{ attachmentSize(file.size) }}{{ file.deleted_at ? ' · 来源在回收站' : !file.record_id ? ' · 独立文件' : '' }}</span>
              </div>
              <template v-if="attachmentTrashVisible">
                <button type="button" class="note-toolbar-text" :disabled="attachmentActionBusy" @click="changeAttachmentTrash(file, 'restore')">恢复</button>
                <button type="button" class="note-toolbar-text" :disabled="attachmentActionBusy" @click="changeAttachmentTrash(file, 'purge')">永久删除</button>
              </template>
              <template v-else>
                <button v-if="file.record_id" type="button" class="note-toolbar-text" :title="file.record_title ?? undefined" @click="openSourceNote(file.record_id)">来源笔记</button>
                <button type="button" class="note-toolbar-text" :disabled="attachmentActionBusy" @click="changeAttachmentTrash(file, 'trash')">删除</button>
              </template>
              <a v-if="!attachmentInlineKind(file.name) && attachmentCanPreview(file.name)" class="note-toolbar-text" :href="attachmentUrl(file, true, attachmentTrashVisible)" target="_blank" rel="noopener">预览</a>
              <a class="note-toolbar-text" :href="attachmentUrl(file, false, attachmentTrashVisible)" :download="file.name">下载</a>
              <AttachmentPreview v-if="attachmentInlineKind(file.name)" :kind="attachmentInlineKind(file.name)" :name="file.name" :src="attachmentUrl(file, true, attachmentTrashVisible)" />
            </li>
          </ul>
        </section>

        <section v-else-if="activeView === 'tasks'" class="recent-card tasks-page">
          <header class="recent-heading">
            <div class="library-heading">
              <h1>待办事项</h1>
              <p v-if="!tasksLoading && !tasksLoadError" class="section-description">{{ pendingTasksCount }} 项待完成</p>
            </div>
            <div class="library-segment" aria-label="待办状态">
              <button type="button" :aria-pressed="taskFilter === 'pending'" :disabled="taskBatchBusy || editingTaskId !== null" @click="taskFilter = 'pending'">待完成</button>
              <button type="button" :aria-pressed="taskFilter === 'completed'" :disabled="taskBatchBusy || editingTaskId !== null" @click="taskFilter = 'completed'">已完成</button>
              <button type="button" :aria-pressed="taskFilter === 'all'" :disabled="taskBatchBusy || editingTaskId !== null" @click="taskFilter = 'all'">全部</button>
            </div>
          </header>
          <div v-if="!tasksLoadError" class="task-overview">
            <div><strong>{{ pendingTasksCount }}</strong><span>待完成</span></div>
            <div><strong :class="{ 'task-overdue': overdueTasksCount }">{{ overdueTasksCount }}</strong><span>已逾期</span></div>
            <div class="task-progress"><strong>{{ taskCompletion }}%</strong><span>整体完成进度</span><progress :value="taskCompletion" max="100" aria-label="待办完成进度"></progress></div>
          </div>
          <fieldset class="task-controls" :disabled="taskBatchBusy || editingTaskId !== null">
            <div class="task-filter-row">
              <input v-model="taskSearch" class="search-input" type="search" placeholder="搜索待办或来源笔记" aria-label="搜索待办" />
              <select v-model="taskPeriod" class="category-filter" aria-label="待办日期范围">
                <option value="all">全部日期</option><option value="today">今天</option><option value="week">未来七天（含今天）</option>
                <option value="overdue">已逾期</option><option value="unscheduled">未安排日期</option><option value="date">{{ taskDay }}</option>
              </select>
              <button type="button" class="search-clear" :aria-expanded="taskCalendarOpen" @click="taskCalendarOpen = !taskCalendarOpen">{{ taskCalendarOpen ? '收起日历' : '按日历查看' }}</button>
              <button type="button" class="search-clear" :aria-pressed="taskBatchMode" @click="taskBatchMode = !taskBatchMode; selectedTaskIds = []">{{ taskBatchMode ? '退出多选' : '批量管理' }}</button>
            </div>
            <div v-if="taskCalendarOpen" class="task-calendar">
              <NoteCalendar :selected-day="taskDay" :today="taskToday" :counts="taskCalendarCounts" item-label="待办"
                :error="Boolean(tasksLoadError)" :counting="tasksLoading" @select="selectTaskDay" @today="selectTaskDay(taskToday)" />
              <p class="section-description">日历按截止日期统计，跟随上方状态和关键词筛选。点击日期查看当天待办。</p>
            </div>
          </fieldset>
          <fieldset v-if="taskBatchMode" class="task-batch-bar" :disabled="taskBatchBusy || editingTaskId !== null">
            <legend>已选 {{ selectedTaskIds.length }} 项（最多 200 项）</legend>
            <div class="task-filter-row">
              <button type="button" class="search-clear" @click="selectedTaskIds = displayedTasks.slice(0, 200).map(task => task.id)">选择当前结果</button>
              <button type="button" class="search-clear" @click="selectedTaskIds = []">取消选择</button>
              <button type="button" class="search-submit" :disabled="!selectedTaskIds.length" @click="applyTaskBatch('complete')">批量完成</button>
              <button type="button" class="search-clear" :disabled="!selectedTaskIds.length" @click="applyTaskBatch('reopen')">恢复待完成</button>
            </div>
            <div class="task-filter-row">
              <label>移到日期 <input v-model="taskBatchDate" type="date" class="category-filter" /></label>
              <label>时间（可选） <input v-model="taskBatchTime" type="time" class="category-filter" :disabled="!taskBatchDate" /></label>
              <button type="button" class="search-clear" :disabled="!selectedTaskIds.length || !taskBatchDate" @click="applyTaskBatch('reschedule')">批量改期</button>
              <button type="button" class="search-clear" :disabled="!selectedTaskIds.length" @click="applyTaskBatch('reschedule', true)">取消日期</button>
            </div>
          </fieldset>
          <p v-if="taskBatchNotice" class="section-description" role="status">{{ taskBatchNotice }}</p>
          <p class="section-description">显示 {{ displayedTasks.length }} 项 · 时间按本机时区显示</p>
          <p v-if="tasksLoading" class="section-description" role="status">正在读取待办…</p>
          <p v-if="tasksLoadError || taskPageError" class="search-error" role="alert">{{ tasksLoadError || taskPageError }}</p>
          <div class="workspace-scroll-region" role="region" aria-label="待办列表" tabindex="0">
          <ul v-if="displayedTasks.length && !tasksLoadError" class="task-list">
            <li v-for="task in displayedTasks" :key="task.id" class="task-row" :class="{ 'task-completed': task.completed_at }">
              <input v-if="taskBatchMode" v-model="selectedTaskIds" type="checkbox" :value="task.id" :aria-label="'选择待办：' + task.title"
                :disabled="taskBatchBusy || editingTaskId !== null || (!selectedTaskIds.includes(task.id) && selectedTaskIds.length >= 200)" />
              <label class="task-check">
                <input type="checkbox" :checked="Boolean(task.completed_at)" :disabled="activeTaskRequests.has(task.id) || taskBatchBusy || editingTaskId === task.id"
                  @click.prevent="changeTask(task)" />
                <span>{{ task.title }}</span>
              </label>
              <div class="task-meta">
                <span v-if="task.priority" class="task-priority" :class="{ urgent: task.priority === 2 }">{{ task.priority === 2 ? '紧急' : '重要' }}</span>
                <button type="button" class="note-toolbar-text" :disabled="activeTaskRequests.has(task.id) || taskBatchBusy" @click="startTaskEdit(task)">编辑 / 改期</button>
                <span v-if="task.due_date" :class="{ 'task-overdue': isOverdue(task) }">
                  {{ isOverdue(task) ? '已逾期 · ' : '截止 ' }}{{ task.due_date }} {{ task.due_time || '' }}
                </span>
                <button type="button" class="note-toolbar-text" @click="openTaskSource(task)">{{ task.record_title }}</button>
                <button type="button" class="note-toolbar-text" :disabled="activeTaskRequests.has(task.id) || taskBatchBusy || editingTaskId === task.id"
                  @click="changeTask(task, true)">移除</button>
              </div>
              <TaskEditor v-if="editingTaskId === task.id" :key="task.id" :task="task" :busy="activeTaskRequests.has(task.id)" :error="taskEditError" @save="saveTaskDetails(task, $event)" @cancel="editingTaskId = null" />
            </li>
          </ul>
          <p v-else-if="!tasksLoading && !tasksLoadError" class="empty-state">
            {{ taskFilter === 'completed' ? '还没有已完成的待办。' : '没有符合当前筛选的待办。可切换日期范围，或从笔记详情添加。' }}
          </p>
          </div>
        </section>

        <div v-else class="note-workspace" :class="{ 'is-split': splitReader }" :style="splitReader && editingId !== null && editWindowWidth ? { gridTemplateColumns: 'minmax(336px, 1fr) clamp(350px, ' + editWindowWidth + 'px, calc(100% - 352px))' } : undefined" @click.self="splitReader && closeActiveReader()">
        <section class="recent-card library-card" :class="{ 'library-list-card': !calendarVisible }">
          <div class="recent-heading">
            <div class="library-heading">
              <h1>{{ viewDetails.label }}</h1>
              <div v-if="calendarVisible || (!isLoading && !listError)" class="section-description">{{ calendarVisible && isLoading ? '正在读取…' : totalRecords + ' 条笔记' }}</div>
            </div>
            <div v-if="activeView === 'library'" class="library-segment" aria-label="知识库视图">
              <button type="button" :aria-pressed="!calendarVisible" @click="changeLibraryMode('list')">列表</button>
              <button type="button" :aria-pressed="calendarVisible" @click="changeLibraryMode('calendar')">日历</button>
            </div>
            <div v-if="activeView !== 'trash'" class="library-actions">
              <details class="export-menu" @keydown.esc.stop="closeMoreMenu">
                <summary class="search-clear">导出</summary>
                <form class="export-controls" @submit.prevent="downloadRecords">
                  <label>格式
                    <select v-model="exportFormat" class="category-filter" aria-label="导出格式" :disabled="exportBusy">
                      <option value="docx">Word (.docx)</option>
                      <option value="xlsx">Excel (.xlsx)</option>
                      <option value="md">Markdown (.md)</option>
                      <option value="json">JSON (.json)</option>
                    </select>
                  </label>
                  <label>范围
                    <select v-model="exportScope" class="category-filter" aria-label="导出范围" :disabled="exportBusy">
                      <option value="all">全库</option>
                      <option value="current">当前筛选</option>
                    </select>
                  </label>
                  <button class="search-submit" :disabled="exportBusy">{{ exportBusy ? '正在导出…' : '下载' }}</button>
                </form>
              </details>
              <button type="button" class="search-submit new-note-button" :title="activeView === 'library' ? '快捷键 Ctrl+Alt+N' : undefined"
                :aria-keyshortcuts="activeView === 'library' ? 'Control+Alt+N' : undefined" @click="openCapture">
                <AppIcon name="plus" :size="18" />{{ hasCaptureDraft || hasStoredCaptureDraft ? '继续草稿' : calendarVisible ? '记在这一天' : '新建笔记' }}
              </button>
            </div>
          </div>
          <p v-if="exportError" class="search-error" role="alert">{{ exportError }}</p>
          <button v-if="activeView === 'trash'" type="button" class="search-clear" @click="openView('settings')">
            回收站设置
          </button>
          <nav v-if="activeView === 'trash'" class="settings-fields attachment-filters" aria-label="回收站类型">
            <button type="button" class="search-submit" aria-current="page">笔记</button>
            <button type="button" class="search-clear" @click="openView('trash', undefined, true)">附件</button>
          </nav>
          <p v-if="recordActionStatus" class="search-result-tip" role="status">{{ recordActionStatus }}</p>
          <p v-if="recordActionError" class="search-error" role="alert">{{ recordActionError }}</p>

          <div class="library-record-layout" :class="{ 'calendar-record-layout': calendarVisible }">
            <NoteCalendar v-if="calendarVisible" v-show="!splitReader || splitCalendarControls === 'calendar'" :selected-day="selectedDay" :today="todayKey"
              :counts="calendarCounts" :counting="calendarLoading" :error="calendarError" @select="selectCalendarDay" @today="selectCalendarToday" />
            <div class="library-record-results">
              <div v-if="calendarVisible" class="calendar-day-strip">
                <h2 class="calendar-results-heading" aria-live="polite">{{ selectedDayLabel }}的笔记</h2>
                <div class="calendar-day-actions" role="group" aria-label="切换笔记日期">
                  <button type="button" class="search-clear" aria-label="前一天" title="前一天"
                    :disabled="batchMoveBusy || dailyReviewBusy || selectedDay === '0001-01-01'" @click="stepCalendarDay(-1)">‹</button>
                  <button type="button" class="search-clear" :disabled="selectedDay === todayKey || batchMoveBusy || dailyReviewBusy" @click="selectCalendarToday">回到今天</button>
                  <button type="button" class="search-clear" aria-label="后一天" title="后一天"
                    :disabled="batchMoveBusy || dailyReviewBusy || selectedDay === '9998-12-31'" @click="stepCalendarDay(1)">›</button>
                  <details class="calendar-month-menu calendar-date-jump" @keydown.esc.stop.prevent="closeMoreMenu">
                    <summary class="search-clear" :aria-label="'当前查看 ' + selectedDay + '，点击跳到其他日期'" title="跳到其他日期">
                      <AppIcon name="calendar" :size="15" />{{ selectedDay }}
                    </summary>
                    <input type="date" class="category-filter" aria-label="跳到指定日期" min="0001-01-01" max="9998-12-31"
                      :value="selectedDay" :disabled="batchMoveBusy || dailyReviewBusy" @change="jumpToCalendarDate" />
                  </details>
                </div>
              </div>
              <div v-if="calendarVisible && splitReader" class="split-calendar-actions">
                <button type="button" class="search-clear" :aria-expanded="splitCalendarControls === 'calendar'"
                  @click="splitCalendarControls = splitCalendarControls === 'calendar' ? null : 'calendar'">月历</button>
                <button type="button" class="search-clear" :aria-expanded="splitCalendarControls === 'filters'"
                  @click="splitCalendarControls = splitCalendarControls === 'filters' ? null : 'filters'">搜索与筛选</button>
              </div>
              <button v-if="calendarVisible" type="button" class="review-entry" @click="openDailyReview">
                <AppIcon name="note" :size="18" />
                <strong>每日回顾</strong>
                <span>{{ !dailyReviewLoading && dailyReviewChanged ? '有未保存草稿' : dailyReviewExists ? '已写' : '开始写' }}</span>
                <span aria-hidden="true">›</span>
              </button>
          <div v-if="activeLibraryFilters.length" class="active-library-filters" aria-label="当前筛选">
            <span>当前筛选</span>
            <button v-for="filter in activeLibraryFilters" :key="filter.key" type="button" class="record-tag tag-filter"
              :aria-label="'移除筛选 ' + filter.label" :disabled="batchMoveBusy || batchBusy" @click="removeLibraryFilter(filter.key)">
              {{ filter.label }} <span aria-hidden="true">×</span>
            </button>
            <button type="button" class="note-toolbar-text" :disabled="batchMoveBusy || batchBusy" @click="clearLibraryFilters">清除全部筛选</button>
          </div>
          <div v-show="!calendarVisible || !splitReader || splitCalendarControls === 'filters'" class="library-filters">
            <form class="search-toolbar" @submit.prevent="searchRecords">
              <select
                v-if="activeView !== 'inbox'"
                v-model="selectedCategory"
                class="category-filter"
                aria-label="筛选分类"
                @change="categoryChanged"
              >
                <option value="">全部分类</option>
                <option v-for="category in categories" :key="category" :value="category">
                  {{ categoryLabel(category) }}
                </option>
              </select>

              <div class="search-input-wrap">
                <AppIcon class="search-icon" name="search" :size="18" />
                <input
                  ref="librarySearchInput"
                  v-model="searchQuery"
                  type="search"
                  placeholder="搜索标题、内容、分类或标签"
                  aria-label="搜索知识库"
                  aria-keyshortcuts="Control+K Meta+K"
                  title="快捷键 Ctrl+K"
                />
              </div>

              <select v-model="recordOrder" class="category-filter" aria-label="记录排序" @change="restartList">
                <option value="newest">最新在前</option>
                <option value="oldest">最早在前</option>
              </select>
              <button type="submit" class="search-submit">搜索</button>
              <button
                v-if="searchQuery || activeKeyword"
                type="button"
                class="search-clear"
                @click="clearSearch"
              >
                清除搜索
              </button>
            </form>

            <div v-if="!calendarVisible" class="date-filter">
              <button type="button" class="search-clear" :aria-expanded="datesOpen" @click="datesOpen = !datesOpen">按笔记日期筛选</button>
              <span v-if="appliedDateFrom || appliedDateTo" class="search-result-tip">
                {{ appliedDateFrom || '不限开始' }} 至 {{ appliedDateTo || '不限结束' }}
              </span>
              <button v-if="appliedDateFrom || appliedDateTo" type="button" class="search-clear" @click="clearDates">清除日期</button>
            </div>
            <form v-if="datesOpen && !calendarVisible" class="date-filter" @submit.prevent="applyDates">
              <label>从 <input v-model="dateFromInput" class="category-filter" type="date" aria-label="开始日期" /></label>
              <label>到 <input v-model="dateToInput" class="category-filter" type="date" aria-label="结束日期" /></label>
              <button class="search-submit">应用日期</button>
              <button type="button" class="search-clear" @click="filterLastSevenDays">最近 7 天</button>
            </form>
            <p v-if="dateError" class="search-error" role="alert">{{ dateError }}</p>
            <div v-if="quickSavedSearches.length" class="saved-searches quick-saved-searches" aria-label="常用搜索快捷入口">
              <span class="section-description">常用搜索</span>
              <button v-for="search in quickSavedSearches" :key="search.id" type="button" class="record-tag tag-filter"
                :title="search.name" :aria-pressed="savedSearchId === search.id" :disabled="batchMoveBusy || batchBusy"
                @click="applySavedSearch(search.id)"><AppIcon v-if="visibleSavedSearchPins.includes(search.id)" name="pinned" :size="13" /> {{ search.name }}</button>
            </div>
            <div class="saved-searches">
              <select v-if="savedSearches.length" v-model="savedSearchId" class="category-filter"
                aria-label="常用搜索" @change="applySavedSearch()">
                <option :value="null">常用搜索</option>
                <option v-for="search in savedSearches" :key="search.id" :value="search.id">{{ search.name }}</option>
              </select>
              <button v-if="savedSearchId !== null" type="button" class="search-clear" :aria-pressed="selectedSavedSearchPinned"
                :disabled="savingSearch || (!selectedSavedSearchPinned && visibleSavedSearchPins.length >= 3)" @click="toggleSavedSearchPin">
                {{ selectedSavedSearchPinned ? '取消固定' : visibleSavedSearchPins.length >= 3 ? '已固定 3 项' : '固定到快捷区' }}
              </button>
              <div v-if="selectedSavedSearchPinned && visibleSavedSearchPins.length > 1" class="saved-search-order" role="group" aria-label="调整固定搜索顺序">
                <button type="button" class="search-clear" :disabled="savingSearch || selectedSavedSearchPinIndex <= 0" @click="moveSavedSearchPin(-1)">往前移</button>
                <button type="button" class="search-clear" :disabled="savingSearch || selectedSavedSearchPinIndex >= visibleSavedSearchPins.length - 1" @click="moveSavedSearchPin(1)">往后移</button>
              </div>
              <button v-if="savedSearchId !== null" type="button" class="search-clear" :disabled="savingSearch"
                @click="removeSavedSearch">移除常用搜索</button>
              <button v-if="activeView !== 'trash' && !showSavedSearchForm && (activeKeyword || selectedCategory || selectedTag || calendarVisible || appliedDateFrom || appliedDateTo || activeView !== 'library')"
                type="button" class="search-clear" @click="openSavedSearchForm">保存当前筛选</button>
            </div>

            <form v-if="showSavedSearchForm" class="saved-searches" @submit.prevent="saveCurrentSearch">
              <span class="saved-search-preview">{{ savedSearchPreview.join(' · ') }}</span>
              <input ref="savedSearchNameInput" v-model="savedSearchName" aria-label="常用搜索名称" maxlength="40"
                class="category-filter saved-search-name" placeholder="输入名称，例如工作资料" required />
              <button class="search-submit" :disabled="savingSearch || !savedSearchName.trim()">保存</button>
              <button type="button" class="search-clear" :disabled="savingSearch"
                @click="resetSavedSearchForm">取消</button>
            </form>
            <p v-if="savedSearchError" class="search-error" role="alert">{{ savedSearchError }}</p>
          </div>

          <div ref="recordScrollRegion" class="workspace-scroll-region" role="region" aria-label="笔记列表" tabindex="0">
          <p v-if="isLoading" class="search-result-tip" role="status">正在读取记录…</p>
          <p v-else-if="listError" class="search-error" role="alert">{{ listError }}</p>
          <p v-else-if="activeKeyword || selectedCategory" class="search-result-tip" role="status">
            {{ selectedCategory ? categoryLabel(selectedCategory) + ' · ' : '' }}
            {{ activeKeyword ? '搜索「' + activeKeyword + '」 · ' : '' }}
            找到 {{ totalRecords }} 条记录
          </p>

          <div v-show="!isLoading && !listError">
            <div v-if="activeView === 'library' && recordCount" class="batch-controls">
              <button type="button" class="search-clear" :disabled="batchMoveBusy" @click="toggleBatchMove">
                {{ batchMoveIsActive ? '退出批量管理' : '批量管理' }}
              </button>
              <button v-if="batchMoveIsActive" type="button" class="search-clear" :disabled="batchMoveBusy"
                @click="batchIds = batchIds.length === records.length ? [] : records.map(record => record.id)">
                {{ batchIds.length === records.length ? '取消全选' : '全选本页' }}
              </button>
              <button v-if="batchMoveIsActive" type="button" class="search-clear batch-trash-button"
                :disabled="!batchIds.length || batchMoveBusy || isLoading" @click="trashSelectedRecords()">
                移入回收站{{ batchIds.length ? '（' + batchIds.length + ' 条）' : '' }}
              </button>
              <form v-if="batchMoveIsActive && batchIds.length" class="batch-controls" @submit.prevent="moveBatchToDate">
                <label class="note-date-field">移动到
                  <input v-model="batchMoveDate" class="category-filter" type="date" required :disabled="batchMoveBusy" />
                </label>
                <button class="search-submit" :disabled="!batchMoveDate || batchMoveBusy">移动 {{ batchIds.length }} 条</button>
              </form>
              <details v-if="batchMoveIsActive && batchIds.length" class="batch-organize">
                <summary>批量归类与标签（{{ batchIds.length }} 条）</summary>
                <form class="batch-controls" @submit.prevent="organizeSelectedRecords">
                  <label>目标分类 <select v-model="batchOrganizeCategory" class="category-filter" :disabled="batchMoveBusy">
                    <option value="">保留原分类</option>
                    <option v-for="category in categories" :key="category" :value="category">{{ categoryLabel(category) }}</option>
                  </select></label>
                  <label>追加标签 <input v-model="batchOrganizeTag" class="category-filter" maxlength="50" placeholder="选填" :disabled="batchMoveBusy" /></label>
                  <button class="search-submit" :disabled="batchMoveBusy || !batchIds.length || !(batchOrganizeCategory || batchOrganizeTag.trim())">应用整理</button>
                </form>
              </details>
            </div>
            <div v-if="activeView === 'trash' && records.length" class="batch-controls">
              <button type="button" class="search-clear" :disabled="batchMoveBusy"
                @click="batchIds = batchIds.length === records.length ? [] : records.map(record => record.id)">
                {{ batchIds.length === records.length ? '取消全选' : '全选本页' }}
              </button>
              <button type="button" class="search-submit" :disabled="batchMoveBusy || !batchIds.length" @click="trashSelectedRecords(true)">
                恢复所选{{ batchIds.length ? '（' + batchIds.length + ' 条）' : '' }}
              </button>
              <button type="button" class="search-clear batch-trash-button" :disabled="batchMoveBusy || !batchIds.length" @click="trashSelectedRecords('purge')">
                永久删除所选
              </button>
            </div>
            <p v-if="(activeView === 'library' || activeView === 'trash') && batchMoveStatus" class="search-result-tip" role="status">{{ batchMoveStatus }}
              <button v-if="batchMovedTo" type="button" class="note-toolbar-text" @click="viewBatchDestination">查看目标日期</button>
            </p>
            <p v-if="(activeView === 'library' || activeView === 'trash') && batchMoveError" class="search-error" role="alert">{{ batchMoveError }}</p>
            <div v-if="activeView === 'inbox' && recordCount" class="batch-controls">
              <button type="button" class="search-clear" :disabled="batchBusy"
                @click="batchIds = batchIds.length === records.length ? [] : records.map(record => record.id)">
                {{ batchIds.length === records.length ? '取消全选' : '全选本页' }}
              </button>
              <form v-if="batchIds.length" class="batch-controls" @submit.prevent="applyBatchCategory">
                <CategoryPicker v-model="batchCategory" :categories="batchCategoryOptions"
                  label="批量目标分类" :disabled="batchBusy" />
                <button class="search-submit" :disabled="batchBusy || !batchCategory.trim() || batchCategory.trim() === '待整理'">
                  归类 {{ batchIds.length }} 条
                </button>
              </form>
            </div>
            <p v-if="activeView === 'inbox' && batchStatus" class="search-result-tip" role="status">{{ batchStatus }}</p>
            <p v-if="activeView === 'inbox' && batchError" class="search-error" role="alert">{{ batchError }}</p>
            <div v-for="record in records" :key="record.id" :data-record-id="record.id" class="record-item" :class="{ 'record-pinned': record.pinned, 'record-selected': detailOpen && linkedRecord?.id === record.id, 'batch-record-active': batchMoveIsActive, 'batch-record-selected': batchMoveIsActive && batchIds.includes(record.id) }"
              @click="openRecordFromRow(record, $event)">
              <input v-if="activeView === 'inbox' || activeView === 'trash' || batchMoveIsActive" v-model="batchIds" type="checkbox" :value="record.id"
                :aria-label="'选择记录 ' + record.title" :disabled="batchBusy || batchMoveBusy" />
              <div class="record-icon"><AppIcon name="note" /></div>

              <div class="record-content">

                  <div class="record-heading">
                    <button type="button" class="record-title-link" :aria-current="detailOpen && linkedRecord?.id === record.id ? 'true' : undefined"
                      :aria-pressed="batchMoveIsActive ? batchIds.includes(record.id) : undefined"
                      @click="batchMoveIsActive ? toggleBatchRecord(record.id) : openLinks(record)">
                      <template v-for="(part, index) in highlight(record.title)" :key="index">
                        <mark v-if="part.matched">{{ part.text }}</mark><template v-else>{{ part.text }}</template>
                      </template>
                    </button>
                    <button v-if="!batchMoveIsActive" type="button" class="note-icon-button" aria-label="复制原文" title="复制原文"
                      @click="copyRecordText(record)"><AppIcon name="copy" :size="18" /></button>
                    <button v-if="activeView !== 'trash' && !batchMoveIsActive" type="button" class="note-icon-button" aria-label="历史版本" title="历史版本"
                      @click="openHistory(record)"><AppIcon name="recent" :size="18" /></button>
                    <div v-if="!batchMoveIsActive" class="record-quick-actions">
                      <template v-if="activeView === 'trash'">
                        <button type="button" class="record-action-button edit-button"
                          :disabled="batchMoveBusy || pendingRecordActions.has(record.id)" @click="changeTrashState(record, true)">恢复</button>
                        <button type="button" class="record-action-button batch-trash-button"
                          :disabled="batchMoveBusy || pendingRecordActions.has(record.id)" @click="changeTrashState(record, 'purge')">永久删除</button>
                      </template>
                      <details v-else class="record-more" @mouseleave="closeMoreMenu" @keydown.esc.stop="closeMoreMenu">
                        <summary class="note-icon-button" title="更多操作" aria-label="更多操作"><AppIcon name="more" :size="18" /></summary>
                        <div class="record-more-actions">
                          <button type="button" @click="openLinks(record, 'edit')">编辑</button>
                          <button type="button" @click="openLinks(record, 'suggest')">整理建议</button>
                          <button type="button" @click="openLinks(record, 'links')">关联笔记</button>
                          <button type="button" @click="templateFromRecord(record)">存为模板</button>
                          <button type="button" :disabled="pinRequests.has(record.id)" :aria-pressed="record.pinned"
                            @click="togglePin(record)">{{ record.pinned ? '取消置顶' : '置顶' }}</button>
                          <button type="button" :disabled="pendingRecordActions.has(record.id)"
                            @click="duplicateRecord(record)">创建副本</button>
                          <button type="button" class="menu-discard" :disabled="pendingRecordActions.has(record.id)"
                            @click="changeTrashState(record, false)">移到回收站</button>
                        </div>
                      </details>
                    </div>
                  </div>

                  <p v-if="excerpt(record)" class="record-excerpt">
                    <template v-for="(part, index) in highlight(excerpt(record))" :key="index">
                      <mark v-if="part.matched">{{ part.text }}</mark><template v-else>{{ part.text }}</template>
                    </template>
                  </p>
                  <a v-if="record.url && !batchMoveIsActive" :href="record.url" target="_blank" rel="noopener noreferrer">打开网站</a>

                  <div class="record-meta">
                    <button v-if="!batchMoveIsActive && !record.deletedAt && editDraftIds.has(record.id)" type="button"
                      class="record-tag draft-continue-button" :aria-label="'继续编辑草稿：' + record.title" @click="openLinks(record, 'edit')">继续编辑草稿</button>
                    <span v-if="record.pinned" class="pin-indicator">置顶</span>
                    <span class="record-category">
                      <template v-for="(part, index) in highlight(record.category)" :key="index"><mark
                        v-if="part.matched">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template>
                    </span>
                    <button v-for="tag in record.tags" :key="tag" type="button" class="record-tag tag-filter" :tabindex="batchMoveIsActive ? -1 : undefined"
                      :aria-pressed="selectedTag === tag" @click="batchMoveIsActive ? toggleBatchRecord(record.id) : filterByTag(selectedTag === tag ? '' : tag)">
                      <template v-for="(part, index) in highlight(tag)" :key="index"><mark
                        v-if="part.matched">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template>
                    </button>
                    <span v-if="record.noteDate && record.noteDate !== record.createdDay" :title="'实际创建 ' + record.time">
                      {{ record.noteDate }}
                    </span>
                    <span v-else>{{ record.time }}</span>
                    <span v-if="activeView === 'trash' && trashPolicyEnabled && record.deletedAt && trashExpiryLabel(record.deletedAt)">
                      清理日期 {{ trashExpiryLabel(record.deletedAt) }}
                    </span>
                  </div>




              </div>
            </div>

            <nav v-if="pageCount > 1" class="record-pagination" aria-label="记录分页">
              <button type="button" class="search-clear" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">上一页</button>
              <span>第 {{ currentPage }} / {{ pageCount }} 页</span>
              <button type="button" class="search-clear" :disabled="currentPage >= pageCount" @click="changePage(currentPage + 1)">下一页</button>
            </nav>
            <div v-if="recordCount === 0" class="empty-state">
              <template v-if="activeKeyword && selectedCategory">
                当前分类没有匹配的记录，试试其他关键词或分类。
              </template>
              <template v-else-if="activeKeyword">没有找到匹配的记录，试试其他关键词。</template>
              <template v-else-if="calendarVisible">这一天没有符合条件的笔记。</template>
              <template v-else-if="appliedDateFrom || appliedDateTo">所选日期范围内没有符合条件的记录。</template>
              <template v-else-if="selectedTag">当前视图没有带这个标签的记录。</template>
              <template v-else-if="selectedCategory">这个分类暂时没有记录。</template>
              <template v-else>{{ viewDetails.empty }}</template>
            </div>
          </div>
            </div>
            </div>
          </div>
        </section>
        <aside v-show="splitReader" ref="readerHost" class="note-detail-dialog split-note-reader" aria-label="笔记阅读区"></aside>
        </div>
      </div>
      <dialog ref="captureDialog" class="links-dialog compose-dialog" :style="captureWindowWidth ? { width: 'min(' + captureWindowWidth + 'px, calc(100% - 24px))' } : undefined" aria-labelledby="compose-heading" @cancel="preventClosingCapture"
        @pointerdown="trackBackdropPress" @click="dismissBackdrop($event, 'capture')">
        <div class="links-toolbar">
          <h2 id="compose-heading">{{ templateEditing ? '模板编辑' : '新建笔记' }}</h2>
          <form method="dialog">
            <button class="note-icon-button note-close" aria-label="关闭新建笔记" title="关闭" :disabled="captureBusy || templateBusy"><AppIcon name="close" /></button>
          </form>
        </div>
          <form class="capture-form" @submit.prevent="addRecord">
            <CaptureTemplates ref="templatePicker" :disabled="captureBusy" @busy="templateBusy = $event" @editing="templateEditing = $event" @apply="applyCaptureTemplate" />
            <div v-show="!templateEditing" class="capture-note-fields">
            <div v-if="templateNotice" class="template-notice" role="status">
              <span>{{ templateNotice }}</span>
              <button v-if="templateUndo" type="button" class="note-toolbar-text" :disabled="captureBusy" @click="undoCaptureTemplate">{{ templateUndo.appliedDate ? '撤销带入' : '撤销模板' }}</button>
            </div>
            <div class="capture-fields">
              <input v-model="captureTitle" class="category-filter" aria-label="记录标题"
                maxlength="200" placeholder="标题（选填）" :disabled="captureBusy" />
              <CategoryPicker v-model="captureCategory" class="capture-category" :categories="categories"
                label="记录分类" :disabled="captureBusy" />
              <button v-if="captureRecommendation && captureRecommendation !== captureCategory" type="button"
                class="record-tag tag-filter" :disabled="captureBusy" @click="captureCategory = captureRecommendation">
                推荐分类：{{ categoryLabel(captureRecommendation) }}
              </button>
            </div>
            <div class="writing-tools" role="group" aria-label="正文格式">
              <button v-for="tool in writingTools" :key="tool.label" type="button" class="note-toolbar-text"
                :disabled="captureBusy" :aria-label="tool.label" :title="tool.label" @pointerdown.prevent @click="insertWritingTool('capture', tool)"><AppIcon :name="tool.icon" :size="18" /></button>
              <button type="button" class="note-toolbar-text" aria-label="撤销" title="撤销 (Ctrl+Z)" :disabled="captureBusy || !captureBody?.canUndo" @pointerdown.prevent @click="captureBody?.replay()">↶</button>
              <button type="button" class="note-toolbar-text" aria-label="重做" title="重做 (Ctrl+Y)" :disabled="captureBusy || !captureBody?.canRedo" @pointerdown.prevent @click="captureBody?.replay(true)">↷</button>
              <button type="button" class="note-toolbar-text" aria-label="查找替换" title="查找替换" :disabled="captureBusy" @click="captureBody?.showReplace()"><AppIcon name="search" :size="18" /></button>
            </div>
            <FormattedEditor ref="captureBody" v-model="message" label="记录正文" :disabled="captureBusy" @shortcut="captureShortcut" @resize-width="captureWindowWidth = $event" />
            <div class="attachment-editor">
              <label class="attachment-action search-clear"><AppIcon name="attachments" :size="16" />添加附件
                <input type="file" multiple aria-label="为新笔记添加附件" :disabled="captureBusy || attachmentUploadBusy" @change="uploadNoteAttachments($event)" />
              </label>
              <ExistingAttachmentPicker :load="loadUnlinkedAttachments" :excluded="captureAttachments.map(file => file.id)"
                :disabled="captureBusy || attachmentUploadBusy" @pick="queueExistingAttachments($event)" />
              <span v-if="attachmentUploadStatus" class="section-description" role="status">{{ attachmentUploadStatus }}</span>
              <ul v-if="captureAttachments.length" class="attachment-list queued-attachments">
                <li v-for="file in captureAttachments" :key="file.id" class="attachment-row">
                  <span class="attachment-file-info">{{ file.name }}</span>
                  <button type="button" class="note-toolbar-text" :disabled="captureBusy || attachmentUploadBusy" @click="captureAttachments = captureAttachments.filter(item => item.id !== file.id)">取消关联</button>
                  <AttachmentPreview v-if="attachmentInlineKind(file.name)" :kind="attachmentInlineKind(file.name)" :name="file.name" :src="attachmentUrl(file, true)" />
                </li>
              </ul>
            </div>
            <div class="capture-footer">
              <div class="compose-meta">
                <details ref="captureDateMenu" class="capture-date-menu" @keydown.esc.stop.prevent="closeMoreMenu">
                  <summary :aria-label="'笔记日期：' + captureDateCaption + '，点击修改'" @click="captureBusy && $event.preventDefault()">
                    <AppIcon name="calendar" :size="16" /><span>{{ captureDateCaption }}</span>
                  </summary>
                  <div class="capture-date-popover">
                    <label for="capture-date-input">笔记日期</label>
                    <input id="capture-date-input" v-model="captureNoteDate" type="date" :disabled="captureBusy"
                      @keydown.enter.prevent="captureDateMenu && (captureDateMenu.open = false)" />
                    <p>用于笔记归档和日历，不是提醒时间。</p>
                    <div>
                      <button type="button" :disabled="captureBusy" @click="captureNoteDate = ''; captureDateMenu && (captureDateMenu.open = false)">今天</button>
                      <button type="button" :disabled="captureBusy" @click="captureDateMenu && (captureDateMenu.open = false)">完成</button>
                    </div>
                  </div>
                </details>
                <span class="compose-word-count">{{ captureLength }} 字符<span class="compose-shortcut"> · Ctrl + Enter 保存</span></span>
                <span v-if="restoredCaptureDraft" class="compose-word-count" role="status">已恢复草稿</span>
              </div>
              <button v-if="hasCaptureDraft" type="button" class="note-toolbar-text" :disabled="captureBusy" @click="discardCaptureDraft">放弃草稿</button>
              <button class="submit-button" :disabled="!message.trim() || captureBusy || attachmentUploadBusy">
                {{ captureBusy ? '正在保存…' : '保存记录' }}
              </button>
            </div>
            <p v-if="captureError" class="search-error" role="alert">{{ captureError }}</p>
            </div>
          </form>
      </dialog>
      <dialog ref="reviewDialog" class="links-dialog compose-dialog" aria-labelledby="daily-review-heading"
        :style="reviewWindowWidth ? { width: 'min(' + reviewWindowWidth + 'px, calc(100% - 24px))' } : undefined"
        @cancel="dailyReviewBusy && $event.preventDefault()">
        <div class="links-toolbar">
          <div><h2 id="daily-review-heading">每日回顾</h2><p class="section-description" aria-live="polite">{{ selectedDay }} · {{ selectedDayLabel }}</p></div>
          <form method="dialog">
            <button class="note-icon-button note-close" aria-label="关闭每日回顾" :disabled="dailyReviewBusy"><AppIcon name="close" /></button>
          </form>
        </div>
        <nav class="review-day-navigation" aria-label="浏览其他日期的回顾">
          <button type="button" class="search-clear" :disabled="dailyReviewBusy || selectedDay === '0001-01-01'" @click="browseDailyReview(-1)">‹ 前一天</button>
          <button type="button" class="search-clear" :disabled="dailyReviewBusy || selectedDay === todayKey" @click="browseDailyReview(0)">回到今天</button>
          <button type="button" class="search-clear" :disabled="dailyReviewBusy || selectedDay === '9998-12-31'" @click="browseDailyReview(1)">后一天 ›</button>
        </nav>
        <div v-if="!showReviewEditor && canEditDailyReview" class="review-reading">
          <WritingPreview :text="dailyReviewSaved[selectedDay] ?? ''" />
        </div>
        <div v-if="!showReviewEditor && canEditDailyReview" class="capture-footer review-reading-footer">
          <span class="compose-word-count" role="status">{{ dailyReviewStatus || (Array.from(dailyReviewSaved[selectedDay] ?? '').length + ' 字符') }}</span>
          <details class="note-share-menu record-more review-export-menu" @keydown.esc.stop.prevent="closeMoreMenu"
            @click="closeReviewExportAfterAction">
            <summary class="search-clear">复制与下载</summary>
            <div class="record-more-actions">
              <button type="button" @click="copyDailyReview()">复制纯文本</button>
              <button type="button" @click="copyDailyReview(true)">复制 Markdown</button>
              <button type="button" @click="downloadDailyReview('markdown')">下载 Markdown</button>
              <button type="button" @click="downloadDailyReview('text')">下载纯文本</button>
            </div>
          </details>
          <button type="button" class="search-clear" @click="reviewToNote">转为笔记</button>
          <button type="button" class="search-submit" @click="editDailyReview">编辑回顾</button>
        </div>
        <p v-if="dailyReviewLoading" class="section-description" role="status">正在读取回顾…</p>
        <div v-else-if="!canEditDailyReview" class="capture-footer">
          <p class="search-error" role="alert">{{ dailyReviewError }}</p>
          <button type="button" class="search-clear" @click="loadDailyReview(selectedDay)">重试</button>
        </div>
        <form v-if="showReviewEditor" class="capture-form" @submit.prevent="saveReviewForDay">
          <div class="capture-note-fields">
            <div class="writing-tools" role="group" aria-label="正文格式">
              <button v-for="tool in writingTools" :key="tool.label" type="button" class="note-toolbar-text"
                :disabled="dailyReviewBusy || dailyReviewLoading" :aria-label="tool.label" :title="tool.label" @pointerdown.prevent @click="reviewBody?.format(tool.prefix)"><AppIcon :name="tool.icon" :size="18" /></button>
              <button type="button" class="note-toolbar-text" aria-label="撤销" title="撤销 (Ctrl+Z)" :disabled="dailyReviewBusy || dailyReviewLoading || !reviewBody?.canUndo" @pointerdown.prevent @click="reviewBody?.replay()">↶</button>
              <button type="button" class="note-toolbar-text" aria-label="重做" title="重做 (Ctrl+Y)" :disabled="dailyReviewBusy || dailyReviewLoading || !reviewBody?.canRedo" @pointerdown.prevent @click="reviewBody?.replay(true)">↷</button>
              <button type="button" class="note-toolbar-text" aria-label="查找替换" title="查找替换" :disabled="dailyReviewBusy || dailyReviewLoading" @click="reviewBody?.showReplace()"><AppIcon name="search" :size="18" /></button>
            </div>
            <details ref="reviewOutlineMenu" class="review-outline-menu" @keydown.esc.stop.prevent="closeMoreMenu">
              <summary class="note-toolbar-text">写作提纲</summary>
              <div class="review-outline-panel">
                <label>选择提纲 <select v-model.number="selectedReviewOutline" class="category-filter">
                  <option v-for="(outline, index) in reviewOutlines" :key="outline.name" :value="index">{{ outline.name }}</option>
                </select></label>
                <ul><li v-for="heading in reviewOutlines[selectedReviewOutline]?.headings" :key="heading">{{ heading }}</li></ul>
                <button type="button" class="search-submit" :disabled="dailyReviewBusy || dailyReviewLoading" @click="insertReviewOutline">
                  {{ dailyReviewText.trim() ? '追加到末尾' : '插入提纲' }}
                </button>
              </div>
            </details>
            <FormattedEditor ref="reviewBody" v-model="dailyReviewText" label="每日回顾正文"
              :disabled="dailyReviewBusy || dailyReviewLoading" @shortcut="reviewShortcut" @resize-width="reviewWindowWidth = $event" />
            <div class="capture-footer">
              <span class="compose-word-count">{{ Array.from(dailyReviewText).length }} 字符 · Ctrl + Enter 保存</span>
              <button v-if="dailyReviewChanged && selectedDay in dailyReviewSaved" type="button" class="note-toolbar-text"
                :disabled="dailyReviewBusy || dailyReviewLoading" @click="discardReviewDraft">放弃草稿</button>
              <button class="submit-button" :disabled="!(selectedDay in dailyReviewSaved) || !dailyReviewChanged || dailyReviewBusy || dailyReviewLoading">
                {{ dailyReviewBusy ? '正在保存…' : '保存回顾' }}
              </button>
            </div>
            <p v-if="dailyReviewLoading || dailyReviewStatus" class="section-description" role="status">{{ dailyReviewLoading ? '正在读取回顾…' : dailyReviewStatus }}</p>
            <p v-if="dailyReviewError" class="search-error" role="alert">{{ dailyReviewError }}</p>
          </div>
        </form>
      </dialog>
      <dialog ref="historyDialog" class="links-dialog" aria-labelledby="history-heading" @close="clearHistory" @cancel="historyBusy && $event.preventDefault()"
        @pointerdown="trackBackdropPress" @click="dismissBackdrop($event, 'history')">
        <div class="links-toolbar">
          <h2 id="history-heading">历史版本</h2>
          <form method="dialog"><button class="search-clear">关闭</button></form>
        </div>
        <p v-if="historyLoading" role="status">正在读取历史版本…</p>
        <p v-if="historyError" class="search-error" role="alert">{{ historyError }}</p>
        <p v-if="historyStatus" class="search-result-tip" role="status">{{ historyStatus }}</p>
        <template v-if="historyRecord && !historyLoading">
          <h3>{{ historyRecord.title }}</h3>
          <p v-if="!versions.length" class="section-description">此记录还没有历史版本。下一次修改时会保存旧内容。</p>
          <template v-else>
            <label class="settings-fields">
              查看版本
              <select v-model="versionId" class="category-filter" :disabled="historyBusy">
                <option v-for="version in versions" :key="version.id" :value="version.id">
                  {{ formatTime(version.captured_at) }} · 版本 {{ version.id }}
                </option>
              </select>
            </label>
            <div v-if="selectedVersion" class="history-preview">
              <strong>{{ selectedVersion.title || '未填写标题' }}</strong>
              <p class="linked-content">{{ selectedVersion.content }}</p>
              <p v-if="selectedVersion.summary" class="section-description">摘要：{{ selectedVersion.summary }}</p>
              <p class="section-description">分类：{{ selectedVersion.category }}</p>
              <p class="section-description">笔记日期：{{ selectedVersion.note_date || historyRecord.createdDay }}</p>
              <p v-if="parseTags(selectedVersion.tags).length" class="section-description">
                标签：{{ parseTags(selectedVersion.tags).join('、') }}
              </p>
              <button type="button" class="search-submit" :disabled="historyBusy" @click="restoreSelectedVersion">恢复此版本</button>
            </div>
          </template>
        </template>
      </dialog>
      <dialog ref="linkDialog" class="links-dialog note-detail-dialog" :style="editingId !== null && editWindowWidth ? { width: 'min(' + editWindowWidth + 'px, calc(100% - 24px))' } : undefined" aria-labelledby="links-heading" @close="handleNoteDialogClosed" @cancel="dismissNoteDialogOnEscape"
        @pointerdown="trackBackdropPress" @click="dismissBackdrop($event, 'note')">
        <Teleport :to="readerHost" :disabled="!splitReader || !readerHost">
        <div class="note-reader-toolbar">
          <button v-if="previousLinkIds.length && editingId === null" type="button" class="note-toolbar-text"
            :disabled="linkLoading" @click="goBackInLinks">‹ 返回上条</button>
          <h2 id="links-heading">{{ editingId === null ? '笔记详情' : '编辑笔记' }}</h2>
          <div v-if="linkedRecord && editingId === null" class="note-reader-tools">
            <details class="note-share-menu record-more" @keydown.esc.stop.prevent="closeMoreMenu">
              <summary class="note-icon-button" aria-label="复制与下载" title="复制与下载"><AppIcon name="download" :size="18" /></summary>
              <div class="record-more-actions">
                <button type="button" @click="shareNote(linkedRecord, 'plain', $event)">复制纯文本</button>
                <button type="button" @click="shareNote(linkedRecord, 'markdown', $event)">下载 Markdown</button>
                <button type="button" @click="shareNote(linkedRecord, 'text', $event)">下载纯文本</button>
              </div>
            </details>
            <button type="button" class="note-icon-button" aria-label="查找正文" title="查找正文" :aria-expanded="readerFindOpen" @click="showReaderFind"><AppIcon name="search" :size="18" /></button>
            <details class="reading-menu" @keydown.esc.stop.prevent="closeMoreMenu">
              <summary class="note-icon-button" aria-label="阅读设置" title="阅读设置">Aa</summary>
              <div class="reading-options">
                <strong>阅读设置</strong>
                <nav v-if="readerOutline.length" class="reader-outline" aria-label="笔记目录">
                  <strong>目录</strong>
                  <button v-for="heading in readerOutline" :key="heading.offset" type="button" class="note-toolbar-text"
                    :style="{ paddingInlineStart: ((heading.level - 1) * 8 + 6) + 'px' }" @click="jumpToHeading(heading.offset, $event)">{{ heading.title }}</button>
                </nav>
                <small v-else>用 # 或 ## 写章节标题，即可生成目录。</small>
                <label>正文字号<select v-model.number="readingPreferences.size"><option :value="14">小 · 14</option><option :value="16">标准 · 16</option><option :value="18">大 · 18</option><option :value="20">特大 · 20</option></select></label>
                <label class="reading-spacing"><input v-model="readingPreferences.spacious" type="checkbox" />宽松行距</label>
                <button type="button" class="note-toolbar-text" @click="resetReadingPreferences">恢复默认</button>
                <small>自动记住此浏览器的阅读偏好。</small>
              </div>
            </details>
            <button type="button" class="note-icon-button" aria-label="复制原文" title="复制原文"
              @click="copyRecordText(linkedRecord)"><AppIcon name="copy" :size="18" /></button>
            <button v-if="!linkedRecord.deletedAt" type="button" class="note-icon-button" aria-label="历史版本" title="历史版本"
              @click="openHistory(linkedRecord)"><AppIcon name="recent" :size="18" /></button>
            <button v-if="!linkedRecord.deletedAt" type="button" class="note-toolbar-text note-edit-action"
              @click="startEdit(linkedRecord)">编辑</button>
          </div>
          <button type="button" class="note-icon-button note-close" aria-label="关闭笔记详情" title="关闭"
            :disabled="isSavingEdit" @click="closeActiveReader"><AppIcon name="close" /></button>
        </div>
        <p v-if="linkLoading && !linkedRecord" role="status">正在读取记录…</p>
        <p v-if="linkError" class="search-error" role="alert">{{ linkError }}</p>
        <div v-if="linkedRecord" class="note-reader-main">
          <nav v-if="editingId === null && readerListIndex >= 0 && records.length > 1 && !batchMoveIsActive" class="reader-page-navigation" aria-label="浏览本页笔记">
            <button type="button" class="note-toolbar-text" :aria-disabled="linkLoading || readerListIndex === 0" @click="browseAdjacentNote(-1)">‹ 上一条</button>
            <span role="status">本页 {{ readerListIndex + 1 }} / {{ records.length }}</span>
            <button type="button" class="note-toolbar-text" :aria-disabled="linkLoading || readerListIndex === records.length - 1" @click="browseAdjacentNote(1)">下一条 ›</button>
          </nav>
          <div v-if="editingId === linkedRecord.id" class="edit-form">

            <div v-if="suggestion" class="suggestion-panel">
              <strong>整理建议</strong>
              <p>点击要采纳的建议，然后保存修改。</p>
              <div class="tag-row">
                <button v-if="suggestion.title && suggestion.title !== editTitle" type="button" class="record-tag"
                  @click="editTitle = suggestion.title">标题：{{ suggestion.title }}</button>
                <button v-if="suggestion.category && suggestion.category !== editCategory" type="button" class="record-tag"
                  @click="editCategory = suggestion.category">分类：{{ suggestion.category }}</button>
                <template v-for="tag in suggestion.tags" :key="tag">
                  <button v-if="!editTags.includes(tag)" type="button" class="record-tag"
                    @click="editTags.push(tag)">标签：{{ tag }}</button>
                </template>
              </div>
              <p v-if="(!suggestion.title || suggestion.title === editTitle) &&
                (!suggestion.category || suggestion.category === editCategory) &&
                suggestion.tags.every(tag => editTags.includes(tag))">没有待采纳的建议。</p>
            </div>

            <div class="edit-field">
              <label :for="'title-' + linkedRecord.id">标题</label>
              <input :id="'title-' + linkedRecord.id" v-model="editTitle" class="record-title-input"
                maxlength="200" placeholder="留空时从正文显示标题" />
            </div>

            <div class="edit-field edit-body-field">
              <span>正文</span>
            <div class="writing-tools" role="group" aria-label="正文格式">
              <button v-for="tool in writingTools" :key="tool.label" type="button" class="note-toolbar-text"
                :disabled="isSavingEdit" :aria-label="tool.label" :title="tool.label" @pointerdown.prevent @click="insertWritingTool('edit', tool)"><AppIcon :name="tool.icon" :size="18" /></button>
              <button type="button" class="note-toolbar-text" aria-label="撤销" title="撤销 (Ctrl+Z)" :disabled="isSavingEdit || !editBody?.canUndo" @pointerdown.prevent @click="editBody?.replay()">↶</button>
              <button type="button" class="note-toolbar-text" aria-label="重做" title="重做 (Ctrl+Y)" :disabled="isSavingEdit || !editBody?.canRedo" @pointerdown.prevent @click="editBody?.replay(true)">↷</button>
              <button type="button" class="note-toolbar-text" aria-label="查找替换" title="查找替换" :disabled="isSavingEdit" @click="editBody?.showReplace()"><AppIcon name="search" :size="18" /></button>
            </div>
              <FormattedEditor ref="editBody" v-model="editContent" label="笔记正文" :disabled="isSavingEdit" @resize-width="editWindowWidth = $event" />
            </div>

            <details class="edit-note-properties">
              <summary>分类、日期和标签</summary>
            <div class="edit-field">
              <label :for="'category-' + linkedRecord.id">分类</label>
              <CategoryPicker :id="'category-' + linkedRecord.id" v-model="editCategory"
                :categories="categories" label="分类" :disabled="isSavingEdit" />
              <button v-if="!suggestion && editRecommendation && editRecommendation !== editCategory"
                type="button" class="record-tag tag-filter" @click="editCategory = editRecommendation">
                推荐分类：{{ categoryLabel(editRecommendation) }}
              </button>
            </div>

            <div class="edit-field">
              <label :for="'note-date-' + linkedRecord.id">笔记日期</label>
              <div class="note-date-field">
                <input :id="'note-date-' + linkedRecord.id" v-model="editNoteDate" class="category-filter"
                  type="date" :disabled="isSavingEdit" />
                <span v-if="!editNoteDate">留空时使用创建日期 {{ linkedRecord.createdDay }}</span>
              </div>
            </div>

            <div class="edit-field">
              <label :for="'tag-' + linkedRecord.id">标签</label>
              <div class="tag-row">
                <button v-for="(tag, index) in editTags" :key="tag" type="button" class="record-tag"
                  :aria-label="'移除标签 ' + tag" @click="editTags.splice(index, 1)">{{ tag }} ×</button>
              </div>
              <div class="tag-row">
                <input :id="'tag-' + linkedRecord.id" v-model="newTag" placeholder="输入一个标签" @keydown.enter.prevent="addTag" />
                <button type="button" class="record-action-button edit-button" :disabled="!newTag.trim()"
                  @click="addTag">添加标签</button>
              </div>
            </div>

            </details>
            <div class="attachment-editor">
              <label class="attachment-action search-clear"><AppIcon name="attachments" :size="16" />添加附件
                <input type="file" multiple aria-label="为当前笔记添加附件" :disabled="isSavingEdit || attachmentUploadBusy" @change="uploadNoteAttachments($event, linkedRecord.id)" />
              </label>
              <ExistingAttachmentPicker :load="loadUnlinkedAttachments" :excluded="attachedEditFiles.map(file => file.id)"
                :disabled="isSavingEdit || attachmentUploadBusy" @pick="queueExistingAttachments($event, linkedRecord.id)" />
              <span v-if="attachmentUploadStatus" class="section-description" role="status">{{ attachmentUploadStatus }}</span>
              <ul v-if="attachedEditFiles.length" class="attachment-list queued-attachments">
                <li v-for="file in attachedEditFiles" :key="file.id" class="attachment-row">
                  <span class="attachment-file-info">{{ file.name }}</span>
                  <button type="button" class="note-toolbar-text" :disabled="isSavingEdit || attachmentUploadBusy"
                    @click="editAttachmentQueue[linkedRecord.id] = attachedEditFiles.filter(item => item.id !== file.id)">取消关联</button>
                  <AttachmentPreview v-if="attachmentInlineKind(file.name)" :kind="attachmentInlineKind(file.name)" :name="file.name" :src="attachmentUrl(file, true)" />
                </li>
              </ul>
            </div>
            <p v-if="editError" class="edit-error">
              {{ editError }}
            </p>

            <div class="edit-actions">
              <span v-if="restoredEditDraft" class="section-description" role="status">已恢复编辑草稿</span>
              <button type="button" class="note-toolbar-text" :disabled="isSavingEdit" @click="discardEditDraft(linkedRecord)">放弃草稿</button>
              <button
                class="save-button"
                :disabled="isSavingEdit || attachmentUploadBusy"
                @click="saveEdit(linkedRecord.id)"
              >
                {{ isSavingEdit ? '正在保存...' : '保存修改' }}
              </button>

              <button
                class="cancel-button"
                :disabled="isSavingEdit"
                @click="cancelEdit"
              >
                返回详情
              </button>
            </div>

          </div>
          <template v-else>
            <article class="note-paper">
              <header class="note-paper-header">
                <h3 class="note-detail-title">{{ linkedRecord.title }}</h3>
                <div class="record-meta note-detail-meta">
                  <span v-if="linkedRecord.deletedAt" class="record-category">{{ categoryLabel(linkedRecord.category) }}</span>
                  <button v-else type="button" class="record-category note-toolbar-text reader-meta-filter"
                    :title="'查看分类：' + categoryLabel(linkedRecord.category)"
                    @click="openView('library', { category: linkedRecord.category })">{{ categoryLabel(linkedRecord.category) }}</button>
                  <span v-if="linkedRecord.deletedAt && linkedRecord.noteDate && linkedRecord.noteDate !== linkedRecord.createdDay">
                    笔记日期 {{ linkedRecord.noteDate }}
                  </span>
                  <button v-if="!linkedRecord.deletedAt" type="button" class="note-toolbar-text reader-meta-action"
                    title="查看这一天的笔记" @click="viewNoteDay(linkedRecord)">
                    <AppIcon name="calendar" :size="14" />{{ linkedRecord.noteDate || linkedRecord.createdDay }}
                  </button>
                  <button v-if="!linkedRecord.deletedAt" type="button" class="note-toolbar-text reader-meta-action"
                    :aria-pressed="linkedRecord.pinned" :disabled="pinRequests.has(linkedRecord.id)" @click="togglePin(linkedRecord)">
                    <AppIcon name="pinned" :size="14" />{{ linkedRecord.pinned ? '已置顶' : '置顶' }}
                  </button>
                  <span :title="'创建于 ' + linkedRecord.time">{{ linkedRecord.time }}</span>
                  <template v-for="tag in linkedRecord.tags" :key="tag">
                    <span v-if="linkedRecord.deletedAt" class="record-tag">{{ tag }}</span>
                    <button v-else type="button" class="record-tag note-toolbar-text reader-meta-filter" :title="'查看标签：' + tag"
                      @click="openView('library', { tag })">{{ tag }}</button>
                  </template>
                </div>
              </header>
              <p class="reading-statistics">{{ readingCharacters }} 字符 · 预计阅读 {{ readingMinutes }} 分钟</p>
              <p v-if="noteShareStatus" class="section-description" role="status">{{ noteShareStatus }}</p>
              <div v-if="readerFindOpen" class="reader-find" role="search" aria-label="正文查找" @keydown.esc.stop.prevent="closeReaderFind">
                <input ref="readerSearch" v-model="readerQuery" type="search" aria-label="正文关键词" placeholder="查找正文"
                  @keydown.enter.prevent="moveReaderMatch($event.shiftKey ? -1 : 1)" />
                <span role="status">{{ !readerQuery.trim() ? '' : readerMatchCount ? (readerMatch + 1) + ' / ' + readerMatchCount : '无匹配' }}</span>
                <button type="button" class="note-toolbar-text" :disabled="!readerMatchCount" @click="moveReaderMatch(-1)">上一处</button>
                <button type="button" class="note-toolbar-text" :disabled="!readerMatchCount" @click="moveReaderMatch(1)">下一处</button>
                <button type="button" class="note-toolbar-text" @click="closeReaderFind">关闭</button>
              </div>
              <div v-if="readerFindOpen || readerOutline.length || linkedRecord.content !== linkedRecord.title" ref="readerText" class="linked-content" :style="{ fontSize: readingPreferences.size + 'px', lineHeight: readingPreferences.spacious ? '1.95' : '1.6' }"><WritingPreview v-if="!readerQuery.trim()" :text="linkedRecord.content" /><template v-else v-for="(part, index) in readerChunks" :key="index"><span v-if="part.anchor !== undefined" :data-heading="part.anchor" tabindex="-1"></span><mark v-else-if="part.match >= 0" :data-current-match="part.match === readerMatch ? '' : undefined">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></div>
              <a v-if="linkedRecord.url" class="note-web-link" :href="linkedRecord.url" target="_blank"
                rel="noopener noreferrer">打开网站 ↗</a>
              <p v-if="recordActionStatus" class="search-result-tip" role="status">{{ recordActionStatus }}</p>
              <p v-if="recordActionError" class="search-error" role="alert">{{ recordActionError }}</p>
              <p v-if="linkedRecord.deletedAt" class="section-description">恢复这条记录后即可编辑。</p>
            </article>

            <section v-if="linkedAttachments.length || linkedAttachmentsError || attachmentActionMessage" class="note-attachment-section" aria-label="笔记附件">
              <h3>附件</h3>
              <p v-if="linkedAttachmentsError" class="section-description">{{ linkedAttachmentsError }}</p>
              <p v-if="attachmentActionMessage" class="section-description" role="status">{{ attachmentActionMessage }}</p>
              <ul v-if="linkedAttachments.length" class="attachment-list">
                <li v-for="file in linkedAttachments" :key="file.id" class="attachment-row">
                  <span class="attachment-file-info">{{ file.name }}</span>
                  <a v-if="!attachmentInlineKind(file.name) && attachmentCanPreview(file.name)" class="note-toolbar-text" :href="attachmentUrl(file, true)" target="_blank" rel="noopener">预览</a>
                  <a class="note-toolbar-text" :href="attachmentUrl(file)" :download="file.name">下载</a>
                  <button type="button" class="note-toolbar-text" :disabled="attachmentActionBusy" @click="changeAttachmentTrash(file, 'trash')">删除</button>
                  <AttachmentPreview v-if="attachmentInlineKind(file.name)" :kind="attachmentInlineKind(file.name)" :name="file.name" :src="attachmentUrl(file, true)" />
                </li>
              </ul>
            </section>
            <footer v-if="!linkedRecord.deletedAt" class="note-reader-footer">
              <details class="note-detail-links" :open="showNoteLinks"
                @toggle="showNoteLinks = ($event.currentTarget as HTMLDetailsElement).open">
                <summary>
                  <span>关联笔记</span><span v-if="noteLinks.length" class="note-link-count">{{ noteLinks.length }} 条</span>
                </summary>
                <div class="note-links-panel">
                  <form class="settings-fields" @submit.prevent="searchLinkCandidates">
                    <input v-model="linkKeyword" class="category-filter" aria-label="查找要关联的记录" placeholder="查找要关联的笔记" />
                    <button class="search-clear" :disabled="!linkKeyword.trim() || linkSearching || linkSaving">查找</button>
                  </form>
                  <p v-if="linkSearchText && !linkCandidates.length" class="section-description">没有可添加的匹配记录。</p>
                  <ul v-if="linkCandidates.length" class="links-list">
                    <li v-for="candidate in linkCandidates" :key="candidate.id">
                      <span>{{ linkDisplayTitle(candidate) }}</span>
                      <button type="button" class="search-clear" :disabled="linkSaving" @click="changeLink(candidate.id, 'PUT')">关联</button>
                    </li>
                  </ul>
                  <p v-if="!noteLinks.length && !linkSearchText && !linkLoading" class="section-description">还没有关联笔记。</p>
                  <template v-for="group in [{ label: '关联到', links: outgoingLinks }, { label: '被这些笔记引用', links: incomingLinks }]"
                    :key="group.label">
                    <section v-if="group.links.length" class="links-group">
                      <h4>{{ group.label }}</h4>
                      <ul class="links-list">
                        <li v-for="link in group.links" :key="link.id">
                          <button type="button" class="linked-title" :disabled="linkSaving" @click="followLink(link.id)">
                            {{ linkDisplayTitle(link) }}
                          </button>
                          <button type="button" class="search-clear" :disabled="linkSaving"
                            @click="changeLink(link.id, 'DELETE', link.direction)">移除关联</button>
                        </li>
                      </ul>
                    </section>
                  </template>
                </div>
              </details>
              <details class="note-task-panel">
                <summary>待办事项 <span v-if="linkedTasks.length">{{ linkedTasks.filter(task => !task.completed_at).length }} 项待完成</span></summary>
                <div class="note-links-panel">
                  <ul v-if="linkedTasks.length" class="task-list">
                    <li v-for="task in linkedTasks" :key="task.id" class="task-row" :class="{ 'task-completed': task.completed_at }">
                      <label class="task-check">
                        <input type="checkbox" :checked="Boolean(task.completed_at)" :disabled="activeTaskRequests.has(task.id) || taskBatchBusy || editingTaskId === task.id"
                          @click.prevent="changeTask(task)" />
                        <span>{{ task.title }}</span>
                      </label>
                      <div class="task-meta">
                <span v-if="task.priority" class="task-priority" :class="{ urgent: task.priority === 2 }">{{ task.priority === 2 ? '紧急' : '重要' }}</span>
                <button type="button" class="note-toolbar-text" :disabled="activeTaskRequests.has(task.id) || taskBatchBusy" @click="startTaskEdit(task)">编辑 / 改期</button>
                        <span v-if="task.due_date" :class="{ 'task-overdue': isOverdue(task) }">
                          {{ isOverdue(task) ? '已逾期 · ' : '截止 ' }}{{ task.due_date }} {{ task.due_time || '' }}
                        </span>
                        <button type="button" class="note-toolbar-text" :disabled="activeTaskRequests.has(task.id) || taskBatchBusy || editingTaskId === task.id"
                          @click="changeTask(task, true)">移除</button>
                      </div>
                      <TaskEditor v-if="editingTaskId === task.id" :key="task.id" :task="task" :busy="activeTaskRequests.has(task.id)" :error="taskEditError" @save="saveTaskDetails(task, $event)" @cancel="editingTaskId = null" />
                    </li>
                  </ul>
                  <form class="settings-fields task-form" @submit.prevent="createTaskForNote">
                    <input v-model="taskTitle" class="category-filter" aria-label="待办名称" maxlength="200"
                      placeholder="写一项要做的事" :disabled="taskCreating" />
                    <label>截止日期 <input v-model="taskDueDate" class="category-filter" type="date" :disabled="taskCreating" /></label>
                    <label>具体时间 <input v-model="taskDueTime" class="category-filter" type="time" :disabled="taskCreating || !taskDueDate" /></label>
                    <label>优先级 <select v-model.number="taskPriority" class="category-filter" :disabled="taskCreating"><option :value="0">普通</option><option :value="1">重要</option><option :value="2">紧急</option></select></label>
                    <button class="search-submit" :disabled="!taskTitle.trim() || taskCreating">添加待办</button>
                  </form>
                  <p v-if="taskModalError" class="search-error" role="alert">{{ taskModalError }}</p>
                </div>
              </details>
              <button type="button" class="note-toolbar-text note-organize-action"
                @click="suggestOrganization(linkedRecord)">整理建议</button>
            </footer>
          </template>
        </div>
        </Teleport>
      </dialog>
    </main>
  </div>
</template>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(html),
:global(body),
:global(#app) {
  margin: 0;
  min-width: 320px;
  min-height: 100%;
}

:global(body) {
  display: block !important;
  min-height: 100vh;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

:global(#app) {
  width: 100%;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
  text-align: left !important;
}

.app-shell {
  display: flex;
  min-height: 100vh;
  background: #f5f7fb;
  color: #202b3c;
}

.sidebar {
  width: 238px;
  min-height: 100vh;
  background: #17243a;
  color: #ffffff;
  padding: 28px 17px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 9px 37px;
}

.brand-logo {
  width: 43px;
  height: 43px;
  border-radius: 13px;
  display: grid;
  place-items: center;
  background: #4178e4;
  font-size: 23px;
  font-weight: bold;
}

.brand-name {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2px;
}

.brand-subtitle {
  font-size: 11px;
  color: #9aabc2;
  margin-top: 4px;
}

.nav-caption {
  color: #7f91aa;
  font-size: 12px;
  padding: 15px 12px 9px;
}

.nav-item {
  height: 44px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 5px;
  border-radius: 8px;
  color: #bdc9d9;
  font-size: 14px;
}

.nav-item.active {
  background: #2c4264;
  color: #ffffff;
}

.nav-icon {
  width: 20px;
  text-align: center;
  font-size: 18px;
  color: #91b8ff;
}

.nav-count {
  margin-left: auto;
  font-size: 11px;
  color: #a9c5ff;
}

.sidebar-bottom {
  margin-top: auto;
  border-top: 1px solid #34445d;
  padding: 22px 7px 0;
  display: flex;
  align-items: center;
  gap: 11px;
}

.user-avatar,
.topbar-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #385b8c;
  display: grid;
  place-items: center;
  color: white;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 12px;
}

.user-info span {
  color: #9aabc2;
  font-size: 11px;
}

.main-area {
  flex: 1;
  min-width: 0;
}

.topbar {
  height: 66px;
  background: #ffffff;
  border-bottom: 1px solid #e9edf3;
  padding: 0 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.breadcrumb {
  font-size: 13px;
  color: #6e7d91;
}

.breadcrumb span {
  padding: 0 9px;
  color: #b1bac6;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 12px;
  color: #728096;
}

.connection-dot {
  width: 8px;
  height: 8px;
  background: #31b982;
  border-radius: 50%;
}

.topbar-avatar {
  width: 30px;
  height: 30px;
  margin-left: 14px;
}

.content {
  max-width: 1200px;
  padding: 39px 42px;
  margin: 0 auto;
}

.welcome-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}

.welcome-tag {
  color: #5783d7;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  margin-bottom: 12px;
}

.welcome-section h1 {
  margin: 0;
  font-size: 27px;
  font-weight: 700;
  letter-spacing: 1px;
}

.welcome-section p {
  font-size: 14px;
  color: #8290a2;
  margin: 10px 0 0;
}

.date-card {
  display: flex;
  flex-direction: column;
  gap: 7px;
  background: white;
  padding: 13px 18px;
  border: 1px solid #edf0f5;
  border-radius: 10px;
  font-size: 11px;
  color: #8793a5;
}

.date-card strong {
  color: #46566c;
  font-size: 13px;
}

.capture-card,
.stat-card,
.recent-card {
  background: #ffffff;
  border: 1px solid #e9edf3;
  border-radius: 13px;
}

.capture-card {
  padding: 25px;
  box-shadow: 0 5px 20px rgba(40, 65, 100, 0.035);
}

.capture-heading,
.recent-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-title {
  font-weight: 700;
  font-size: 16px;
}

.section-description {
  color: #929eaf;
  font-size: 12px;
  margin-top: 7px;
}

.ai-tag {
  font-size: 11px;
  padding: 8px 12px;
  border-radius: 20px;
  color: #547fd0;
  background: #f0f5ff;
}

textarea {
  width: 100%;
  margin-top: 22px;
  border: 1px solid #e7ebf1;
  background: #fafbfd;
  border-radius: 9px;
  padding: 15px;
  resize: vertical;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.8;
  color: #34445a;
  outline: none;
}

textarea:focus {
  border-color: #8cace8;
  background: #ffffff;
}

textarea::placeholder {
  color: #aeb8c6;
}

.capture-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
}

.capture-footer > span {
  color: #9aa5b4;
  font-size: 11px;
}

.submit-button {
  border: none;
  border-radius: 8px;
  background: #477ce1;
  color: white;
  padding: 11px 18px;
  font-size: 12px;
  cursor: pointer;
}

.submit-button:disabled {
  background: #aabbdc;
  cursor: not-allowed;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 17px;
  margin: 23px 0;
}

.stat-card {
  padding: 19px;
}

.stat-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #7d8ba0;
}

.stat-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  font-size: 17px;
}

.stat-icon.blue {
  color: #477ce1;
  background: #edf3ff;
}

.stat-icon.purple {
  color: #9474d9;
  background: #f3effc;
}

.stat-icon.orange {
  color: #db9c48;
  background: #fff5e8;
}

.stat-number {
  font-size: 27px;
  font-weight: 700;
  margin-top: 11px;
  color: #26354a;
}

.stat-note {
  color: #a0aab8;
  font-size: 11px;
  margin-top: 5px;
}

.recent-card {
  padding: 23px 25px;
}

.more-text {
  font-size: 12px;
  color: #527fd0;
}

.record-item {
  display: flex;
  gap: 13px;
  align-items: flex-start;
  padding: 20px 0;
  border-bottom: 1px solid #f0f2f6;
}

.record-item:last-of-type {
  border-bottom: none;
}

.record-icon {
  width: 37px;
  height: 37px;
  background: #eef4ff;
  color: #4d7edb;
  border-radius: 9px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.record-content {
  min-width: 0;
  flex: 1;
}

.record-content strong {
  font-size: 13px;
  color: #34445a;
}

.record-content p {
  font-size: 12px;
  line-height: 1.7;
  color: #8995a6;
  margin: 7px 0;
}

.record-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #a3adba;
  font-size: 10px;
}

.record-category {
  color: #527fd0;
  background: #edf3ff;
  padding: 4px 8px;
  border-radius: 4px;
}

.empty-state {
  padding: 30px;
  text-align: center;
  color: #a0aab8;
  font-size: 13px;
}

.prototype-note {
  text-align: center;
  font-size: 11px;
  line-height: 1.8;
  color: #a1acba;
  margin: 22px 0;
}

@media (max-width: 850px) {
  .sidebar {
    width: 190px;
    padding-left: 12px;
    padding-right: 12px;
  }

  .content {
    padding: 28px 20px;
  }

  .topbar {
    padding: 0 20px;
  }

  .welcome-section h1 {
    font-size: 21px;
  }
}

@media (max-width: 600px) {
  .sidebar {
    width: 65px;
    padding: 16px 8px;
  }

  .brand {
    padding: 0 2px 30px;
  }

  .brand-logo {
    width: 43px;
  }

  .brand-name,
  .brand-subtitle,
  .nav-caption,
  .nav-item span:not(.nav-icon),
  .user-info,
  .sidebar-bottom {
    display: none;
  }

  .nav-item {
    justify-content: center;
    padding: 0;
  }

  .topbar {
    padding: 0 12px;
  }

  .content {
    padding: 23px 12px;
  }

  .date-card {
    display: none;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .capture-card,
  .recent-card {
    padding: 17px;
  }

  .capture-heading,
  .capture-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}

/* 记录操作按钮区域 */
.record-actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  margin-top: 12px;
}

/* 通用按钮 */
.record-action-button {
  padding: 7px 15px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

/* 编辑按钮 */
.edit-button {
  background: #eef4ff;
  color: #477ce1;
  border: 1px solid #dce7fc;
}

.edit-button:hover {
  background: #dce8ff;
}

/* 删除按钮 */
.delete-button {
  background: #fff1f0;
  color: #d65c55;
  border: 1px solid #f7d9d7;
}

.delete-button:hover {
  background: #ffe2df;
}

/* 编辑表单 */
.edit-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.edit-field label {
  font-size: 12px;
  color: #617087;
  font-weight: 600;
}

.edit-field textarea,
.edit-field select {
  width: 100%;
  box-sizing: border-box;
  padding: 11px;
  border: 1px solid #dfe5ee;
  border-radius: 7px;
  font-family: inherit;
  font-size: 13px;
  color: #34445a;
  background: #fafbfd;
  outline: none;
}

.edit-field textarea:focus,
.edit-field select:focus {
  border-color: #7398df;
  background: #ffffff;
}

.edit-error {
  color: #d65c55;
  font-size: 12px;
  margin: 0;
}

/* 保存和取消按钮 */
.edit-actions {
  display: flex;
  gap: 10px;
}

.save-button,
.cancel-button {
  padding: 9px 17px;
  border-radius: 7px;
  border: none;
  font-size: 12px;
  cursor: pointer;
}

.save-button {
  background: #477ce1;
  color: #ffffff;
}

.cancel-button {
  background: #edf0f5;
  color: #64748b;
}

.save-button:disabled,
.cancel-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 知识搜索区域 */
.search-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 22px 0 12px;
}

.category-filter {
  max-width: 100%;
  height: 42px;
  padding: 0 12px;
  border: 1px solid #e4e9f1;
  border-radius: 8px;
  background: #fafbfd;
  color: #34445a;
  font: inherit;
  font-size: 13px;
}

.search-input-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 13px;
  height: 42px;
  border: 1px solid #e4e9f1;
  background: #fafbfd;
  border-radius: 8px;
}

.search-input-wrap:focus-within {
  border-color: #7398df;
  background: #ffffff;
}

.search-icon {
  color: #8392a6;
  font-size: 22px;
}

.search-input-wrap input {
  width: 100%;
  min-width: 0;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: #34445a;
  font-family: inherit;
  font-size: 13px;
}

.search-input-wrap input::placeholder {
  color: #aab4c1;
}

.search-submit,
.search-clear {
  height: 42px;
  padding: 0 18px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
}

.search-submit {
  border: none;
  background: #477ce1;
  color: white;
}

.search-clear {
  border: 1px solid #e4e9f1;
  background: #ffffff;
  color: #64748b;
}

.search-result-tip {
  margin: 12px 0;
  font-size: 12px;
  color: #6e7d91;
}

.search-error {
  color: #d65c55;
  font-size: 12px;
  margin: 10px 0;
}

@media (max-width: 600px) {
  .search-toolbar {
    flex-wrap: wrap;
  }

  .category-filter,
  .search-input-wrap {
    flex: 1 1 100%;
  }

  .search-submit,
  .search-clear {
    flex: 1;
  }
}

.auth-screen {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
  background: #f5f7fb;
  color: #202b3c;
}

.auth-card {
  width: min(100%, 400px);
  padding: 24px;
  border: 1px solid #e4e9f1;
  border-radius: 14px;
  background: #fff;
}

.auth-card h1 {
  margin: 16px 0;
  font-size: 24px;
}

.auth-card form, .password-form {
  display: grid;
  gap: 12px;
}

.auth-card label {
  display: grid;
  gap: 6px;
  font-size: 14px;
}

.auth-card input {
  width: 100%;
  padding: 10px;
  border: 1px solid #b8c6d8;
  border-radius: 8px;
  background: #fff;
  color: #202b3c;
  font: inherit;
}

.auth-card .submit-button {
  margin-top: 8px;
}

.password-form {
  margin-bottom: 18px;
}

.pending-nav {
  opacity: .72;
}

.topbar {
  gap: 8px;
}

.topbar-right button {
  padding-inline: 9px;
  white-space: nowrap;
}

@media (max-width: 420px) {
  .topbar { padding-inline: 10px; }
  .breadcrumb span { padding-inline: 2px; }
}

.view-button {
  width: 100%;
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}

.view-button:hover {
  background: #243854;
}

.record-content {
  min-width: 0;
  overflow-wrap: anywhere;
}

.record-meta, .tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-row input {
  min-width: 0;
  flex: 1 1 100px;
  padding: 7px;
  border: 1px solid #dce7fc;
  border-radius: 6px;
  font: inherit;
}

.record-tag {
  padding: 3px 8px;
  border: 1px solid #dce7fc;
  border-radius: 8px;
  background: #f0f5ff;
  color: #34445a;
  font: inherit;
}

.record-content mark {
  background: #ffedaa;
  color: #352700;
  border-radius: 2px;
}

@media (max-width: 420px) {
  .record-icon { display: none; }
  .record-actions { flex-wrap: wrap; }
}

.saved-searches {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.saved-search-name {
  min-width: 0;
  flex: 1 1 160px;
}

.saved-searches button:disabled {
  opacity: .6;
  cursor: default;
}

.preview-label {
  color: #48617b;
  white-space: nowrap;
}

.suggestion-panel {
  padding: 12px;
  border: 1px solid #c6e5df;
  border-radius: 8px;
  background: #f0faf7;
}

.suggestion-panel .record-tag {
  cursor: pointer;
  text-align: left;
}

.record-title-input {
  width: 100%;
  padding: 8px;
  border: 1px solid #dce7fc;
  border-radius: 6px;
  font: inherit;
}

.capture-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.capture-fields > input,
.capture-category {
  flex: 1 1 160px;
  min-width: 0;
}

.tag-filter {
  cursor: pointer;
}

.tag-filter[aria-pressed="true"] {
  border-color: #477ce1;
}

.recent-heading {
  flex-wrap: wrap;
  gap: 8px;
}

.export-controls,
.batch-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.batch-controls {
  margin-block: 6px;
}

.app-shell {
  color-scheme: light;
  --note-border: #e7e0d3;
  --note-field: #f9f7f1;
  --note-ink: #302b23;
  --note-muted: #6d6253;
  background: #f7f4ed;
  color: var(--note-ink);
}

.sidebar {
  background: #efeae0;
  color: var(--note-ink);
  border-right: 1px solid #e6ded0;
}

.brand {
  padding-bottom: 26px;
}

.brand-logo {
  display: block;
  object-fit: contain;
  background: transparent;
  flex-shrink: 0;
}

.brand-name {
  letter-spacing: .04em;
}

.brand-subtitle,
.nav-caption,
.welcome-section p,
.section-description,
.search-result-tip,
.capture-footer > span,
.breadcrumb {
  color: #6d6253;
}

.nav-item {
  color: #51483b;
  border-radius: 12px;
}

.nav-item .nav-icon {
  color: #766446;
}

.nav-item.active {
  background: #f5dfac;
  color: #513605;
  font-weight: 650;
}

.nav-item.active .nav-icon {
  color: #76501b;
}

.view-button:hover:not(.active) {
  background: #e9e1d2;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 5;
  background: #f7f4ed;
  border-color: #e7dfd2;
}

.breadcrumb span {
  color: #8a7c69;
}

.welcome-section h1 {
  color: var(--note-ink);
  letter-spacing: -.035em;
}

.date-card,
.capture-card,
.recent-card,
.auth-card {
  border-color: #e7e0d3;
  border-radius: 18px;
  background: #fffdf8;
}

.date-card strong,
.section-title,
.record-content strong {
  color: #302b23;
}

.capture-card {
  margin-bottom: 18px;
}

.capture-card textarea,
.record-title-input,
.category-filter,
.search-input-wrap {
  background: #f9f7f1;
  border-color: #e7e0d3;
  border-radius: 9px;
  color: #302b23;
}

.search-input-wrap input,
.record-content p {
  color: #51483b;
}

.search-input-wrap input::placeholder,
.capture-card textarea::placeholder {
  color: #786e60;
}

.auth-screen {
  background: #f7f4ed;
  color: #302b23;
}

.submit-button,
.search-submit,
.save-button {
  border-radius: 9px;
  background: #9b640c;
  color: #fff;
}

.submit-button:hover:not(:disabled),
.search-submit:hover:not(:disabled),
.save-button:hover:not(:disabled) {
  background: #825307;
}

.submit-button:disabled {
  background: #eadfc9;
  color: #695534;
}

.search-clear,
.record-action-button {
  border-radius: 8px;
}

.search-clear,
.edit-button,
.cancel-button,
.record-tag,
.record-category,
.record-icon {
  background: #f3ece0;
  border-color: #e7ddcc;
  color: #655539;
}

.record-item {
  border-bottom-color: #eee6d9;
  border-radius: 11px;
  transition: background-color 150ms ease;
}

.record-item:hover,
.record-item:focus-within {
  background: #faf7ef;
}

.record-pinned {
  background: #fff7e4;
  box-shadow: inset 3px 0 #be8a32;
}

.pin-indicator,
.pin-button {
  color: #735017;
  border: 1px solid #ecd8ad;
  background: #fff3d6;
}

.pin-indicator {
  border-radius: 8px;
  padding: 1px 8px;
}

.suggestion-panel {
  border-color: #ecd8ad;
  background: #fff8e9;
}

.empty-state {
  color: #6d6253;
}

.app-shell :is(button, input, select, textarea, a):focus-visible {
  outline: 2px solid #a8701a;
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .record-item {
    transition: none;
  }
}

@media (max-width: 420px) {
  .topbar {
    flex-wrap: wrap;
    height: auto;
    min-height: 66px;
    padding-block: 8px;
  }
}
.trash-policy {
  margin-block: 12px;
  padding: 10px 14px;
  border: 1px solid var(--note-border);
  border-radius: 10px;
  background: var(--note-field);
}

.trash-policy label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
}

.trash-policy input {
  accent-color: #9b640c;
}

.trash-policy p {
  margin: 3px 0 0;
  color: var(--note-muted);
  font-size: 13px;
}
.settings-page h1 {
  margin: 0 0 18px;
  color: var(--note-ink);
  font-size: 25px;
}

.settings-section + .settings-section {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid var(--note-border);
}

.settings-section h2 {
  margin: 0 0 10px;
  color: var(--note-ink);
  font-size: 15px;
}

.settings-fields {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.settings-fields input {
  min-width: 0;
}

.settings-counts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(104px, 1fr));
  gap: 8px;
  margin: 0;
}

.settings-counts div {
  padding: 9px 12px;
  border: 1px solid var(--note-border);
  border-radius: 10px;
  background: var(--note-field);
}

.settings-counts dt {
  color: var(--note-muted);
  font-size: 13px;
}

.settings-counts dd {
  margin: 2px 0 0;
  font-size: 21px;
  font-weight: 650;
}

.compact-records .record-item {
  padding-block: 7px;
}

.compact-records .record-actions {
  margin-top: 5px;
}
.links-dialog {
  width: min(640px, calc(100% - 32px));
  max-height: 85vh;
  margin: auto;
  padding: 20px;
  border: 1px solid var(--note-border);
  border-radius: 16px;
  background: #fffdf8;
  color: var(--note-ink);
}

.links-dialog::backdrop {
  background: #302b2366;
}

.links-toolbar,
.links-list li {
  display: flex;
  align-items: center;
  gap: 8px;
}

.links-toolbar {
  justify-content: space-between;
}

.links-toolbar h2 {
  flex: 1;
  margin: 0;
  font-size: 17px;
}

.linked-content {
  margin-bottom: 14px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.links-group h4 {
  margin: 14px 0 4px;
}

.links-list {
  padding: 0;
  list-style: none;
}

.links-list li {
  justify-content: space-between;
  margin-top: 6px;
  padding: 6px 0;
  border-bottom: 1px solid var(--note-border);
  overflow-wrap: anywhere;
}

.links-list li .search-clear {
  flex-shrink: 0;
}

.linked-title {
  padding: 5px;
  border: 0;
  text-align: left;
  background: transparent;
  color: #785018;
  font: inherit;
  cursor: pointer;
}

.linked-title:hover {
  text-decoration: underline;
}
.date-filter,
.record-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
}

.date-filter label {
  color: var(--note-muted);
  font-size: 13px;
}

.record-pagination {
  justify-content: center;
  margin-top: 14px;
  color: var(--note-muted);
  font-size: 13px;
}

.record-pagination button:disabled {
  opacity: .55;
  cursor: default;
}
.record-more {
  position: relative;
}

.record-more summary {
  list-style: none;
}

.record-more summary::-webkit-details-marker {
  display: none;
}

.record-more-actions {
  position: absolute;
  z-index: 4;
  right: 0;
  min-width: 105px;
  padding: 5px;
  top: 100%;
  background: #fffdf8;
  border: 1px solid var(--note-border);
  border-radius: 9px;
  box-shadow: 0 8px 24px #302b2325;
}

.record-more-actions button {
  display: block;
  width: 100%;
  padding: 7px 9px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--note-ink);
  text-align: left;
  white-space: nowrap;
  cursor: pointer;
}

.record-more-actions button:hover {
  background: var(--note-field);
}

.history-preview {
  padding: 12px;
  margin-top: 12px;
  border: 1px solid var(--note-border);
  border-radius: 10px;
  background: var(--note-field);
}

.history-preview .search-submit {
  margin-top: 10px;
}
.record-heading,
.note-detail-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
}

.record-title-link {
  min-width: 0;
  padding: 2px 3px 2px 0;
  border: 0;
  background: transparent;
  color: var(--note-ink);
  text-align: left;
  overflow-wrap: anywhere;
  font: inherit;
  font-weight: 650;
  cursor: pointer;
}

.record-title-link:hover {
  color: #875612;
  text-decoration: underline;
}

.note-icon-button {
  position: relative;
  flex: 0 0 30px;
  display: inline-grid;
  place-items: center;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 1px solid var(--note-border);
  border-radius: 8px;
  background: var(--note-field);
  color: #765623;
  cursor: pointer;
}

.note-icon-button:hover {
  background: #f5e6c8;
}

.copy-symbol {
  position: relative;
  width: 10px;
  height: 11px;
  margin: 3px 3px 0 0;
  border: 1.5px solid currentColor;
  border-radius: 2px;
}

.copy-symbol::after {
  position: absolute;
  inset: -4px -4px 2px 2px;
  border: 1.5px solid currentColor;
  border-radius: 2px;
  background: var(--note-field);
  content: '';
}

.history-symbol {
  position: relative;
  width: 14px;
  height: 14px;
  border: 1.5px solid currentColor;
  border-radius: 50%;
}

.history-symbol::after {
  position: absolute;
  inset: 2px 2px 4px 5px;
  border-left: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor;
  content: '';
}

.note-detail-title {
  margin: 14px 0 6px;
  overflow-wrap: anywhere;
}

.note-detail-meta,
.note-detail-actions {
  margin: 8px 0 12px;
}

.note-detail-links {
  padding-top: 8px;
  border-top: 1px solid var(--note-border);
}

.note-detail-dialog .edit-form {
  margin-top: 14px;
}
.record-item {
  cursor: pointer;
}

.record-item .record-excerpt {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  overflow-wrap: anywhere;
  white-space: pre-line;
}

.record-more summary {
  display: inline-block;
}

.record-title-link {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.app-shell {
  --note-border: #e7dccb;
  --note-field: #f7f1e8;
  --note-ink: #2c241b;
  --note-muted: #695945;
  background: #f3eee4;
}

.sidebar {
  background: #eae0d1;
  border-right-color: #dacdb9;
}

.brand {
  margin-bottom: 14px;
  padding-bottom: 19px;
  border-bottom: 1px solid #d9ccb7;
}

.nav-item.active {
  background: #ffebc0;
  box-shadow: 0 1px 3px #56380b24;
}

.nav-item.active .nav-icon {
  color: #8a5811;
}

.topbar {
  background: #fcf8ef;
  border-bottom-color: #e5d9c7;
  box-shadow: 0 2px 8px #49351b0a;
}

.content {
  max-width: 1120px;
  padding-top: 32px;
}

.welcome-section {
  align-items: flex-end;
  margin-bottom: 23px;
  padding: 3px 0 18px;
  border-bottom: 1px solid #ddd0bc;
}

.welcome-section h1 {
  font-size: clamp(24px, 4vw, 38px);
  font-weight: 740;
  line-height: 1.2;
}

.welcome-section p {
  margin-top: 6px;
}

.date-card {
  gap: 3px;
  flex-shrink: 0;
  padding: 8px 12px;
  background: #eee5d6;
  border-color: transparent;
  border-radius: 10px;
  color: var(--note-muted);
}

.date-card strong {
  font-size: 12px;
}

.capture-card {
  position: relative;
  border-left: 4px solid #bd8731;
  border-radius: 15px;
  background: #fffaf0;
  box-shadow: 0 8px 24px #50361810;
  margin-bottom: 23px;
}

.capture-heading {
  margin-bottom: 14px;
}

.section-title {
  margin: 0;
  font-size: 19px;
  line-height: 1.25;
  font-weight: 700;
}

.capture-card textarea {
  background: #fffdf8;
}

.capture-card textarea {
  min-height: 102px;
  margin-top: 0;
}

.capture-footer {
  padding-top: 10px;
  border-top: 1px solid #eee3cf;
}

.capture-footer .submit-button:not(:disabled) {
  background: #865714;
  box-shadow: 0 3px 7px #7045122f;
}

.recent-card {
  background: #fffdf9;
  border-radius: 15px;
  box-shadow: 0 5px 16px #5036180c;
}

.recent-heading {
  margin-bottom: 12px;
}

.library-filters {
  margin-bottom: 12px;
  padding: 8px 12px;
  border: 1px solid #eee4d6;
  border-radius: 11px;
  background: #f8f3ea;
}

.library-filters .search-toolbar {
  margin: 0;
}

.library-filters .saved-searches:empty {
  display: none;
}

.record-item {
  padding: 15px 10px;
  border-bottom-color: #eee5d7;
  transition: background-color 140ms ease;
}

.record-item .record-title-link {
  font-size: 16px;
  line-height: 1.45;
}

.record-item .record-excerpt {
  margin-top: 4px;
  font-size: 13px;
  color: #665848;
}

.record-item .record-icon {
  background: #f3e7d2;
  color: #8a6326;
}

.record-item .record-meta {
  color: #71614d;
}

.compact-records .record-item {
  padding-block: 7px;
}

@media (max-width: 600px) {
  .content {
    padding-top: 19px;
  }

  .welcome-section {
    margin-bottom: 15px;
    padding-bottom: 13px;
  }

  .library-filters {
    padding-inline: 8px;
  }

  .record-item {
    padding-inline: 5px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .record-item {
    transition: none;
  }
}
.app-shell,
.auth-screen {
  font-family: "Segoe UI Variable", "Microsoft YaHei UI", "PingFang SC", system-ui, sans-serif;
}

.note-detail-dialog {
  --reader-pad: clamp(18px, 6vw, 46px);
  width: min(720px, calc(100% - 24px));
  padding: 0;
  border-color: #e4d8c5;
  border-radius: 18px;
  background: #fffdf8;
  box-shadow: 0 25px 70px #34241135;
}

.note-reader-toolbar {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 58px;
  padding: 8px 18px;
  border-bottom: 1px solid #eee4d4;
  background: #fcf8ef;
}

.note-reader-toolbar h2 {
  flex: 1;
  margin: 0;
  color: #6d5b45;
  font-size: 13px;
  font-weight: 600;
}

.note-reader-tools {
  display: flex;
  align-items: center;
  gap: 5px;
}

.note-reader-toolbar .note-icon-button {
  min-height: 34px;
  width: 34px;
  border-color: transparent;
  background: transparent;
}

.note-reader-toolbar .note-icon-button:hover,
.note-toolbar-text:hover {
  background: #f4ead7;
}

.note-reader-toolbar .copy-symbol::after {
  background: #fcf8ef;
}

.note-toolbar-text {
  padding: 7px 9px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #7c541f;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.note-toolbar-text.note-edit-action {
  color: #68400c;
  background: #f6e5c2;
}

.note-close {
  font-size: 23px;
  line-height: 1;
}

.note-reader-main {
  padding: 0 var(--reader-pad);
}

.note-paper {
  padding: 29px 0 26px;
}

.note-paper-header {
  margin-bottom: 20px;
}

.note-paper .note-detail-title {
  margin: 0;
  font-size: clamp(25px, 5vw, 36px);
  line-height: 1.28;
  font-weight: 720;
  letter-spacing: -.02em;
}

.note-paper .note-detail-meta {
  gap: 7px;
  margin: 9px 0 0;
  color: #776956;
  font-size: 12px;
}

.note-detail-meta .record-category,
.note-detail-meta .record-tag {
  padding: 2px 7px;
  font-size: 12px;
  border-radius: 6px;
}

.note-paper .linked-content {
  margin: 0;
  color: #392f25;
  font-size: 16px;
  line-height: 1.85;
}

.note-web-link {
  display: inline-block;
  margin-top: 12px;
  color: #825621;
}

.note-reader-footer {
  position: relative;
  padding: 10px 0 19px;
  border-top: 1px solid #ece1cf;
}

.note-detail-links {
  padding-top: 0;
  border-top: 0;
}

.note-detail-links summary {
  display: list-item;
  width: fit-content;
  min-height: 34px;
  padding: 7px 5px;
  color: #5c4a34;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.note-link-count {
  margin-left: 7px;
  color: #796c5b;
  font-size: 12px;
  font-weight: 400;
}

.note-links-panel {
  margin-top: 8px;
  padding: 12px;
  border: 1px solid #eee3d2;
  border-radius: 10px;
  background: #f9f4eb;
}

.note-organize-action {
  position: absolute;
  top: 10px;
  right: 0;
}

.note-detail-dialog .edit-form {
  margin: 22px 0 0;
  padding-bottom: 22px;
}

.note-detail-dialog .edit-form textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--note-border);
  border-radius: 9px;
  background: var(--note-field);
  color: var(--note-ink);
  font: inherit;
  font-size: 15px;
  line-height: 1.65;
  resize: vertical;
}

@media (max-width: 480px) {
  .note-reader-toolbar {
    gap: 4px;
    padding-inline: 9px;
  }

  .note-paper {
    padding-top: 20px;
  }

  .note-paper .linked-content {
    font-size: 15px;
  }
}
.import-fields {
  margin-block: 9px;
}

.import-file-label {
  display: grid;
  gap: 4px;
  max-width: 100%;
  color: var(--note-muted);
  font-size: 13px;
}

.import-file-label input {
  max-width: 100%;
}

.import-review {
  padding: 10px 12px;
  border: 1px solid var(--note-border);
  border-radius: 10px;
  background: var(--note-field);
}

.import-review details {
  padding: 6px 0;
  overflow-wrap: anywhere;
}

.import-review summary {
  cursor: pointer;
}

.import-review details p {
  max-height: 180px;
  overflow: auto;
  white-space: pre-wrap;
}

.import-review button {
  margin: 8px 6px 0 0;
}

.import-warnings {
  padding-left: 20px;
  color: #775328;
  font-size: 13px;
}
.main-area {
  background: #f8f5ee;
}

.content {
  max-width: 1040px;
}

.recent-card {
  padding: clamp(16px, 3vw, 28px);
}

.library-heading h1 {
  margin: 0;
  color: var(--note-ink);
  font-size: clamp(22px, 3.2vw, 32px);
  font-weight: 720;
  line-height: 1.22;
  letter-spacing: -.025em;
}

.library-heading .section-description {
  margin-top: 5px;
}

.library-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.new-note-button {
  padding-inline: 14px;
  white-space: nowrap;
  font-weight: 650;
}

.export-menu {
  position: relative;
}

.export-menu > summary {
  display: grid;
  place-items: center;
  cursor: pointer;
  list-style: none;
}

.export-menu > summary::-webkit-details-marker {
  display: none;
}

.export-menu .export-controls {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 4;
  display: grid;
  width: min(220px, 65vw);
  padding: 12px;
  border: 1px solid var(--note-border);
  border-radius: 11px;
  background: #fffdf8;
  box-shadow: 0 8px 22px #302b2325;
}

.export-controls label {
  display: grid;
  gap: 4px;
  color: var(--note-muted);
  font-size: 13px;
}

.library-filters {
  background: transparent;
  border-color: transparent;
  border-bottom-color: var(--note-border);
  border-radius: 0;
  padding: 4px 0 9px;
}

.record-quick-actions {
  margin-left: auto;
}

.record-more summary.note-icon-button {
  display: inline-grid;
  font-size: 17px;
  font-weight: 700;
}

.record-more-actions .menu-discard {
  color: #a23831;
}

.record-heading {
  min-height: 32px;
}

.compose-dialog {
  width: min(860px, calc(100% - 24px));
  padding: clamp(14px, 4vw, 24px);
}

.compose-dialog .capture-form {
  margin-top: 15px;
}

.compose-dialog .capture-note-fields > textarea {
  display: block;
  width: 100%;
  min-height: 170px;
  padding: 12px;
  border: 1px solid var(--note-border);
  border-radius: 9px;
  background: #fffdf8;
  color: var(--note-ink);
  font: inherit;
  line-height: 1.65;
  resize: vertical;
}

@media (max-width: 600px) {
  .library-actions {
    margin-top: 4px;
  }
}
.content.split-content {
  max-width: 1520px;
  padding-inline: clamp(18px, 2vw, 34px);
}

.note-workspace.is-split {
  display: grid;
  grid-template-columns: minmax(345px, 0.9fr) minmax(390px, 1.15fr);
  align-items: start;
  gap: 16px;
}

.note-workspace.is-split > .recent-card {
  min-width: 0;
  padding-inline: 14px;
}

.note-workspace.is-split .library-heading h1 {
  font-size: 24px;
}

.note-workspace.is-split .search-toolbar {
  flex-wrap: wrap;
}

.note-workspace.is-split .search-input-wrap {
  order: -1;
  flex-basis: 100%;
}

.note-workspace.is-split .record-item {
  padding-inline: 8px;
}

.split-note-reader {
  position: sticky;
  top: 84px;
  width: auto;
  min-width: 0;
  max-height: calc(100vh - 103px);
  margin: 0;
  overflow: auto;
  border: 1px solid var(--note-border);
  box-shadow: 0 4px 14px #3424110e;
}

.split-note-reader .note-reader-main {
  --reader-pad: clamp(15px, 3vw, 35px);
}

.record-item.record-selected {
  background: #faedd3;
  box-shadow: inset 3px 0 #ac7322;
}

@media (min-width: 1180px) and (max-width: 1260px) {
  .split-content .note-workspace.is-split {
    grid-template-columns: minmax(336px, 0.9fr) minmax(370px, 1.15fr);
    gap: 12px;
  }
}
.library-segment {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  border-radius: 10px;
  background: #f1ece3;
}

.library-segment button {
  min-height: 30px;
  padding: 4px 12px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #695b48;
  font: inherit;
  font-size: 13px;
  white-space: nowrap;
  cursor: pointer;
}

.library-segment button[aria-pressed="true"] {
  background: #fffdf8;
  color: #422e18;
  font-weight: 650;
  box-shadow: 0 1px 2px #593c1728;
}

.library-record-results {
  min-width: 0;
}

.calendar-record-layout {
  display: grid;
  align-items: start;
  gap: 18px;
}

.calendar-results-heading {
  margin: 0 0 8px;
  color: var(--note-ink);
  font-size: 17px;
  font-weight: 700;
}

@media (min-width: 1024px) {
  .note-workspace:not(.is-split) .calendar-record-layout {
    grid-template-columns: minmax(320px, .95fr) minmax(300px, 1.05fr);
  }
}

@media (max-width: 480px) {
  .calendar-record-layout { gap: 12px; }
  .library-segment button { padding-inline: 8px; }
}

@media (max-width: 380px) {
  .calendar-record-layout .calendar { margin-inline: -8px; }
}
.note-date-field {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 0 0 10px;
  color: var(--note-muted);
  font-size: 13px;
}

.note-date-field span {
  font-size: 12px;
}
.daily-review {
  padding: 6px 10px;
  margin: 8px 0 12px;
  border: 1px solid var(--note-border);
  border-radius: 9px;
  background: #faf5ea;
}

.daily-review summary {
  padding: 6px 0;
  color: #674d2a;
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
}

.daily-review summary span {
  margin-left: 6px;
  color: var(--note-muted);
  font-size: 12px;
  font-weight: 400;
}

.daily-review textarea {
  display: block;
  width: 100%;
  min-height: 95px;
  margin: 5px 0 8px;
  padding: 8px 10px;
  border: 1px solid var(--note-border);
  border-radius: 8px;
  background: #fffdf8;
  color: var(--note-ink);
  font: inherit;
  resize: vertical;
}

.batch-controls .note-date-field {
  margin: 0;
}
.task-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.task-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 7px 10px;
  padding: 11px 5px;
  border-bottom: 1px solid var(--note-border);
}

.task-check {
  display: flex;
  flex: 1 1 180px;
  align-items: flex-start;
  gap: 7px;
  min-width: 0;
  overflow-wrap: anywhere;
}

.task-check input {
  margin-top: 4px;
  accent-color: #9b640c;
}

.task-completed .task-check span {
  color: var(--note-muted);
  text-decoration: line-through;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  color: var(--note-muted);
  font-size: 12px;
}

.task-meta button {
  max-width: 100%;
  overflow-wrap: anywhere;
  white-space: normal;
}

.task-overdue {
  color: #a23831;
}

.note-task-panel summary {
  width: fit-content;
  padding: 7px 5px;
  color: #5c4a34;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.note-task-panel summary span,
.task-form label {
  margin-left: 5px;
  color: var(--note-muted);
  font-size: 12px;
  font-weight: 400;
}

.task-form {
  margin-top: 10px;
}

.task-form > input {
  flex: 1 1 150px;
  min-width: 0;
}

.task-controls { border: 0; padding: 0; margin: 16px 0; min-width: 0; }
.task-filter-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 10px 0; }
.task-filter-row .search-input { flex: 1 1 200px; width: auto; min-width: 120px; }
.task-filter-row label { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 12px; color: var(--note-muted); }
.task-overview { display: grid; grid-template-columns: 1fr 1fr 2fr; gap: 16px; margin: 22px 0; padding: 20px; background: #faf7f1; border: 1px solid var(--note-border); border-radius: 14px; }
.task-overview > div { display: grid; align-content: start; gap: 6px; }
.task-overview strong { font-size: 26px; font-weight: 600; line-height: 1.2; }
.task-overview span { color: var(--note-muted); font-size: 12px; }
.task-progress progress { width: 100%; height: 6px; accent-color: #a66d12; }
.task-calendar { max-width: 480px; margin: 16px 0; }
.task-batch-bar { border: 1px solid #e8dcc6; background: #fffaf0; border-radius: 12px; margin: 16px 0; padding: 12px; min-width: 0; }
.task-batch-bar legend { color: #805b23; font-size: 13px; padding: 0 5px; }
.task-priority { border-radius: 5px; background: #f6ead1; color: #8a5b10; padding: 3px 6px; }
.task-priority.urgent { background: #fbeae6; color: #a23831; }
.task-controls:disabled, .task-batch-bar:disabled { opacity: .65; }
@media (max-width: 600px) { .task-overview { gap: 10px; padding: 14px; } .task-filter-row > .search-input { flex-basis: 100%; } }

</style>

<style scoped>
/* Zhiji / quiet workspace. Final visual layer; geometry and behavior stay in App.vue. */
.app-shell, .auth-screen {
  --note-border: #e8e5de;
  --note-field: #f8f7f4;
  --note-ink: #292825;
  --note-muted: #77746d;
  font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif;
  font-size: 14px;
  line-height: 1.6;
  letter-spacing: 0;
  color: var(--note-ink);
  background: #f6f5f2;
}
.main-area { background: #f6f5f2; }
.sidebar { background: #eeede8; border-right: 1px solid #e3e1da; padding-top: 24px; }
.brand { border-bottom: 0; padding-bottom: 24px; margin-bottom: 6px; gap: 11px; }
.brand-logo { width: 38px; height: 38px; border-radius: 10px; }
.brand-name { font-size: 21px; font-weight: 650; letter-spacing: .08em; }
.brand-subtitle { color: #77746d; font-size: 11px; letter-spacing: .03em; }
.nav-caption { color: #79766e; font-size: 11px; letter-spacing: .06em; padding-bottom: 12px; }
.nav-item { min-height: 44px; border-radius: 9px; gap: 12px; color: #5c5a53; margin-bottom: 4px; }
.nav-item .nav-icon { color: #77746d; width: 19px; height: 19px; }
.nav-item.active { background: #fff; color: #49391e; box-shadow: 0 1px 3px #2928250a; font-weight: 600; }
.nav-item.active .nav-icon { color: #9a6b23; }
.view-button:hover:not(.active) { background: #e5e3dc; }
.nav-item[aria-label="回收站"] { margin-top: 18px; }
.sidebar-footnote { margin-top: auto; padding: 30px 12px 4px; font-size: 11px; color: #817d74; letter-spacing: .06em; }
.topbar { min-height: 64px; background: #f6f5f2; border-bottom: 1px solid #e8e5de; padding-inline: 30px; }
.breadcrumb { color: #77746d; font-size: 12px; }
.breadcrumb span { color: #aaa69c; }
.topbar .search-clear { background: transparent; border-color: transparent; color: #69665e; min-height: 36px; }
.preview-label { background: #eeede8; color: #77746d; border: 0; font-size: 11px; }
.content { max-width: 1160px; padding: 30px clamp(18px, 3vw, 40px); }
.recent-card, .auth-card, .capture-card { background: #fff; border: 1px solid #e8e5de; border-radius: 16px; box-shadow: 0 3px 16px #29282504; }
.recent-card { padding: clamp(20px, 3vw, 32px); }
.recent-heading { align-items: center; gap: 16px; margin-bottom: 24px; }
.library-heading h1, .settings-page > h1 { font-size: 26px; line-height: 1.35; letter-spacing: -.025em; font-weight: 650; }
.section-description, .search-result-tip { color: #77746d; font-size: 12px; line-height: 1.7; }
.library-actions { gap: 8px; }
.search-submit, .submit-button, .save-button { background: #96651f; border-color: #96651f; color: #fff; box-shadow: 0 1px 2px #3d291316; font-weight: 600; }
.search-submit:hover:not(:disabled), .submit-button:hover:not(:disabled), .save-button:hover:not(:disabled) { background: #7e5216; }
.new-note-button { display: inline-flex; align-items: center; justify-content: center; gap: 7px; }
.search-clear, .record-action-button, .cancel-button { background: #fff; border-color: #e5e2da; color: #676258; }
.search-clear:hover:not(:disabled), .record-action-button:hover:not(:disabled) { background: #f5f3ee; }
.search-submit, .search-clear, .category-filter, .new-note-button { min-height: 40px; font-size: 13px; border-radius: 9px; }
.search-input-wrap { background: #f7f6f3; border-color: #e9e6df; border-radius: 9px; min-height: 42px; }
.search-input-wrap input { font: inherit; font-size: 14px; color: #3c3933; }
.search-input-wrap input::placeholder { color: #858077; }
.search-icon { color: #817c72; }
.category-filter, .record-title-input, .edit-form textarea, .tag-row input { background: #faf9f7; border-color: #e5e2da; color: #38352f; }
.library-filters { padding-bottom: 16px; border-bottom: 1px solid #eeece6; }
.library-segment { background: #f0eee9; padding: 4px; border-radius: 10px; }
.library-segment button { min-height: 34px; color: #777168; }
.library-segment button[aria-pressed="true"] { background: #fff; color: #4e4536; box-shadow: 0 1px 4px #29282510; }
.record-item { padding: 21px 12px; border-radius: 10px; border-bottom: 1px solid #eeece7; background: transparent; box-shadow: none; gap: 14px; }
.record-item:hover, .record-item:focus-within { background: #faf9f6; }
.record-item.record-pinned { background: #fdfaf3; box-shadow: inset 2px 0 #d7b777; }
.record-item.record-selected { background: #f6edda; box-shadow: inset 3px 0 #b68b43; }
.record-item .record-icon { width: 34px; height: 38px; border: 0; border-radius: 8px; background: #f4f2ed; color: #a18c66; display: grid; place-items: center; }
.record-item .record-title-link { font-size: 16px; font-weight: 600; line-height: 1.5; color: #302e28; letter-spacing: 0; }
.record-item .record-excerpt { font-size: 14px; line-height: 1.75; color: #78736a; margin-top: 5px; }
.record-item .record-meta { margin-top: 12px; gap: 8px; align-items: center; color: #817b71; font-size: 12px; }
.record-category, .record-tag { padding: 2px 7px; border: 0; border-radius: 5px; background: #f1efe9; color: #716650; font-size: 12px; font-weight: 400; }
.note-icon-button, .note-reader-toolbar .note-icon-button { width: 36px; min-height: 36px; border-radius: 8px; background: transparent; color: #817b70; border-color: transparent; display: inline-grid; place-items: center; }
.note-icon-button:hover, .note-reader-toolbar .note-icon-button:hover { color: #76511c; background: #eee8db; }
.record-more-actions, .export-menu .export-controls { background: #fff; border: 1px solid #e8e4da; border-radius: 12px; box-shadow: 0 8px 28px #29282518, 0 2px 6px #29282508; padding: 8px; }
.record-more-actions button { min-height: 38px; border-radius: 7px; font-size: 13px; }
.note-detail-dialog { background: #fff; border-color: #e5e1d7; box-shadow: 0 16px 60px #29282524; }
.note-reader-toolbar { background: #fcfbf8; border-color: #ede9e0; padding: 10px 18px; }
.note-reader-toolbar h2 { color: #81796d; letter-spacing: .04em; font-weight: 500; }
.note-paper { padding-block: 34px; }
.note-paper .note-detail-title { font-size: clamp(24px, 2.5vw, 30px); font-weight: 650; line-height: 1.5; letter-spacing: 0; color: #292825; }
.note-paper .note-detail-meta { margin-top: 12px; gap: 8px; color: #81796d; }
.note-paper .linked-content { max-width: 68ch; color: #45413b; font-size: 16px; line-height: 1.95; letter-spacing: .01em; }
.note-reader-footer { border-color: #ede9e0; padding-top: 16px; }
.note-links-panel, .suggestion-panel { background: #f8f6f1; border-color: #e8e2d6; }
.note-toolbar-text { color: #796346; font-weight: 500; }
.note-toolbar-text.note-edit-action { background: #f0e6d2; color: #72511f; }
.split-note-reader { box-shadow: 0 3px 12px #29282506; }
.settings-section { padding-block: 24px; border-color: #eeebe4; }
.settings-section h2 { font-size: 17px; font-weight: 600; margin-bottom: 12px; }
.task-overview { background: #f8f7f3; border-color: #ece8df; border-radius: 12px; }
.task-overview strong { font-size: 28px; font-variant-numeric: tabular-nums; font-weight: 600; }
.task-row { padding: 17px 8px; border-color: #eeebe5; gap: 10px; }
.task-check { font-size: 15px; line-height: 1.65; }
.task-meta { gap: 8px; color: #80776a; }
.task-batch-bar { background: #faf7ef; border-color: #e8dfcd; }
.empty-state { padding-block: 64px; color: #898174; font-size: 14px; line-height: 1.8; }
.app-shell :deep(.calendar) { background: #faf9f6; border-color: #e8e4da; border-radius: 13px; }
.app-shell :deep(.calendar-day) { background: #f0eee8; border-radius: 10px; }
.app-shell :deep(.calendar-day.calendar-selected) { background: #ede0c6; color: #735121; }
.app-shell :deep(.month-picker) { background: #fff; border-color: #e8e4da; }
.app-shell :deep(.category-picker input), .app-shell :deep(.category-picker select) { font-size: 14px; }
.note-icon-button, .nav-item, .search-clear, .search-submit { transition: background-color 140ms ease, color 140ms ease, box-shadow 140ms ease; }
.note-detail-dialog::backdrop, .links-dialog::backdrop { background: #29282545; backdrop-filter: blur(3px); }
@media (max-width: 760px) {
  .content { padding: 18px 14px; }
  .topbar { padding-inline: 16px; }
  .recent-card { padding: 20px 16px; }
  .recent-heading { gap: 12px; margin-bottom: 18px; }
  .record-item { padding-inline: 4px; gap: 10px; }
  .sidebar-footnote { display: none; }
  .note-paper { padding-block: 24px; }
  .note-icon-button { min-height: 40px; width: 40px; }
  .library-heading h1 { font-size: 23px; }
}

</style>

<style scoped>
.compose-dialog .capture-note-fields > textarea { margin-top: 16px; }
.compose-dialog .capture-footer { gap: 12px; align-items: center; flex-wrap: wrap; }
.compose-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; min-width: 0; }
.compose-word-count { font-size: 11px; color: #8a8275; }
.capture-date-menu { position: relative; }
.capture-date-menu > summary { display: inline-flex; align-items: center; gap: 7px; min-height: 36px; padding: 6px 9px; border-radius: 8px; background: #f5f2eb; color: #78664b; font-size: 12px; cursor: pointer; list-style: none; }
.capture-date-menu > summary::-webkit-details-marker { display: none; }
.capture-date-menu > summary:hover, .capture-date-menu[open] > summary { background: #eee5d5; color: #644b26; }
.capture-date-popover { position: absolute; bottom: calc(100% + 8px); left: 0; z-index: 5; width: min(260px, 72vw); padding: 16px; border: 1px solid #e6dfd2; border-radius: 12px; background: #fff; box-shadow: 0 8px 28px #302b2320; }
.capture-date-popover label { display: block; color: #574b38; font-size: 13px; margin-bottom: 8px; font-weight: 600; }
.capture-date-popover input { display: block; width: 100%; box-sizing: border-box; min-height: 40px; padding: 8px 10px; border: 1px solid #e5dfd3; border-radius: 8px; background: #faf9f6; font: inherit; color: #40382c; }
.capture-date-popover p { margin: 9px 0 12px; font-size: 11px; line-height: 1.6; color: #83796a; }
.capture-date-popover > div { display: flex; justify-content: space-between; gap: 10px; }
.capture-date-popover button { min-height: 34px; padding: 6px 12px; border: 0; border-radius: 7px; background: #f3eee4; color: #775a30; cursor: pointer; font: inherit; font-size: 12px; }
@media (max-width: 520px) { .compose-shortcut { display: none; } .compose-meta { gap: 8px; } }
</style>

<style scoped>
.reading-menu { position: relative; }
.reading-menu > summary { list-style: none; cursor: pointer; font-size: 15px; font-weight: 600; }
.reading-menu > summary::-webkit-details-marker { display: none; }
.reading-options { position: absolute; top: calc(100% + 8px); right: 0; z-index: 10; width: min(230px, 70vw); display: grid; gap: 14px; padding: 16px; background: #fff; border: 1px solid #e7e1d5; border-radius: 12px; box-shadow: 0 8px 28px #302b2320; font-size: 13px; color: #675b48; }
.reading-options label { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.reading-options select { padding: 7px; border: 1px solid #e7e1d5; border-radius: 7px; background: #faf8f4; color: inherit; font: inherit; }
.reading-options .reading-spacing { justify-content: flex-start; }
.reading-options small { color: #8a8173; font-size: 11px; }
.reading-statistics { margin: 0 0 18px; color: #8a8173; font-size: 11px; font-variant-numeric: tabular-nums; }
</style>

<style scoped>
.reader-find { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 16px; padding: 8px; background: #f8f6f1; border-radius: 8px; }
.reader-find input { flex: 1 1 130px; min-width: 0; padding: 7px; border: 1px solid #ded8cb; border-radius: 6px; }
.reader-find span { color: #746652; font-size: 12px; }
.linked-content mark { background: #f8e6ae; color: inherit; }
.linked-content mark[data-current-match] { background: #edbd66; scroll-margin: 80px 0 24px; }
</style>

<style scoped>
.reader-outline { display: grid; max-height: 180px; overflow: auto; gap: 3px; }
.reader-outline button { text-align: left; white-space: normal; overflow-wrap: anywhere; }
.linked-content [data-heading] { scroll-margin-top: 110px; }
</style>

<style scoped>
.writing-tools { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-top: 10px; }
.writing-tools button { display: inline-grid; place-items: center; min-width: 36px; min-height: 34px; padding: 5px; background: #f5f2eb; }
.writing-tools span { color: #a23831; font-size: 12px; }
.compose-dialog .capture-note-fields > textarea { margin-top: 6px; }
.compose-dialog[open] {
  display: flex;
  flex-direction: column;
  max-height: calc(100dvh - 24px);
  overflow: hidden;
}
.compose-dialog > .links-toolbar { flex: 0 0 auto; }
.compose-dialog .capture-form,
.compose-dialog .capture-note-fields {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.compose-dialog .capture-note-fields > * { flex: 0 0 auto; }
.compose-dialog .capture-note-fields > :deep(.formatted-editor-frame) {
  display: flex;
  flex: 0 1 auto;
  flex-direction: column;
  min-height: 0;
}
.compose-dialog .formatted-editor-frame :deep(.formatted-editor) {
  flex: 0 1 auto;
  min-height: 0;
}
.compose-dialog :deep(.capture-templates[open]) {
  max-height: min(36dvh, 320px);
  overflow: auto;
  overscroll-behavior: contain;
  flex-shrink: 0;
}
.compose-dialog :deep(.capture-templates.is-editing) { max-height: calc(100dvh - 120px); }
.app-shell > .sidebar {
  position: sticky;
  top: 0;
  align-self: flex-start;
  box-sizing: border-box;
  height: 100dvh;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior-y: contain;
}
.app-shell > .sidebar > * { flex-shrink: 0; }
.note-detail-dialog:is([open], .split-note-reader):has(.edit-form) {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
dialog.note-detail-dialog[open]:has(.edit-form) { max-height: calc(100dvh - 24px); }
.note-detail-dialog:has(.edit-form) > .note-reader-toolbar { flex: 0 0 auto; }
.note-detail-dialog:has(.edit-form) > .note-reader-main,
.note-detail-dialog .edit-form,
.note-detail-dialog .edit-body-field {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.note-detail-dialog .edit-form { margin-top: 16px; padding-bottom: 16px; }
.edit-form > :not(.edit-body-field), .edit-body-field > :not(.formatted-editor-frame) { flex-shrink: 0; }
.edit-body-field > :deep(.formatted-editor-frame) {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.edit-body-field .formatted-editor-frame :deep(.formatted-editor) { flex: 0 1 auto; min-height: 0; }
.edit-note-properties, .edit-form > .suggestion-panel {
  max-height: min(28dvh, 210px);
  overflow: auto;
  overscroll-behavior: contain;
}
.edit-note-properties { padding: 7px 10px; border: 1px solid var(--note-border); border-radius: 8px; }
.edit-note-properties summary { cursor: pointer; color: #736044; font-size: 13px; }
.edit-note-properties > .edit-field { margin-top: 10px; }
/* Keep the main controls in reach while a long result list scrolls. */
@media (min-height: 620px) {
  .library-list-card,
  .tasks-page:not(:has(.task-calendar)) {
    display: flex;
    flex-direction: column;
    max-height: calc(100dvh - 128px);
    min-height: 0;
  }
  .library-list-card > :not(.library-record-layout),
  .library-list-card .library-filters,
  .tasks-page > :not(.workspace-scroll-region) { flex-shrink: 0; }
  .library-list-card .library-record-layout,
  .library-list-card .library-record-results {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
  }
  .library-list-card .workspace-scroll-region,
  .tasks-page:not(:has(.task-calendar)) .workspace-scroll-region {
    min-height: 96px;
    overflow-y: auto;
    overscroll-behavior-y: contain;
    scrollbar-gutter: stable;
    padding: 0 6px 6px 2px;
    scroll-padding-block: 10px;
  }
  .library-list-card .library-filters { max-height: 36dvh; overflow-y: auto; }
  .tasks-page .task-batch-bar { max-height: 20dvh; overflow-y: auto; }
}
@media (min-width: 1024px) and (min-height: 620px) {
  .note-workspace .library-card:has(.calendar-record-layout) {
    display: flex;
    flex-direction: column;
    height: calc(100dvh - 128px);
  }
  .note-workspace:not(.is-split) .calendar-record-layout {
    flex: 1 1 auto;
    min-height: 0;
    align-items: stretch;
    grid-template-rows: minmax(0, 1fr);
  }
  .note-workspace:not(.is-split) .calendar-record-layout > :first-child {
    align-self: start;
    max-height: 100%;
    overflow-y: auto;
    overscroll-behavior-y: contain;
  }
  .note-workspace:not(.is-split) .calendar-record-layout .library-record-results {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .calendar-record-layout .library-record-results > :not(.workspace-scroll-region) { flex-shrink: 0; }
  .calendar-record-layout .daily-review { max-height: 24dvh; overflow-y: auto; }
  .calendar-record-layout .workspace-scroll-region {
    min-height: 88px;
    overflow-y: auto;
    overscroll-behavior-y: contain;
    scrollbar-gutter: stable;
    padding: 0 6px 6px 2px;
  }
  .note-workspace.is-split .library-card { position: sticky; top: 84px; }
  .note-workspace.is-split .calendar-record-layout,
  .note-workspace.is-split .calendar-record-layout .library-record-results {
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    min-height: 0;
  }
  .note-workspace.is-split .calendar-record-layout { gap: 10px; }
  .note-workspace.is-split .calendar-record-layout > :deep(.calendar) {
    flex: 0 1 auto;
    min-height: 64px;
    max-height: min(330px, 32dvh);
    overflow: auto;
    overscroll-behavior-y: contain;
    padding: 8px;
  }
  .note-workspace.is-split .calendar-record-layout :deep(.calendar-grid) { gap: 3px; }
  .note-workspace.is-split .calendar-record-layout :deep(.calendar-day) {
    min-height: 32px;
    padding: 2px;
    aspect-ratio: auto;
  }
  .note-workspace.is-split .calendar-record-layout :deep(.calendar-toolbar) { margin-bottom: 4px; }
  .note-workspace.is-split .calendar-record-layout .library-filters { max-height: 23dvh; overflow-y: auto; }
  .note-workspace.is-split .library-card .recent-heading { margin-bottom: 20px; }
  .note-workspace.is-split .library-card { padding-inline: clamp(18px, 1.65vw, 26px); }
}
.split-calendar-actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0 12px; }
.split-calendar-actions [aria-expanded="true"] { background: #f4ead6; }
.note-workspace.is-split .calendar-record-layout .workspace-scroll-region { border-top: 1px solid var(--note-border); margin-top: 12px; }
</style>
<style scoped>
.record-item.batch-record-active { cursor: pointer; user-select: none; }
.record-item.batch-record-selected, .record-item.batch-record-selected:hover { background: #f6edda; box-shadow: inset 3px 0 #b68b43; }
.search-clear.batch-trash-button { color: #963d32; }
</style>
<style scoped>
.reader-page-navigation { display: flex; align-items: center; justify-content: space-between; gap: 4px; padding-block: 8px; border-bottom: 1px solid var(--note-border); }
.reader-page-navigation span { color: var(--note-muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.reader-page-navigation [aria-disabled="true"] { opacity: .45; cursor: default; }
.reader-meta-action { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; padding: 3px 6px; }
.reader-meta-action[aria-pressed="true"] { background: #f4ead6; }
.reader-meta-filter { white-space: normal; overflow-wrap: anywhere; }
.reader-meta-filter:hover { background: #eee2ca; }
.active-library-filters { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-block: 6px; color: var(--note-muted); font-size: 12px; }
.active-library-filters .record-tag { max-width: 100%; overflow-wrap: anywhere; }
.saved-search-preview { flex-basis: 100%; color: var(--note-muted); font-size: 12px; overflow-wrap: anywhere; }
.quick-saved-searches button { max-width: min(180px, 100%); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.quick-saved-searches button[aria-pressed="true"] { background: #efe2c8; color: #654719; }
.saved-search-order { display: inline-flex; flex-wrap: wrap; gap: 4px; }
</style>
<style scoped>
.draft-continue-button { background: #f4ead6; color: #76511c; cursor: pointer; }
.draft-continue-button:hover { background: #eddbb9; }
</style>
<style scoped>
.calendar-day-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; justify-content: space-between; margin-bottom: 10px; }
.calendar-day-strip .calendar-results-heading { margin: 0; }
.library-card:has(.calendar-record-layout) { overflow-anchor: none; }
.calendar-record-layout .workspace-scroll-region { overflow-anchor: none; }
.calendar-day-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; }
.calendar-day-actions .search-clear { min-height: 34px; padding-inline: 9px; }
.calendar-date-jump { position: relative; }
.calendar-date-jump summary { list-style: none; display: flex; align-items: center; gap: 6px; cursor: pointer; font-variant-numeric: tabular-nums; }
.calendar-date-jump summary::-webkit-details-marker { display: none; }
.calendar-date-jump input { position: absolute; top: calc(100% + 6px); right: 0; background: #fff; z-index: 5; box-shadow: 0 5px 16px #302b231a; }
</style>

<style scoped>
.review-entry { display: flex; align-items: center; gap: 9px; width: 100%; margin: 8px 0 12px; padding: 11px 13px; border: 1px solid var(--note-border); border-radius: 9px; color: #705832; background: #f9f6ee; font: inherit; cursor: pointer; text-align: left; }
.review-entry strong { flex: 1; }
.review-entry span { font-size: 12px; }
.review-entry:hover { background: #f3ecdc; }
.review-reading { min-height: 0; max-height: 60dvh; overflow-y: auto; overscroll-behavior-y: contain; padding: 16px 2px; line-height: 1.85; }
.review-reading-footer { flex-shrink: 0; }
.review-day-navigation { flex-shrink: 0; display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 4px; }
.review-day-navigation .search-clear { min-height: 34px; }
.review-export-menu { position: relative; }
.review-export-menu > summary { list-style: none; display: flex; align-items: center; cursor: pointer; }
.review-export-menu > summary::-webkit-details-marker { display: none; }
.review-export-menu .record-more-actions { top: auto; bottom: calc(100% + 6px); }
.review-outline-menu { margin-top: 7px; }
.review-outline-menu summary { width: fit-content; }
.review-outline-panel { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; padding: 8px; border: 1px solid var(--note-border); border-radius: 8px; font-size: 13px; }
.review-outline-panel ul { margin-block: 4px; padding-inline-start: 20px; }
</style>
<style scoped>
.attachment-editor { margin-block: 8px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.attachment-action { position: relative; display: inline-flex; align-items: center; gap: 6px; text-decoration: none; cursor: pointer; }
.attachment-action input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.attachment-action:focus-within { outline: 2px solid #a56d19; outline-offset: 2px; }
.attachment-action:has(input:disabled) { opacity: .55; }
.attachment-list { list-style: none; padding: 0; margin: 8px 0; }
.attachment-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 10px 4px; border-bottom: 1px solid var(--note-border); }
.attachment-row a { text-decoration: none; }
.attachment-file-info { display: grid; gap: 2px; flex: 1 1 125px; min-width: 0; overflow-wrap: anywhere; }
.queued-attachments { width: 100%; max-height: 18dvh; overflow: auto; }
.queued-attachments .attachment-row { padding-block: 3px; font-size: 13px; }
.queued-attachments { max-height: 150px; overflow: auto; }
.queued-attachments :deep(.attachment-preview img),
.queued-attachments :deep(.attachment-preview video) { max-height: 100px; max-width: min(100%, 220px); }
.attachment-folder-path { overflow-wrap: anywhere; }
.attachment-folder-picker { margin-top: 12px; padding: 12px; border: 1px solid var(--note-border); border-radius: 12px; background: var(--note-field); }
.attachment-folder-list { list-style: none; padding: 0; margin: 12px 0; max-height: 240px; overflow: auto; display: grid; gap: 4px; }
.attachment-folder-list button { width: 100%; display: flex; justify-content: space-between; text-align: left; overflow-wrap: anywhere; }
.attachment-filters { margin-bottom: 12px; }
.note-attachment-section { margin-bottom: 16px; }
.note-attachment-section h3 { font-size: 15px; margin-bottom: 4px; }
</style>
