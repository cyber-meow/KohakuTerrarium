import { createPinia, setActivePinia } from "pinia"
import { beforeEach, describe, expect, it, vi } from "vitest"

class FakeWebSocket {}

vi.mock("@/composables/useVisibilityInterval", () => ({
  createVisibilityInterval: vi.fn(() => ({
    start: vi.fn(),
    stop: vi.fn(),
    isRunning: vi.fn(() => true),
  })),
}))

vi.mock("@/utils/uiPrefs", () => ({
  getHybridPrefSync: vi.fn(() => ({ nodes: {}, connections: {}, groups: {}, view: {} })),
  setHybridPref: vi.fn(),
}))

vi.mock("@/utils/wsUrl", () => ({
  wsUrl: vi.fn((path) => `ws://test${path}`),
}))

vi.mock("@/stores/runtimeLifecycle", () => ({
  stopRuntime: vi.fn(),
  removeRuntimeCreature: vi.fn(),
}))

vi.mock("@/utils/api", () => ({
  runtimeGraphAPI: { snapshot: vi.fn() },
  sessionAPI: {
    listActive: vi.fn(() => Promise.resolve([])),
  },
  terrariumAPI: {
    connect: vi.fn(),
    wireCreature: vi.fn(),
    unwireCreature: vi.fn(),
    stop: vi.fn(),
    addChannel: vi.fn(),
    list: vi.fn(() => Promise.resolve([])),
  },
  agentAPI: {
    list: vi.fn(() => Promise.resolve([])),
  },
  wiringAPI: {
    addOutput: vi.fn(),
    removeOutput: vi.fn(),
  },
}))

import { removeRuntimeCreature, stopRuntime } from "./runtimeLifecycle"
import { runtimeGraphAPI, terrariumAPI, wiringAPI } from "@/utils/api"
import { useRuntimeGraphStore } from "./runtimeGraph"
import { useAuthStore } from "./auth"

const snapshot = {
  version: 1,
  graphs: [
    {
      graph_id: "graph_1",
      name: "team",
      creatures: [
        {
          creature_id: "alice",
          name: "Alice",
          running: true,
          is_processing: false,
          listen_channels: [],
          send_channels: ["tasks"],
        },
        {
          creature_id: "bob",
          name: "Bob",
          running: true,
          is_processing: true,
          listen_channels: ["tasks"],
          send_channels: [],
        },
      ],
      channels: [
        {
          name: "tasks",
          type: "queue",
          description: "Task queue",
          qsize: 1,
          message_count: 1,
          last_message: { content_preview: "hello" },
        },
      ],
      output_edges: [
        {
          id: "wire_bob_content_simple_noself_811c9dc5",
          edge_id: "wire_bob_content_simple_noself_811c9dc5",
          from: "alice",
          to: "bob",
          to_creature_id: "bob",
          with_content: true,
        },
      ],
    },
  ],
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  globalThis.WebSocket = FakeWebSocket
  runtimeGraphAPI.snapshot.mockReset().mockResolvedValue(snapshot)
  stopRuntime.mockReset()
  removeRuntimeCreature.mockReset()
  useAuthStore().sameOriginUser = null
})

describe("runtime graph store", () => {
  it("closes one creature and applies the authoritative split topology", async () => {
    const store = useRuntimeGraphStore()
    await store.loadSnapshot()
    store.selectNode("alice")
    const after = {
      graphs: [
        {
          graph_id: "split-peer",
          creatures: [{ ...snapshot.graphs[0].creatures[1], listen_channels: [] }],
          channels: [],
        },
      ],
    }
    runtimeGraphAPI.snapshot.mockResolvedValueOnce(snapshot).mockResolvedValueOnce(after)
    removeRuntimeCreature.mockResolvedValueOnce({ removed: true })
    await store.closeNode("alice")
    expect(removeRuntimeCreature).toHaveBeenCalledWith("graph_1", "alice")
    expect(stopRuntime).not.toHaveBeenCalled()
    expect(store.state.nodes.map((node) => node.id)).toEqual(["bob"])
    expect(store.nodeById.bob.graphId).toBe("split-peer")
    expect(store.state.connections).toEqual([])
    expect(store.state.selection.id).toBeNull()
  })

  it("uses the full runtime stop path for the last creature, including hidden solo groups", async () => {
    const store = useRuntimeGraphStore()
    store.applySnapshot({
      graphs: [{ graph_id: "solo", creatures: [snapshot.graphs[0].creatures[0]] }],
    })
    expect(store.state.groups).toHaveLength(0)
    runtimeGraphAPI.snapshot
      .mockResolvedValueOnce(store.state.rawSnapshot)
      .mockResolvedValueOnce({ graphs: [] })
    stopRuntime.mockResolvedValueOnce()
    await store.closeNode("alice")
    expect(stopRuntime).toHaveBeenCalledWith("solo")
    expect(removeRuntimeCreature).not.toHaveBeenCalled()
    expect(store.state.nodes).toEqual([])
  })

  it("retains the node and shows the backend detail when removal fails", async () => {
    const store = useRuntimeGraphStore()
    await store.loadSnapshot()
    removeRuntimeCreature.mockRejectedValueOnce({
      response: { data: { detail: "cannot close agent" } },
    })
    await expect(store.closeNode("alice")).rejects.toBeTruthy()
    expect(store.nodeById.alice).toBeDefined()
    expect(store.nodeById.bob).toBeDefined()
    expect(store.state.error).toContain("cannot close agent")
    expect(runtimeGraphAPI.snapshot).toHaveBeenCalledTimes(2)
  })

  it("does not stop a whole runtime when a peer joined after the cached singleton snapshot", async () => {
    const store = useRuntimeGraphStore()
    store.applySnapshot({
      graphs: [{ graph_id: "graph_1", creatures: [snapshot.graphs[0].creatures[0]] }],
    })
    runtimeGraphAPI.snapshot.mockResolvedValueOnce(snapshot).mockResolvedValueOnce({ graphs: [] })
    removeRuntimeCreature.mockResolvedValueOnce({ removed: true })
    await store.closeNode("alice")
    expect(removeRuntimeCreature).toHaveBeenCalledWith("graph_1", "alice")
    expect(stopRuntime).not.toHaveBeenCalled()
  })

  it("rejects a changed user scope before sending any close request", async () => {
    const store = useRuntimeGraphStore()
    await store.loadSnapshot()
    let resolve
    runtimeGraphAPI.snapshot.mockReturnValueOnce(
      new Promise((done) => {
        resolve = done
      }),
    )
    const closing = store.closeNode("alice")
    useAuthStore().sameOriginUser = { id: "different-user" }
    resolve(snapshot)
    await expect(closing).rejects.toThrow("host changed")
    expect(removeRuntimeCreature).not.toHaveBeenCalled()
    expect(stopRuntime).not.toHaveBeenCalled()
    expect(store.state.error).toBe("")
  })

  it("does not overwrite a new user graph with an old close refresh", async () => {
    const store = useRuntimeGraphStore()
    await store.loadSnapshot()
    let resolve
    runtimeGraphAPI.snapshot.mockResolvedValueOnce(snapshot).mockReturnValueOnce(
      new Promise((done) => {
        resolve = done
      }),
    )
    removeRuntimeCreature.mockResolvedValueOnce({ removed: true })
    const closing = store.closeNode("alice")
    await vi.waitFor(() => expect(resolve).toBeTypeOf("function"))
    useAuthStore().sameOriginUser = { id: "different-user" }
    store.applySnapshot({
      graphs: [{ graph_id: "new-user", creatures: [{ creature_id: "new-peer" }] }],
    })
    resolve({ graphs: [] })
    await expect(closing).rejects.toThrow("host changed")
    expect(store.state.nodes.map((node) => node.id)).toEqual(["new-peer"])
    expect(store.state.error).toBe("")
  })
  it("routes graph dissolution through the shared instance stop action", async () => {
    const store = useRuntimeGraphStore()
    stopRuntime.mockResolvedValue()

    await store.dissolveGroup("graph_1")

    expect(stopRuntime).toHaveBeenCalledWith("graph_1")
    expect(terrariumAPI.stop).not.toHaveBeenCalled()
  })

  it("normalizes runtime snapshot into graph editor data", async () => {
    const store = useRuntimeGraphStore()

    await store.loadSnapshot()

    expect(store.state.groups).toHaveLength(1)
    expect(store.state.groups[0].id).toBe("graph_1")
    expect(store.nodeById.alice.status).toBe("waiting")
    expect(store.nodeById.bob.status).toBe("running")
    expect(store.nodeById["channel:graph_1:tasks"].kind).toBe("channel")
    expect(store.state.connections.map((c) => c.label).sort()).toEqual(["tasks", "tasks", "wire"])
  })

  it("wires creature-to-creature drags as direct output wiring (no channel)", async () => {
    const store = useRuntimeGraphStore()
    wiringAPI.addOutput.mockResolvedValue({ status: "wired", edge_id: "ed_1" })
    await store.loadSnapshot()

    await store.connect("alice", "bob")

    expect(wiringAPI.addOutput).toHaveBeenCalledWith(
      "graph_1",
      "alice",
      expect.objectContaining({ to: "bob", with_content: true }),
    )
    expect(terrariumAPI.connect).not.toHaveBeenCalled()
    // No await loadSnapshot inside the mutation — the WS pushes the
    // topology_changed event and that triggers the reload.
    expect(runtimeGraphAPI.snapshot).toHaveBeenCalledTimes(1)
  })

  it("toggles channel-edge direction through wire and unwire APIs", async () => {
    const store = useRuntimeGraphStore()
    terrariumAPI.unwireCreature.mockResolvedValue({ status: "unwired" })
    await store.loadSnapshot()
    const edge = store.state.connections.find(
      (c) => c.backend?.kind === "channel_edge" && c.backend.creatureId === "alice",
    )

    await store.toggleDirection(edge.id, "aToB")

    expect(terrariumAPI.unwireCreature).toHaveBeenCalledWith("graph_1", "alice", "tasks", "send")
  })

  it("removes output wiring edges through wiring API", async () => {
    const store = useRuntimeGraphStore()
    wiringAPI.removeOutput.mockResolvedValue({ status: "unwired" })
    await store.loadSnapshot()
    const edge = store.state.connections.find((c) => c.backend?.kind === "output_edge")

    await store.deleteConnection(edge.id)

    expect(wiringAPI.removeOutput).toHaveBeenCalledWith(
      "graph_1",
      "alice",
      "wire_bob_content_simple_noself_811c9dc5",
    )
  })

  it("renders a solo-creature graph as a free card with no membrane", async () => {
    runtimeGraphAPI.snapshot.mockResolvedValue({
      version: 2,
      graphs: [
        {
          graph_id: "graph_solo",
          name: "alice (standalone)",
          creatures: [
            {
              creature_id: "alice",
              name: "Alice",
              running: true,
              is_processing: false,
              listen_channels: [],
              send_channels: [],
            },
          ],
          channels: [],
          output_edges: [],
        },
      ],
    })
    const store = useRuntimeGraphStore()

    await store.loadSnapshot()

    // No membrane for a single creature with no channels — the
    // creature shows up free instead of wrapped in a one-card group.
    expect(store.state.groups).toHaveLength(0)
    const alice = store.nodeById.alice
    expect(alice.groupId).toBeNull()
    // The backend graph id is still tracked separately so wiring
    // calls have the right session id.
    expect(alice.graphId).toBe("graph_solo")
  })

  it("patches channel message websocket events without refetch", async () => {
    const store = useRuntimeGraphStore()
    await store.loadSnapshot()

    store.applyRuntimeEvent({
      type: "channel_message",
      graph_id: "graph_1",
      channel: "tasks",
      sender: "alice",
      content_preview: "latest task",
    })

    const edges = store.state.connections.filter((c) => c.backend?.kind === "channel_edge")
    expect(edges.every((edge) => edge.brief === "latest task")).toBe(true)
  })
})
