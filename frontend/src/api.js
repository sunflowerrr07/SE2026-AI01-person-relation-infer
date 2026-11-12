export async function request(path, token, options = {}) {
  const headers = new Headers(options.headers || {})
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(path, { ...options, headers })
  if (!response.ok) throw new Error(`请求失败 (${response.status})`)
  return (await response.json()).data
}

export function graphOption(people, relations) {
  return {
    tooltip: { trigger: 'item' },
    series: [{ type: 'graph', layout: 'force', roam: true, draggable: true,
      label: { show: true, color: '#dbeafe', position: 'bottom' },
      force: { repulsion: 350, edgeLength: 150 },
      lineStyle: { color: '#43d6ca', width: 2, opacity: 0.7 },
      data: people.map(p => ({ id: p.person_id, name: p.person_id, symbolSize: 42, itemStyle: { color: '#50c9c3' } })),
      links: relations.map(r => ({ source: r.source, target: r.target, value: r.confidence, name: r.uncertain ? '不确定' : '关系' })) }]
  }
}
