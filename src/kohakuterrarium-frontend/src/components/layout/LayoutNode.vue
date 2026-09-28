<template>
  <!-- Leaf node: render the panel -->
  <div v-if="node.type === 'leaf'" class="layout-leaf h-full w-full overflow-hidden flex flex-col">
    <!-- Edit mode: panel label bar with replace/split/close -->
    <div v-if="layout.editMode" class="flex items-center gap-1 px-2 h-6 border-b border-amber/30 bg-amber/10 text-[10px] shrink-0">
      <span class="font-medium text-amber-shadow dark:text-amber-light truncate flex-1">
        {{ panel?.label || node.panelId || "empty" }}
      </span>
      <button class="px-1 py-0.5 rounded text-warm-500 hover:text-warm-700 dark:hover:text-warm-300 hover:bg-warm-100 dark:hover:bg-warm-800" title="Replace panel" @click="pickerOpen = true">
        <div class="i-carbon-switcher text-[11px]" />
      </button>
      <button class="px-1 py-0.5 rounded text-warm-500 hover:text-warm-700 dark:hover:text-warm-300 hover:bg-warm-100 dark:hover:bg-warm-800" title="Split horizontally" @click="layout.splitTreeNode(node, 'horizontal')">
        <div class="i-carbon-split-screen text-[11px]" />
      </button>
      <button class="px-1 py-0.5 rounded text-warm-500 hover:text-warm-700 dark:hover:text-warm-300 hover:bg-warm-100 dark:hover:bg-warm-800" title="Split vertically" @click="layout.splitTreeNode(node, 'vertical')">
        <div class="i-carbon-row text-[11px]" />
      </button>
      <button class="px-1 py-0.5 rounded text-warm-500 hover:text-coral hover:bg-warm-100 dark:hover:bg-warm-800" title="Close panel" @click="layout.removeTreeNode(node)">
        <div class="i-carbon-close text-[11px]" />
      </button>
    </div>

    <div class="flex-1 min-h-0">
      <component :is="panel?.component" v-if="panel?.component" v-bind="panelRuntimeProps" />
      <div v-else class="h-full w-full flex items-center justify-center text-[11px] text-warm-400">
        <template v-if="layout.editMode">
          <button class="px-3 py-2 rounded border border-dashed border-warm-300 dark:border-warm-600 text-warm-500 hover:border-iolite hover:text-iolite transition-colors" @click="pickerOpen = true">+ Add panel</button>
        </template>
        <template v-else>
          {{ node.panelId ? `no such panel: ${node.panelId}` : "empty slot" }}
        </template>
      </div>
    </div>

    <!-- Panel picker modal -->
    <PanelPicker v-model="pickerOpen" @select="onPick" />
  </div>

  <!-- Split node: two children separated by a draggable handle -->
  <div v-else-if="node.type === 'split'" ref="containerEl" class="layout-split h-full w-full overflow-hidden" :class="node.direction === 'horizontal' ? 'flex flex-row' : 'flex flex-col'">
    <div v-show="collapsedChild !== 0" :id="`${nodeId}-0`" data-layout-child="0" class="overflow-hidden min-w-0 min-h-0" :style="firstStyle">
      <LayoutNode :node="node.children[0]" :instance-id="instanceId" :panel-props-map="panelPropsMap" />
    </div>

    <div class="layout-split__handle relative shrink-0" :class="handleClass" :style="{ background: dragging ? 'var(--color-iolite, #6366f1)' : '' }" @pointerdown.prevent="onPointerDown">
      <div class="layout-split__controls absolute flex rounded border border-warm-300 dark:border-warm-600 bg-warm-100 dark:bg-warm-800 shadow-sm" :class="horizontal ? 'flex-col' : 'flex-row'">
        <button v-for="index in visibleControls" :key="index" type="button" class="w-6 h-6 flex items-center justify-center rounded text-warm-500 hover:text-iolite hover:bg-warm-200 dark:hover:bg-warm-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-iolite" :title="controlLabel(index)" :aria-label="controlLabel(index)" :aria-expanded="collapsedChild !== index" :aria-controls="`${nodeId}-${index}`" @pointerdown.stop @click.stop="toggleChild(index)">
          <span :class="controlIcon(index)" aria-hidden="true" />
        </button>
      </div>
    </div>

    <div v-show="collapsedChild !== 1" :id="`${nodeId}-1`" data-layout-child="1" :style="secondStyle" class="overflow-hidden min-w-0 min-h-0">
      <LayoutNode :node="node.children[1]" :instance-id="instanceId" :panel-props-map="panelPropsMap" />
    </div>
  </div>
</template>

<script setup>
import { computed, inject, ref, useId, watch } from "vue"

import PanelPicker from "./PanelPicker.vue"
import { useLayoutStore } from "@/stores/layout"
import { useI18n } from "@/utils/i18n"

const props = defineProps({
  node: { type: Object, required: true },
  instanceId: { type: String, default: null },
  panelPropsMap: { type: Object, default: null },
})

const layout = useLayoutStore()
const { t } = useI18n()
const pickerOpen = ref(false)
const nodeId = useId()
// Collapse is local to this rendered workspace, never saved into a shared
// preset. v-show keeps panel drafts, terminals, and nested state mounted.
const collapsedChild = ref(null)
const horizontal = computed(() => props.node.direction === "horizontal")
const visibleControls = computed(() => (collapsedChild.value == null ? [0, 1] : [collapsedChild.value]))

function toggleChild(index) {
  collapsedChild.value = collapsedChild.value === index ? null : index
}

function controlLabel(index) {
  const side = horizontal.value ? ["Left", "Right"][index] : ["Top", "Bottom"][index]
  return t(`layout.${collapsedChild.value === index ? "expand" : "collapse"}${side}`)
}

function controlIcon(index) {
  const direction = collapsedChild.value === index ? 1 - index : index
  return horizontal.value ? ["i-carbon-chevron-left", "i-carbon-chevron-right"][direction] : ["i-carbon-chevron-up", "i-carbon-chevron-down"][direction]
}

watch([() => props.node, () => props.instanceId], () => {
  collapsedChild.value = null
})
watch(
  () => layout.editMode,
  (editing) => {
    if (editing) collapsedChild.value = null
  },
)

function onPick(newPanelId) {
  layout.replaceTreePanel(props.node, newPanelId)
  pickerOpen.value = false
}

// Resolve panel component for leaf nodes.
const panel = computed(() => {
  if (props.node.type !== "leaf") return null
  return layout.getPanel(props.node.panelId)
})

// Runtime props from provide/inject chain.
const injectedProps = inject("panelProps", null)

const panelRuntimeProps = computed(() => {
  if (props.node.type !== "leaf") return {}
  const panelId = props.node.panelId
  const map = props.panelPropsMap || (injectedProps && typeof injectedProps === "object" && "value" in injectedProps ? injectedProps.value : injectedProps) || {}
  return map[panelId] || {}
})

// Split sizing.
const ratio = computed(() => props.node.ratio ?? 50)

const firstStyle = computed(() => childStyle(0))

const secondStyle = computed(() => childStyle(1))

function childStyle(index) {
  if (collapsedChild.value != null) return { flex: "1 1 0%" }
  const size = (index === 0 ? ratio.value : 100 - ratio.value) + "%"
  return horizontal.value ? { width: size, height: "100%" } : { height: size, width: "100%" }
}

const handleClass = computed(() => {
  if (collapsedChild.value != null) return horizontal.value ? "w-7" : "h-7"
  return horizontal.value ? "w-[3px] cursor-col-resize hover:bg-iolite/30 active:bg-iolite/50" : "h-[3px] cursor-row-resize hover:bg-iolite/30 active:bg-iolite/50"
})

// Drag handle — uses store action so editModeDirty is managed centrally.
const containerEl = ref(null)
const dragging = ref(false)

function onPointerDown(e) {
  if (collapsedChild.value != null) return
  dragging.value = true
  e.target.setPointerCapture(e.pointerId)

  const onMove = (ev) => {
    if (!dragging.value || !containerEl.value) return
    const rect = containerEl.value.getBoundingClientRect()
    const pct = props.node.direction === "horizontal" ? ((ev.clientX - rect.left) / rect.width) * 100 : ((ev.clientY - rect.top) / rect.height) * 100
    layout.setTreeRatio(props.node, pct)
  }

  const onUp = (ev) => {
    dragging.value = false
    ev.target.releasePointerCapture(ev.pointerId)
    ev.target.removeEventListener("pointermove", onMove)
    ev.target.removeEventListener("pointerup", onUp)
    ev.target.removeEventListener("pointercancel", onUp)
    // Persist the adjusted ratios to localStorage
    layout.persistTreeRatios()
  }

  e.target.addEventListener("pointermove", onMove)
  e.target.addEventListener("pointerup", onUp)
  e.target.addEventListener("pointercancel", onUp)
}
</script>

<style scoped>
.layout-split__handle {
  transition: background 0.15s ease;
  touch-action: none;
  z-index: 1;
}

.layout-split__controls {
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}
</style>
