import test from 'node:test'
import assert from 'node:assert/strict'
import { execSync } from 'node:child_process'

// Exercise the documented npm commands even when node_modules/.bin has no
// Windows .cmd shims (the existing pnpm dependency tree remains authoritative).
test('documented typecheck and lint commands resolve project-local tools', () => {
  for (const command of ['npm run typecheck -- --version', 'npm run lint -- --version']) {
    const result = execSync(command, { encoding: 'utf8', timeout: 30000 })
    assert.match(result, /\d+\.\d+\.\d+/)
  }
})
