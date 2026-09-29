import { afterEach, expect, it, vi } from "vitest"
import api, { sessionAPI } from "@/utils/api"

afterEach(() => vi.restoreAllMocks())

it("removes only the encoded creature within the encoded runtime", async () => {
  const removed = { removed: true }
  const request = vi.spyOn(api, "delete").mockResolvedValue({ data: removed })
  expect(await sessionAPI.removeCreature("graph /一", "worker #二")).toEqual(removed)
  expect(request).toHaveBeenCalledWith(
    "/sessions/active/graph%20%2F%E4%B8%80/creatures/worker%20%23%E4%BA%8C",
  )
})
