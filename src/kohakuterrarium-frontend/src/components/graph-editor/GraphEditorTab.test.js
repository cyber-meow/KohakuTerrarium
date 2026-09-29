import { flushPromises, mount } from "@vue/test-utils"
import { createPinia, setActivePinia } from "pinia"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

import GraphEditorTab from "./GraphEditorTab.vue"
import { useRuntimeGraphStore } from "@/stores/runtimeGraph"

let wrapper
let editor

beforeEach(() => {
  setActivePinia(createPinia())
  editor = useRuntimeGraphStore()
  editor.applySnapshot({
    graphs: [
      {
        graph_id: "team",
        creatures: [
          { creature_id: "idle", name: "timeline-locations", running: true, is_processing: false },
          { creature_id: "busy", name: "working", running: true, is_processing: true },
        ],
        channels: [{ name: "tasks" }],
      },
    ],
  })
  vi.spyOn(editor, "loadSnapshot").mockResolvedValue()
  vi.spyOn(editor, "startPolling").mockImplementation(() => {})
  vi.spyOn(editor, "startLive").mockImplementation(() => {})
  vi.spyOn(editor, "closeNode").mockResolvedValue()
  wrapper = mount(GraphEditorTab, {
    global: {
      stubs: {
        RuntimeCanvasStage: { template: "<div><slot /></div>" },
        RuntimeMolecule: true,
        RuntimeConnection: true,
        SiteChip: true,
        NewCreatureModal: true,
        NewTerrariumModal: true,
      },
    },
  })
})

afterEach(() => {
  wrapper?.unmount()
  vi.restoreAllMocks()
})

function button(label) {
  return wrapper.findAll("button").find((node) => node.text() === label)
}

it.each(["contextmenu", "more"])(
  "offers Close agent for an idle card through %s",
  async (gesture) => {
    const card = wrapper.get('[data-node-id="idle"]')
    if (gesture === "more") {
      await card.trigger("click")
      await card.get('button[title="More options"]').trigger("click")
    } else await card.trigger("contextmenu")
    expect(button("Close agent")).toBeDefined()
    await button("Close agent").trigger("click")
    await flushPromises()
    expect(editor.closeNode).toHaveBeenCalledWith(
      "idle",
      expect.objectContaining({ expectedScope: expect.any(String) }),
    )
    expect(wrapper.text()).not.toContain("currently working")
  },
)

it("does not offer Close agent for channels", async () => {
  await wrapper.get('[data-node-id="channel:team:tasks"]').trigger("contextmenu")
  expect(button("Close agent")).toBeUndefined()
})

it("shows a close error and leaves the selected agent visible", async () => {
  editor.closeNode.mockRejectedValueOnce(new Error("Permission denied"))
  await wrapper.get('[data-node-id="idle"]').trigger("contextmenu")
  await button("Close agent").trigger("click")
  await flushPromises()
  expect(wrapper.text()).toContain("Permission denied")
  expect(wrapper.find('[data-node-id="idle"]').exists()).toBe(true)
})

it("asks before interrupting active work and supports cancelling", async () => {
  await wrapper.get('[data-node-id="busy"]').trigger("contextmenu")
  await button("Close agent").trigger("click")
  expect(wrapper.text()).toContain("currently working")
  expect(wrapper.text()).toContain("Saved history")
  expect(editor.closeNode).not.toHaveBeenCalled()
  await button("Cancel").trigger("click")
  expect(editor.closeNode).not.toHaveBeenCalled()
  await wrapper.get('[data-node-id="busy"]').trigger("contextmenu")
  await button("Close agent").trigger("click")
  await button("Close agent").trigger("click")
  await flushPromises()
  expect(editor.closeNode).toHaveBeenCalledWith("busy", expect.any(Object))
})
