import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'

vi.mock('./components/GraphView.vue', () => ({ default: { template: '<div>GRAPH CANVAS</div>' } }))
beforeEach(() => setActivePinia(createPinia()))

describe('dashboard navigation', () => {
  it('shows task upload, graph and audit pages with mock disclosure', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(App, { global: { plugins: [pinia], stubs: ['el-input', 'el-button', 'el-checkbox', 'el-alert', 'el-table', 'el-table-column', 'el-progress', 'el-select', 'el-option'] } })
    expect(wrapper.text()).toContain('实验演示模式')
    expect(wrapper.find('input[type=file]').exists()).toBe(true)
    await wrapper.findAll('aside button')[1].trigger('click')
    expect(wrapper.text()).toContain('GRAPH CANVAS')
    await wrapper.findAll('aside button')[2].trigger('click')
    expect(wrapper.text()).toContain('隐私与访问审计')
    wrapper.unmount()
  })
})
