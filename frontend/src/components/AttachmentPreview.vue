<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ kind?: 'image' | 'video'; name: string; src: string }>()
const failed = ref(false)
watch(() => props.src, () => { failed.value = false })
</script>

<template>
  <div class="attachment-preview">
    <p v-if="failed" role="status">无法显示附件，可下载后查看。</p>
    <a v-else-if="kind === 'image'" :href="src" target="_blank" rel="noopener" :aria-label="'查看原图 ' + name">
      <img :src="src" :alt="name" loading="lazy" decoding="async" @error="failed = true" />
    </a>
    <video v-else :src="src" :aria-label="name" controls playsinline preload="metadata" @error="failed = true" />
  </div>
</template>

<style scoped>
.attachment-preview {
  flex-basis: 100%;
  min-width: 0;
}
.attachment-preview img,
.attachment-preview video {
  display: block;
  max-width: min(100%, 480px);
  max-height: 280px;
  border-radius: 10px;
  object-fit: contain;
}
.attachment-preview video {
  width: 100%;
}
.attachment-preview p {
  margin: 0;
  font-size: 13px;
}
</style>
