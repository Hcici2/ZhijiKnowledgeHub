<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

const props = defineProps<{
  categories: string[]
  label: string
  id?: string
  disabled?: boolean
}>()

const category = defineModel<string>({ required: true })
const enteringCategory = ref(false)
const newCategoryInput = ref<HTMLInputElement | null>(null)

const selection = computed<string | null>({
  get() {
    if (props.categories.includes(category.value)) return category.value
    return category.value || enteringCategory.value ? null : ''
  },
  set(value) {
    enteringCategory.value = value === null
    category.value = value ?? ''
    if (value === null) void nextTick(() => newCategoryInput.value?.focus())
  }
})
</script>

<template>
  <div class="category-picker">
    <select :id="id" v-model="selection" :aria-label="label" :disabled="disabled">
      <option value="" disabled>选择分类</option>
      <option v-for="item in categories" :key="item" :value="item">
        {{ item === 'AI工具' ? 'AI 工具' : item }}
      </option>
      <option :value="null">＋ 输入新分类</option>
    </select>
    <input
      v-if="selection === null"
      ref="newCategoryInput"
      v-model="category"
      aria-label="新分类名称"
      placeholder="输入新分类名称"
      maxlength="50"
      :disabled="disabled"
    />
  </div>
</template>

<style scoped>
.category-picker {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.category-picker select,
.category-picker input {
  flex: 1 1 140px;
  min-width: 0;
  width: 100%;
  min-height: 42px;
  padding: 8px 12px;
  border: 1px solid var(--note-border, #dce7fc);
  border-radius: 8px;
  background: var(--note-field, #fafbfd);
  color: var(--note-ink, #34445a);
  font: inherit;
}
</style>
