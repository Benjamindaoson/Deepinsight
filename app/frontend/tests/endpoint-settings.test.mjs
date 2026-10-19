import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import ts from 'typescript'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import * as utils from '../src/lib/utils.ts'

const componentPath = new URL('../src/components/workspace/EndpointSettings.tsx', import.meta.url)
function loadSettings() {
  assert.ok(existsSync(componentPath), 'Connection settings must provide an editable endpoint form')
  const compiled = ts.transpileModule(readFileSync(componentPath, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true }
  }).outputText
  const require = createRequire(import.meta.url)
  const module = { exports: {} }
  new Function('require', 'exports', 'module', compiled)(
    (specifier) => specifier === '@/lib/utils' ? utils : require(specifier),
    module.exports, module
  )
  return module.exports
}

test('connection settings render a labelled editable URL and normal Save form', () => {
  const { default: EndpointSettings } = loadSettings()
  const markup = renderToStaticMarkup(React.createElement(EndpointSettings, {
    endpoint: 'http://127.0.0.1:8000', onSave: () => {}, disabled: false
  }))
  assert.match(markup, /<form\b/)
  assert.match(markup, /<label[^>]*for="agentos-endpoint"[^>]*>AgentOS endpoint<\/label>/)
  assert.match(markup, /<input[^>]*id="agentos-endpoint"[^>]*type="url"[^>]*value="http:\/\/127\.0\.0\.1:8000"/)
  assert.match(markup, /<button[^>]*type="submit"[^>]*>Save connection<\/button>/)
})

test('endpoint save updates the destination with a trimmed valid service URL', () => {
  const { saveEndpoint } = loadSettings()
  const saved = []
  assert.equal(saveEndpoint('  http://127.0.0.1:7808/  ', (value) => saved.push(value)), true)
  assert.deepEqual(saved, ['http://127.0.0.1:7808'])
})

test('invalid destinations or credentials never update the connection', () => {
  const { saveEndpoint } = loadSettings()
  const saved = []
  for (const value of ['', 'not a URL', 'javascript:alert(1)', 'file:///tmp/service',
    'http://127.0.0.1:99999', 'http://key:secret@127.0.0.1:7808',
    'http://127.0.0.1:7808?api_key=secret', 'http://127.0.0.1:7808#secret']) {
    assert.equal(saveEndpoint(value, (url) => saved.push(url)), false, value)
  }
  assert.deepEqual(saved, [])
})
