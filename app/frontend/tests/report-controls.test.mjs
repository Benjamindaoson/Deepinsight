import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import ts from 'typescript'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import * as reportArtifact from '../src/lib/report-artifact.ts'
import * as marketApi from '../src/lib/market-api.ts'

// The test runner strips TypeScript but not JSX. Compile the actual component
// in memory; only its CSS module is omitted from server-rendered markup.
const require = createRequire(import.meta.url)
const componentPath = new URL('../src/components/market/InstitutionalReport.tsx', import.meta.url)
const compiled = ts.transpileModule(readFileSync(componentPath, 'utf8'), {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    jsx: ts.JsxEmit.ReactJSX,
    esModuleInterop: true
  }
}).outputText
const componentModule = { exports: {} }
new Function('require', 'exports', 'module', compiled)(
  (specifier) => {
    if (specifier === '@/lib/report-artifact') return reportArtifact
    if (specifier === '@/lib/market-api') return marketApi
    if (specifier.endsWith('.module.css')) return {}
    return require(specifier)
  },
  componentModule.exports,
  componentModule
)
const InstitutionalReport = componentModule.exports.default

function renderReport(generatedAt = '2026-10-18T23:30:00+00:00') {
  return renderToStaticMarkup(React.createElement(InstitutionalReport, {
    report: {
      schema_version: '1.0', report_id: 'saved/report-1', title: 'Saved report',
      report_type: 'market_report', generated_at: generatedAt,
      query: 'London office rent', scope: { metrics: ['rent'] },
      geographies: ['City'], observation_period: '2026Q2', generation_status: 'partial',
      executive_summary: [], key_findings: [], risks: [], opportunities: [], outlook: [],
      charts: [], market_snapshot: [], regional_comparison: [], data_gaps: [],
      limitations: [], evidence: [],
      publication_review: { status: 'pending', codes: [], semantic_approval: false },
      acquisition: { mode: 'saved', notice: 'Saved source records' }
    },
    renderChart: () => null
  }))
}

test('report actions retain inline HTML and download the same stored report in all three formats', () => {
  const markup = renderReport()
  const links = [...markup.matchAll(/<a\b([^>]+)>([^<]+)<\/a>/g)]
  const printable = links.find((match) => match[2] === 'Print / HTML report')
  assert.ok(printable)
  assert.ok(printable[1].includes(`href="${marketApi.MARKET_API}/reports/saved%2Freport-1?format=html"`))
  assert.doesNotMatch(printable[1], /\bdownload(?:=|\s|$)/)
  for (const [format, label] of [['html', 'Download HTML'], ['markdown', 'Markdown'], ['json', 'JSON']]) {
    const link = links.find((match) => match[2] === label)
    assert.ok(link, `${label} export action must be visible`)
    const query = `format=${format}&amp;download=true`
    assert.ok(link[1].includes(`href="${marketApi.MARKET_API}/reports/saved%2Freport-1?${query}"`))
    assert.match(link[1], /\bdownload(?:=|\s|$)/)
  }
})

test('Prepared gives the UTC zone and time explicitly across local-date rollover', () => {
  const markup = renderReport()
  assert.match(markup, /Prepared \(UTC\)/)
  assert.match(markup, /<time dateTime="2026-10-18T23:30:00\+00:00">18 October 2026(?:,| at) 23:30 UTC<\/time>/)
  const offsetMarkup = renderReport('2026-10-19T07:30:00+08:00')
  assert.match(offsetMarkup, /<time dateTime="2026-10-19T07:30:00\+08:00">18 October 2026(?:,| at) 23:30 UTC<\/time>/)
})
