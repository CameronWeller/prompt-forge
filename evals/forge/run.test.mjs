// node --test evals/forge/run.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { checks, decide, extractPrompt, forgeSystem, parseCase, parseScores } from './run.mjs'

const row = (id, split, score, hard = []) => ({ id, split, score, hard })

test('the forge rules come out of register.tsx, STOP included, without running it', () => {
  const s = forgeSystem(readFileSync(new URL('../../hooks/register.tsx', import.meta.url), 'utf8'))
  assert.ok(s.startsWith('You are the prompt forge') && s.includes('"Hand back when:"') && s.includes('output exactly PASS'))
  assert.throws(() => extractPrompt("const GATE = [\n 'a', process.exit(1),\n].join('\\n')", 'GATE'), /plain string lines/)
})

test('deterministic checks: the gate, required sections and dropped exact tokens', () => {
  const c = parseCase('x.md', '---\nsplit: train\nexpect: brief\n---\nspeed up `reports/weekly.csv`')
  assert.deepEqual(checks(c, 'PASS').gateRight, false)
  const k = checks(c, 'OUTCOME: fast\nVERIFY: time it\nSTOP: Done when: under 10 s\nBOUNDS: none\nASSUMPTIONS: - x')
  assert.deepEqual(k.missingSections, [])
  assert.ok(k.dropped.includes('reports/weekly.csv'))
})

test('a version ships only with no new hard failure and no held-out loss', () => {
  assert.equal(decide([row('a', 'heldout', 10)], [row('a', 'heldout', 12)]).ship, true)
  assert.equal(decide([row('a', 'heldout', 12)], [row('a', 'heldout', 10)]).ship, false)
  assert.equal(decide([row('a', 'heldout', 10), row('b', 'train', 9)],
    [row('a', 'heldout', 14), row('b', 'train', 12, ['authority widened'])]).ship, false)
  assert.equal(decide([row('a', 'train', 1)], [row('a', 'train', 14)]).ship, false) // no held-out evidence
})

test('judge replies must be the JSON scores, each 0 to 2', () => {
  const ok = '{"outcome":2,"checkable":1,"verify":2,"loop":0,"authority":2,"assumptions":1,"fidelity":2,"worst":"w"}'
  assert.equal(parseScores(`Here you go: ${ok}`).loop, 0)
  assert.throws(() => parseScores(ok.replace('"loop":0', '"loop":5')), /not 0, 1 or 2/)
  assert.throws(() => parseScores('no json'), /no JSON/)
})
