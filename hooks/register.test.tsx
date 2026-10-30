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
  on('prompt.submit', (_: any, e: any) => ({ ...e }))
  on('session.append', (_: any, e: any, next: any) => (appended.push(e), next(e)))
  on('ui.render', ($: any, e: any) => {
    const { Text } = $.ui.resolve(e)
    return <Text>{`> ${e.props.text}`}</Text>
  })
}

const ROW = (text: string) =>
  ({
    plugin: 'prompt-forge',
    component: 'UserMessage',
    requestId: 'm1',
    surface: 'terminal',
    props: { text, origin: { kind: 'composer' }, isExpanded: false },
  }) as const

// The notice after a prompt's row (session.append, door 'prompt') is raised only by the engine,
// so it is checked end to end with `claude -p --plugin-dir` and the transcript file instead.

test('the terminal row shows your original words', async ($, on) => {
  stubs(on, [])
  await $.prompt.submit({ text: ORIGINAL })
  const ui = await $.ui.mount(ROW(BRIEF))
  expect((await ui.find({ type: 'Text', text: /^> / }))?.text).toBe(`> ${ORIGINAL}`)
  await ui.unmount()
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
