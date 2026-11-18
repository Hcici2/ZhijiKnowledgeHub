<script setup lang="ts">
withDefaults(defineProps<{ name: string, size?: number }>(), { size: 20 })
const paths: Record<string, string> = {
  inbox: 'M4 4h16v16H4z M4 13h5l2 3h2l2-3h5',
  library: 'M4 4h6v16H4z M14 4l5-1 3 16-5 1z M4 8h6 M4 16h6',
  web: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M3 12h18 M12 3c5 5 5 13 0 18-5-5-5-13 0-18',
  pinned: 'M9 3h6l-1 6 4 4v2H6v-2l4-4z M12 15v6',
  recent: 'M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v5l3 2',
  trash: 'M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7',
  tasks: 'M9 5h11 M9 12h11 M9 19h11 M3 5l1 1 2-3 M3 12l1 1 2-3 M3 19l1 1 2-3',
  settings: 'M12 3v3 M12 18v3 M3 12h3 M18 12h3 M5.6 5.6l2.1 2.1 M16.3 16.3l2.1 2.1 M5.6 18.4l2.1-2.1 M16.3 7.7l2.1-2.1 M18 12a6 6 0 1 1-12 0 6 6 0 0 1 12 0 M14 12a2 2 0 1 1-4 0 2 2 0 0 1 4 0',
  note: 'M6 3h9l4 4v14H6z M14 3v5h5 M9 12h7 M9 16h5',
  search: 'M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0 M15 15l6 6',
  plus: 'M12 5v14 M5 12h14',
  copy: 'M9 8h11v13H9z M5 16H3V3h11v2',
  more: 'M5 12h.01 M12 12h.01 M19 12h.01',
  close: 'M6 6l12 12 M18 6L6 18',
  calendar: 'M4 5h16v16H4z M8 3v4 M16 3v4 M4 10h16 M8 14h2 M14 14h2 M8 18h2',
  'clear-format': 'M4 5h13 M10.5 5v13 M7 18h7 M16 13l5 5 M21 13l-5 5',
  'numbered-list': 'M2 5l2-1v5 M2 9h4 M2 14a2 2 0 0 1 4 0c0 2-4 3-4 5h4 M9 7h12 M9 16h12',
  quote: 'M4 16v-4c0-3 2-5 5-6 M4 12h6v6H4z M14 16v-4c0-3 2-5 5-6 M14 12h6v6h-6z',
  heading: 'M4 5v14 M13 5v14 M4 12h9 M17 11l2-2v10 M17 19h4',
  subheading: 'M4 5v14 M13 5v14 M4 12h9 M17 11a2 2 0 0 1 4 0c0 3-4 4-4 8h4',
  list: 'M8 5h13 M8 12h13 M8 19h13 M3 5h.01 M3 12h.01 M3 19h.01',
  download: 'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5'
}
</script>
<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    :stroke-width="name === 'more' ? 3.5 : 1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path :d="paths[name] || paths.note" />
  </svg>
</template>
<style scoped>svg { flex-shrink: 0; display: inline-block; vertical-align: middle; pointer-events: none; }</style>
