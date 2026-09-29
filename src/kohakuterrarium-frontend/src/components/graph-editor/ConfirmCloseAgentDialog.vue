<template>
  <ModalShell @close="!closing && $emit('close')">
    <template #title>Close agent</template>
    <p class="text-sm text-warm-700 dark:text-warm-300">
      <strong>{{ name }}</strong> is currently working. Closing it will interrupt its work. Saved history will remain available, and other agents will keep running.
    </p>
    <p v-if="error" role="alert" class="mt-2 text-sm text-coral">{{ error }}</p>
    <template #footer>
      <div class="flex justify-end gap-2">
        <button class="btn-secondary text-xs px-3 py-1.5" :disabled="closing" @click="$emit('close')">Cancel</button>
        <button class="btn-primary text-xs px-3 py-1.5 bg-coral hover:bg-coral-dark" :disabled="closing" @click="$emit('confirm')">
          {{ closing ? "Closing…" : "Close agent" }}
        </button>
      </div>
    </template>
  </ModalShell>
</template>

<script setup>
import ModalShell from "@/components/common/ModalShell.vue"

defineProps({ name: { type: String, required: true }, closing: Boolean, error: { type: String, default: "" } })
defineEmits(["close", "confirm"])
</script>
