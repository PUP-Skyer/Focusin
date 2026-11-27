const HEADERS = { 'Content-Type': 'application/json' }

async function api(path, opts = {}) {
  const res = await fetch('/api' + path, opts)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json()
}

export const get = (p) => api(p)
export const post = (p, body) => api(p, { method: 'POST', headers: HEADERS, body: JSON.stringify(body || {}) })
export function notifyConversationsChanged() {
  window.dispatchEvent(new Event('fi-conversations-changed'))
}

/** SSE/NDJSON 流式对话 */
export async function* chatStream(message, { sessionId = 'legacy', signal } = {}) {
  const res = await fetch('/api/chat', {
    method: 'POST', headers: HEADERS, signal,
    body: JSON.stringify({ message, session_id: sessionId })
  })
  if (!res.ok) throw new Error(`${res.status} /api/chat`)
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

export const chatSessions = () => get('/chat/sessions')
export const createChatSession = (title = '新对话') => post('/chat/sessions', { title })
export const chatSessionMessages = (id) => get(`/chat/sessions/${encodeURIComponent(id)}/messages`)
export const runWorkflow = (id, sessionId = '') => post(`/workflows/${encodeURIComponent(id)}/execute`, { session_id: sessionId })

export const GROUP_LABEL = { todo: '待办', schedule: '日程', notice: '通知', important: '重要', chatter: '闲聊' }
export const GROUP_CLASS = { todo: 'grp-todo', schedule: 'grp-schedule', notice: 'grp-notice', important: 'grp-important', chatter: 'grp-chatter' }
export const CH_CLASS = { wechat: 'ch-wechat', feishu: 'ch-feishu', dingtalk: 'ch-dingtalk', email: 'ch-email', qq: 'ch-qq' }
export const CHANNEL_META = [
  { key: 'wechat', label: '微信' },
  { key: 'qq', label: 'QQ' },
  { key: 'feishu', label: '飞书' },
  { key: 'email', label: 'QQ邮箱' },
  { key: 'dingtalk', label: '钉钉' }
]

export function conversationGroupKey(c) {
  return c.channel_key === 'email' ? `email:${c.provider_key || 'other'}` : c.channel_key
}

export function groupConversations(convs, emailAccounts = []) {
  const groups = CHANNEL_META.filter(c => c.key !== 'email').map(meta => {
    const items = convs.filter(c => c.channel_key === meta.key)
    return { ...meta, channel: meta.key, items, important: items.reduce((n, c) => n + (c.important || 0), 0) }
  }).filter(g => g.items.length)

  const accounts = new Map(emailAccounts.map(a => [a.account_key, a]))
  const emailGroups = new Map()
  for (const c of convs.filter(c => c.channel_key === 'email')) {
    const account = accounts.get(c.account_key)
    const providerKey = c.provider_key || account?.provider_key || 'other'
    const provider = c.provider || account?.provider || '其他邮箱'
    const key = `email:${providerKey}`
    let group = emailGroups.get(key)
    if (!group) {
      group = { key, channel: 'email', label: provider, title: provider, items: [], important: 0 }
      emailGroups.set(key, group)
    }
    group.items.push(c)
    group.important += c.important || 0
  }
  groups.push(...emailGroups.values())

  const known = new Set(CHANNEL_META.map(c => c.key))
  convs.filter(c => !known.has(c.channel_key)).forEach(c => {
    let group = groups.find(g => g.channel === c.channel_key)
    if (!group) {
      group = { key: c.channel_key, channel: c.channel_key, label: c.channel_key, items: [], important: 0 }
      groups.push(group)
    }
    group.items.push(c)
    group.important += c.important || 0
  })
  const order = { wechat: 0, qq: 1, feishu: 2, email: 3, dingtalk: 4 }
  groups.sort((a, b) => (order[a.channel] ?? 99) - (order[b.channel] ?? 99))
  return groups
}

export function fmtTime(ts) {
  return ts ? ts.slice(11, 16) : ''
}
export function fmtDate(ts) {
  return ts ? ts.slice(5, 10) : ''
}

export function senderDisplayName(message) {
  const sender = String(message?.sender || '').trim()
  if (!sender || sender === 'member' || /^(ou_|on_|cli_)/.test(sender)) {
    if (message?.channel_key === 'feishu' && message?.sender_id) return '昵称未同步'
    return message?.sender_id ? '群成员' : '未知发送人'
  }
  return sender
}

export function senderInitial(message) {
  return senderDisplayName(message).slice(0, 1)
}

const EMAIL_WEBMAIL = [
  { match: ['gmail.com'], label: 'Gmail', url: 'https://mail.google.com/mail/u/0/' },
  { match: ['outlook.', 'office365', 'hotmail.'], label: 'Outlook', url: 'https://outlook.office.com/mail/' },
  { match: ['qq.com', 'foxmail.com'], label: 'QQ邮箱', url: 'https://mail.qq.com/' },
  { match: ['163.com'], label: '163邮箱', url: 'https://mail.163.com/' },
  { match: ['126.com'], label: '126邮箱', url: 'https://mail.126.com/' },
  { match: ['yeah.net'], label: 'Yeah.net', url: 'https://mail.yeah.net/' },
  { match: ['aliyun.com'], label: '阿里邮箱', url: 'https://mail.aliyun.com/' },
  { match: ['sina.', 'sina.cn'], label: '新浪邮箱', url: 'https://mail.sina.com.cn/' },
  { match: ['icloud.com', 'me.com', 'mac.com'], label: 'iCloud邮箱', url: 'https://www.icloud.com/mail/' }
]

function emailSource(m) {
  const parts = String(m.dedup_key || '').split(':')
  const host = (parts[1] || '').toLowerCase()
  const uid = parts.at(-1) || ''
  const subject = String(m.text || '').split(/\r?\n/)[0].replace(/^subject\s*[:：]\s*/i, '').slice(0, 120)
  const provider = EMAIL_WEBMAIL.find(p => p.match.some(x => host.includes(x)))
  let url = provider?.url || ''
  if (provider?.label === 'Gmail') {
    url += `#search/${encodeURIComponent(subject ? `subject:"${subject}"` : 'in:anywhere')}`
  } else if (provider?.label === 'Outlook' && subject) {
    url += `search?q=${encodeURIComponent(subject)}`
  }
  return { url, ref: uid, label: provider?.label || '网页邮箱', supported: !!url }
}

export function messageSource(m) {
  const dedup = String(m.dedup_key || '')
  if (dedup.startsWith('seed:') || dedup.startsWith('inj:')) {
    return { url: '', ref: '', label: '演示消息', supported: false }
  }
  if (m.channel_key === 'feishu' && m.conv_key) {
    return {
      url: `https://applink.feishu.cn/client/chat/open?openChatId=${encodeURIComponent(m.conv_key)}`,
      ref: dedup.startsWith('feishu:') ? dedup.slice(7) : '',
      label: '飞书会话',
      supported: true
    }
  }
  if (m.channel_key === 'email') return emailSource(m)
  if (dedup.startsWith('seed:')) {
    return { url: '', ref: '', label: '演示消息', supported: false }
  }
  const label = { wechat: '微信', qq: 'QQ', dingtalk: '钉钉' }[m.channel_key] || m.channel_key
  return { url: '', ref: dedup, label, supported: false }
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const input = document.createElement('textarea')
  input.value = text
  input.style.position = 'fixed'
  input.style.opacity = '0'
  document.body.appendChild(input)
  input.select()
  document.execCommand('copy')
  input.remove()
}

export async function openMessageSource(m) {
  const source = messageSource(m)
  if (source.url) window.open(source.url, '_blank', 'noopener,noreferrer')
  let copied = false
  if (source.ref) {
    try {
      await copyText(source.ref)
      copied = true
    } catch { /* 剪贴板不可用时保留页面提示 */ }
  }
  if (source.supported) {
    if (m.channel_key === 'feishu') {
      return `已打开飞书唤起页，请点击页面中的“立即打开”${copied ? '；会话定位信息已复制' : ''}`
    }
    return `已打开${source.label}${copied ? '，定位信息已复制' : ''}`
  }
  return `${source.label}暂未开放单条消息深链${copied ? '，已复制定位信息' : ''}`
}
