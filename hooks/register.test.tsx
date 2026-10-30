import { expect, test } from 'claude-code/testing'

const BRIEF = 'OUTCOME: Ship the invite flow.\nWHY: teammates join.\nDO: build it.'
const ORIGINAL = 'ship the invite flow so teammates can join'

function stubs(on: any, appended: any[], complete = () => ({ value: { isAnswered: true, text: BRIEF } })) {
  const kept = new Map<string, unknown>()
  on('store.set', (_: any, e: any) => (kept.set(e.key, e.value), { value: undefined }))
  on('store.get', (_: any, e: any) => ({ value: kept.get(e.key) }))
  on('store.keys', () => ({ value: [...kept.keys()] }))
  on('store.delete', (_: any, e: any) => (kept.delete(e.key), { value: undefined }))
  on('session.turns', () => ({ value: 0 }))
  on('model.complete', complete)
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('ui.log', () => ({ value: undefined }))
  on('clock.after', () => ({ value: { cancel: () => undefined } }))
  on('prompt.submit', (_: any, e: any) => ({ ...e }))
  on('session.append', (_: any, e: any, next: any) => (appended.push(e), next(e)))
  on('ui.render', ($: any, e: any) => {
    const { Text } = $.ui.resolve(e)
    return <Text>{`> ${e.props.text}`}</Text>
  })
}

test('a forged prompt is held, and the brief is sent as the next message', async ($, on) => {
  const appended: any[] = []
  stubs(on, appended)
  const r: any = await $.prompt.submit({ text: ORIGINAL })
  expect(r.drop).toContain('The next message is what the agent receives')
  const notes = appended.filter(e => e.message.type === 'system').map(e => e.message.content[0].text)
  expect(notes.some(n => n.includes('your original prompt') && n.includes(ORIGINAL))).toBe(true)
})

test('the resent brief is not forged again', async ($, on) => {
  let forged = 0
  stubs(on, [], () => (forged++, { value: { isAnswered: true, text: BRIEF } }))
  await $.prompt.submit({ text: BRIEF + ' ' + 'word '.repeat(60), origin: { kind: 'plugin', name: 'prompt-forge' } } as any)
  expect(forged).toBe(0)
})

test('harness-wrapped prompts are never forged', async ($, on) => {
  const appended: any[] = []
  let forged = 0
  stubs(on, appended, () => (forged++, { value: { isAnswered: true, text: BRIEF } }))
  await $.prompt.submit({ text: '<system-reminder>\nrules\n</system-reminder>\nplease start the task now' })
  expect(forged).toBe(0)
})

test('a transient API error is retried once', async ($, on) => {
  let calls = 0
  stubs(on, [], () => {
    calls++
    return { value: calls === 1 ? { isAnswered: false, reason: 'api-error', status: 529 } : { isAnswered: true, text: BRIEF } }
  })
  await $.prompt.submit({ text: ORIGINAL })
  expect(calls).toBe(2)
})

test('a prompt too large to forge says so in the chat', async ($, on) => {
  const appended: any[] = []
  let forged = 0
  stubs(on, appended, () => (forged++, { value: { isAnswered: true, text: BRIEF } }))
  await $.prompt.submit({ text: 'word '.repeat(6000) })
  expect(forged).toBe(0)
  const notices = appended.filter(e => e.message.type === 'system')
  expect(notices.length).toBe(1)
  expect(notices[0].message.content[0].text).toContain('not forged')
})
