const HEADERS = { 'Content-Type': 'application/json' }

async function api(path, opts = {}) {
  const res = await fetch('/api' + path, opts)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json()
}

export const get = (p) => api(p)
export const post = (p, body) => api(p, { method: 'POST', headers: HEADERS, body: JSON.stringify(body || {}) })

/** SSE/NDJSON 流式对话 */
export async function* chatStream(message) {
  const res = await fetch('/api/chat', {
    method: 'POST', headers: HEADERS, body: JSON.stringify({ message })
  })
  const reader = res.body.getReader()
  const dec = new TextDecoder('utf-8')
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 1)
      if (line) {
        try { yield JSON.parse(line) } catch { /* 忽略残行 */ }
      }
    }
  }
}

export const GROUP_LABEL = { todo: '待办', schedule: '日程', notice: '通知', important: '重要', chatter: '闲聊' }
export const GROUP_CLASS = { todo: 'grp-todo', schedule: 'grp-schedule', notice: 'grp-notice', important: 'grp-important', chatter: 'grp-chatter' }
export const CH_CLASS = { wechat: 'ch-wechat', feishu: 'ch-feishu', dingtalk: 'ch-dingtalk', email: 'ch-email', qq: 'ch-qq' }

export function fmtTime(ts) {
  return ts ? ts.slice(11, 16) : ''
}
export function fmtDate(ts) {
  return ts ? ts.slice(5, 10) : ''
}
