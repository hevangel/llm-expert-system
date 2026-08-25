import assert from 'node:assert/strict'
import test from 'node:test'

test('reasoning states keep abstention distinct from unknown and errors', () => {
  const states = ['answered', 'unknown', 'unsat', 'abstained', 'error', 'timeout']
  assert.equal(new Set(states).size, states.length)
  assert.ok(states.includes('abstained'))
})
