<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ text: string }>()
const lines = computed(() => {
  let offset = 0
  let fence = ''
  return props.text.split('\n').map(raw => {
    const start = offset
    offset += raw.length + 1
    const line = raw.replace(/\r$/, '')
    const token = /^ {0,3}(~{3,}|\x60{3,})(.*)$/.exec(line)
    if (fence || token) {
      if (!fence && token) fence = token[1]!
      else if (token && token[1]![0] === fence[0] && token[1]!.length >= fence.length && !token[2]!.trim()) fence = ''
      return { tag: 'p', text: line, marker: '', anchor: undefined }
    }
    const heading = /^ {0,3}(#{1,6})[ \t]+(.*)$/.exec(line)
    if (heading) return { tag: 'h' + heading[1]!.length, text: heading[2]!.replace(/\s+#+\s*$/, ''), marker: '', anchor: start }
    const task = /^[-*] +\[([ xX])\] *(.*)$/.exec(line)
    if (task) return { tag: 'p', text: task[2], marker: task[1] === ' ' ? '☐' : '☑', anchor: undefined }
    const numbered = /^(\d{1,9}\.) +(.*)$/.exec(line)
    if (numbered) return { tag: 'p', text: numbered[2], marker: numbered[1], anchor: undefined }
    if (line.startsWith('> ')) return { tag: 'blockquote', text: line.slice(2), marker: '', anchor: undefined }
    const bullet = /^[-*] +(.*)$/.exec(line)
    return { tag: 'p', text: bullet ? bullet[1] : line, marker: bullet ? '•' : '', anchor: undefined }
  })
})
</script>

<template>
  <section class="writing-preview" aria-label="笔记正文">

    <component :is="line.tag" v-for="(line, index) in lines" :key="index" :data-heading="line.anchor" :tabindex="line.anchor === undefined ? undefined : -1">
      <span v-if="line.marker" class="marker">{{ line.marker }}</span>{{ line.text || '\u00a0' }}
    </component>
  </section>
</template>

<style scoped>
.writing-preview { overflow-wrap: anywhere; white-space: pre-wrap; }
.writing-preview h1 { font-size: 1.56em; margin: .7em 0 .3em; }
.writing-preview h2 { font-size: 1.25em; margin: .65em 0 .25em; }
.writing-preview p { margin: 0; }
.writing-preview [data-heading] { scroll-margin-top: 110px; }
.writing-preview blockquote { margin: 0; border-inline-start: 2px solid var(--zh-accent); padding: 4px 10px; color: var(--zh-muted); background: var(--zh-field); }
.marker { display: inline-block; min-width: 20px; color: var(--zh-muted); }
</style>
