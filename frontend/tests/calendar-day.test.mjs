import assert from 'node:assert/strict'
import { test } from 'node:test'
import { adjacentCalendarDay } from '../src/calendarDay.ts'

test('steps across month, leap day and year boundaries', () => {
  assert.equal(adjacentCalendarDay('2028-03-01', -1), '2028-02-29')
  assert.equal(adjacentCalendarDay('2026-12-31', 1), '2027-01-01')
  assert.equal(adjacentCalendarDay('2027-01-01', -1), '2026-12-31')
})

test('respects the supported calendar range', () => {
  assert.equal(adjacentCalendarDay('0001-01-01', -1), null)
  assert.equal(adjacentCalendarDay('9998-12-31', 1), null)
  assert.equal(adjacentCalendarDay('0001-01-01', 1), '0001-01-02')
  assert.equal(adjacentCalendarDay('invalid', 1), null)
})
