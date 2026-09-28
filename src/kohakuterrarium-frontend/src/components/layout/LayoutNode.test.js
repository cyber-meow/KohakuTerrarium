import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { mount } from "@vue/test-utils"
import { createPinia, setActivePinia } from "pinia"
import { defineComponent, h, onUnmounted, ref } from "vue"

import LayoutNode from "./LayoutNode.vue"
import { useLayoutStore } from "@/stores/layout"
import { useLocaleStore } from "@/stores/locale"
import { _resetUIPrefsForTests } from "@/utils/uiPrefs"

const mounted = []
let unmounted

beforeEach(() => {
  vi.useFakeTimers()
  _resetUIPrefsForTests()
  localStorage.clear()
  setActivePinia(createPinia())
  useLocaleStore().locale = "en"
  unmounted = vi.fn()
  const panel = defineComponent({
    setup() {
      const draft = ref("")
      onUnmounted(unmounted)
      return () =>
        h("input", { value: draft.value, onInput: (event) => (draft.value = event.target.value) })
    },
  })
  useLayoutStore().registerPanel({ id: "custom-panel", component: panel })
})

afterEach(() => {
  for (const wrapper of mounted.splice(0)) wrapper.unmount()
  _resetUIPrefsForTests()
  vi.useRealTimers()
})

function split(direction = "horizontal") {
  return {
    type: "split",
    direction,
    ratio: 30,
    children: [
      { type: "leaf", panelId: "custom-panel" },
      { type: "leaf", panelId: "custom-panel" },
    ],
  }
}

function render(node) {
  const wrapper = mount(LayoutNode, {
    props: { node },
    attachTo: document.body,
    global: { stubs: { PanelPicker: true } },
  })
  mounted.push(wrapper)
  return wrapper
}

describe("custom layout panel collapse", () => {
  it.each([
    ["horizontal", 0, "left", "width", "30%"],
    ["horizontal", 1, "right", "width", "70%"],
    ["vertical", 0, "top", "height", "30%"],
    ["vertical", 1, "bottom", "height", "70%"],
  ])(
    "restores %s child %s without losing its draft or ratio",
    async (direction, index, side, dimension, size) => {
      const node = split(direction)
      const original = JSON.stringify(node)
      const wrapper = render(node)
      const input = wrapper.findAll("input")[index]
      await input.setValue("Keep this draft")
      const button = wrapper.get(`button[aria-label="Collapse ${side} panel"]`)
      const pane = wrapper.get(`[id="${button.attributes("aria-controls")}"]`)
      // Pointerdown on a button must not start the splitter's drag handler.
      await button.trigger("pointerdown")
      await button.trigger("click")
      expect(pane.isVisible()).toBe(false)
      const sibling = wrapper.findAll("input")[1 - index]
      expect(sibling.isVisible()).toBe(true)
      expect(sibling.element.closest("[data-layout-child]").style.flex).toBe("1 1 0%")
      expect(unmounted).not.toHaveBeenCalled()
      expect(JSON.stringify(node)).toBe(original)
      const expand = wrapper.get(`button[aria-label="Expand ${side} panel"]`)
      expect(expand.attributes("aria-expanded")).toBe("false")
      await expand.trigger("click")
      expect(pane.isVisible()).toBe(true)
      expect(pane.element.style[dimension]).toBe(size)
      expect(input.element.value).toBe("Keep this draft")
      expect(JSON.stringify(node)).toBe(original)
    },
  )

  it("preserves nested collapse when the parent reopens", async () => {
    const node = split()
    node.children[1] = split("vertical")
    const wrapper = render(node)
    await wrapper.get('button[aria-label="Collapse bottom panel"]').trigger("click")
    await wrapper.get('button[aria-label="Collapse right panel"]').trigger("click")
    await wrapper.get('button[aria-label="Expand right panel"]').trigger("click")
    expect(wrapper.findAll("input").map((input) => input.isVisible())).toEqual([true, true, false])
    await wrapper.get('button[aria-label="Expand bottom panel"]').trigger("click")
    expect(wrapper.findAll("input").every((input) => input.isVisible())).toBe(true)
    expect(unmounted).not.toHaveBeenCalled()
  })

  it("does not collapse another workspace sharing the preset tree", async () => {
    const node = split()
    const first = render(node)
    const second = render(node)
    await first.get('button[aria-label="Collapse left panel"]').trigger("click")
    expect(second.findAll("input").every((input) => input.isVisible())).toBe(true)
    expect(second.get('button[aria-label="Collapse left panel"]').attributes("aria-expanded")).toBe(
      "true",
    )
  })

  it("reveals panels when customizing or replacing the layout", async () => {
    const wrapper = render(split())
    await wrapper.get('button[aria-label="Collapse left panel"]').trigger("click")
    useLayoutStore().editMode = true
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll("input").every((input) => input.isVisible())).toBe(true)
    useLayoutStore().editMode = false
    await wrapper.vm.$nextTick()
    await wrapper.get('button[aria-label="Collapse right panel"]').trigger("click")
    await wrapper.setProps({ node: split("vertical") })
    expect(wrapper.findAll("input").every((input) => input.isVisible())).toBe(true)
  })

  it("reveals panels when a reused view navigates to another instance", async () => {
    const wrapper = render(split())
    await wrapper.setProps({ instanceId: "first" })
    await wrapper.get('button[aria-label="Collapse right panel"]').trigger("click")
    await wrapper.setProps({ instanceId: "second" })
    expect(wrapper.findAll("input").every((input) => input.isVisible())).toBe(true)
  })

  it("localizes the accessible controls", async () => {
    const wrapper = render(split())
    useLocaleStore().locale = "zh-TW"
    await wrapper.vm.$nextTick()
    await wrapper.get('button[aria-label="收合左側面板"]').trigger("click")
    expect(wrapper.get('button[aria-label="展開左側面板"]').attributes("aria-expanded")).toBe(
      "false",
    )
  })
})
