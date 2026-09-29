import { beforeEach, describe, expect, it, vi } from "vitest"
import { createPinia, setActivePinia } from "pinia"

vi.mock("@/utils/api", () => ({
  sessionAPI: {
    listOpen: vi.fn(),
    stopActive: vi.fn(),
    removeCreature: vi.fn(),
    listActive: vi.fn(),
    getActive: vi.fn(),
  },
}))

import { useAuthStore } from "./auth"
import { useConversationsStore } from "./conversations"
import { useHostsStore } from "./hosts"
import { useInstancesStore } from "./instances"
import { removeRuntimeCreature, stopRuntime } from "./runtimeLifecycle"
import { sessionAPI } from "@/utils/api"

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  sessionAPI.listOpen.mockResolvedValue([])
  sessionAPI.stopActive.mockResolvedValue()
  sessionAPI.removeCreature.mockResolvedValue({ removed: true })
  sessionAPI.listActive.mockResolvedValue([])
  useAuthStore().sameOriginUser = null
})

describe("runtime lifecycle", () => {
  it("refreshes split runtimes and the conversation rail after removing one creature", async () => {
    const instances = useInstancesStore()
    instances._syncHostScope()
    instances.current = { id: "runtime-one", creatures: [{ creature_id: "removed" }] }
    instances.list = [instances.current]
    sessionAPI.listActive.mockResolvedValue([
      { session_id: "runtime-one", creatures: 1 },
      { session_id: "split-runtime", creatures: 1 },
    ])
    sessionAPI.getActive.mockImplementation(async (id) => ({
      session_id: id,
      creatures: [{ creature_id: id === "runtime-one" ? "peer-a" : "peer-b" }],
    }))
    await removeRuntimeCreature("runtime-one", "removed")
    expect(sessionAPI.removeCreature).toHaveBeenCalledWith("runtime-one", "removed")
    expect(sessionAPI.stopActive).not.toHaveBeenCalled()
    expect(instances.list.map((row) => row.creatures[0].creature_id)).toEqual(["peer-a", "peer-b"])
    expect(instances.current.id).toBe("runtime-one")
    expect(sessionAPI.listOpen).toHaveBeenCalledTimes(1)
  })

  it("keeps peers untouched on a rejected individual removal", async () => {
    const instances = useInstancesStore()
    instances.list = [{ id: "runtime-one", creatures: ["a", "b"] }]
    sessionAPI.removeCreature.mockRejectedValueOnce(new Error("permission denied"))
    await expect(removeRuntimeCreature("runtime-one", "a")).rejects.toThrow("permission denied")
    expect(instances.list).toEqual([{ id: "runtime-one", creatures: ["a", "b"] }])
    expect(sessionAPI.listActive).not.toHaveBeenCalled()
    expect(sessionAPI.listOpen).not.toHaveBeenCalled()
  })

  it("does not refresh a different host after an individual removal completes", async () => {
    const hosts = useHostsStore()
    hosts.hosts = [hostRecord("host-a"), hostRecord("host-b")]
    hosts.activeHostId = "host-a"
    const request = promiseWithResolvers()
    sessionAPI.removeCreature.mockReturnValueOnce(request.promise)
    const removing = removeRuntimeCreature("same-id", "a")
    hosts.activeHostId = "host-b"
    request.resolve({ removed: true })
    await expect(removing).rejects.toThrow("host changed")
    expect(sessionAPI.listActive).not.toHaveBeenCalled()
    expect(sessionAPI.listOpen).not.toHaveBeenCalled()
  })
  it("removes a stopped runtime from both live stores in the same scope", async () => {
    const instances = useInstancesStore()
    const conversations = useConversationsStore()
    instances.list = [{ id: "runtime-one", status: "running" }]
    instances.current = instances.list[0]
    conversations.rows = [
      {
        id: "conversation-one",
        runtime_id: "runtime-one",
        is_live: true,
        status: "running",
      },
    ]

    await stopRuntime("runtime-one")

    expect(sessionAPI.stopActive).toHaveBeenCalledWith("runtime-one")
    expect(instances.list).toEqual([])
    expect(instances.current).toBeNull()
    expect(conversations.liveRows).toEqual([])
    expect(sessionAPI.listOpen).toHaveBeenCalledTimes(1)
  })

  it("does not mutate the new host when the stop response belongs to the old host", async () => {
    const hosts = useHostsStore()
    hosts.hosts = [hostRecord("host-a"), hostRecord("host-b")]
    hosts.activeHostId = "host-a"

    const instances = useInstancesStore()
    const conversations = useConversationsStore()
    conversations._syncHostScope()
    const stop = promiseWithResolvers()
    sessionAPI.stopActive.mockReturnValue(stop.promise)

    const stopping = stopRuntime("shared-runtime")
    hosts.activeHostId = "host-b"
    conversations._syncHostScope()
    instances.list = [{ id: "shared-runtime", status: "running", host: "host-b" }]
    instances.current = instances.list[0]
    conversations.rows = [
      {
        id: "conversation-b",
        runtime_id: "shared-runtime",
        is_live: true,
        status: "running",
      },
    ]
    stop.resolve()

    await expect(stopping).rejects.toThrow("host changed")
    expect(instances.list).toEqual([{ id: "shared-runtime", status: "running", host: "host-b" }])
    expect(instances.current).toEqual({
      id: "shared-runtime",
      status: "running",
      host: "host-b",
    })
    expect(conversations.liveRows.map((row) => row.id)).toEqual(["conversation-b"])
    expect(sessionAPI.listOpen).not.toHaveBeenCalled()
  })

  it("does not mutate the new user when the stop response belongs to the old user", async () => {
    const auth = useAuthStore()
    auth.sameOriginUser = { id: "user-a" }

    const instances = useInstancesStore()
    const conversations = useConversationsStore()
    conversations._syncHostScope()
    const stop = promiseWithResolvers()
    sessionAPI.stopActive.mockReturnValue(stop.promise)

    const stopping = stopRuntime("shared-runtime")
    auth.sameOriginUser = { id: "user-b" }
    conversations._syncHostScope()
    instances.list = [{ id: "shared-runtime", status: "running", user: "user-b" }]
    instances.current = instances.list[0]
    conversations.rows = [
      {
        id: "conversation-b",
        runtime_id: "shared-runtime",
        is_live: true,
        status: "running",
      },
    ]
    stop.resolve()

    await expect(stopping).rejects.toThrow("host changed")
    expect(instances.list).toEqual([{ id: "shared-runtime", status: "running", user: "user-b" }])
    expect(instances.current).toEqual({
      id: "shared-runtime",
      status: "running",
      user: "user-b",
    })
    expect(conversations.liveRows.map((row) => row.id)).toEqual(["conversation-b"])
    expect(sessionAPI.listOpen).not.toHaveBeenCalled()
  })
})

function hostRecord(id) {
  return {
    id,
    name: id,
    url: `https://${id}.example`,
    token: "",
    adminToken: "",
    userToken: "",
    currentUser: null,
  }
}

function promiseWithResolvers() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}
