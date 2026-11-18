import assert from 'node:assert/strict'
import { test } from 'node:test'
import { reviewMarkdown } from '../src/reviewExport.ts'

test('exports the selected day and preserves Markdown and leading indentation', () => {
  assert.deepEqual(reviewMarkdown('2026-11-18', '    代码\n\n## 收获\n- [x] 完成\n\n'), {
    filename: '知己-每日回顾-2026-11-18.md',
    text: '# 2026-11-18 每日回顾\n\n    代码\n\n## 收获\n- [x] 完成\n',
  })
})

test('rejects empty content and malformed day keys', () => {
  assert.equal(reviewMarkdown('2026-11-18', ' \n '), null)
  assert.equal(reviewMarkdown('../review', '已写'), null)
})
