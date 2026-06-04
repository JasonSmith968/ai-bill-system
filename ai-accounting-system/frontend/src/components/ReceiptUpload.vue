<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['upload'])

const isDragging = ref(false)
const fileInput = ref(null)
const previewUrl = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)
const uploadProgress = ref(0)
const error = ref('')

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_SIZE = 10 * 1024 * 1024 // 10MB

const hasImage = computed(() => !!previewUrl.value)

function triggerFileInput() {
  fileInput.value?.click()
}

function handleDragOver(e) {
  e.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

function handleDrop(e) {
  e.preventDefault()
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files?.length) {
    processFile(files[0])
  }
}

function handleFileChange(e) {
  const files = e.target.files
  if (files?.length) {
    processFile(files[0])
  }
}

function processFile(file) {
  error.value = ''

  // Validate type
  if (!ACCEPTED_TYPES.includes(file.type)) {
    error.value = '不支持的图片格式，请使用 JPG/PNG/WEBP'
    return
  }

  // Validate size
  if (file.size > MAX_SIZE) {
    error.value = `图片大小不能超过 ${MAX_SIZE / (1024 * 1024)}MB`
    return
  }

  selectedFile.value = file

  // Create preview
  const reader = new FileReader()
  reader.onload = (e) => {
    previewUrl.value = e.target.result
  }
  reader.readAsDataURL(file)
}

function removeImage() {
  previewUrl.value = null
  selectedFile.value = null
  error.value = ''
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

async function handleUpload() {
  if (!selectedFile.value) return
  if (uploading.value) return

  console.log('upload start', selectedFile.value.name, selectedFile.value.size)
  uploading.value = true
  uploadProgress.value = 0
  error.value = ''

  // Simulate progress
  const progressInterval = setInterval(() => {
    if (uploadProgress.value < 90) {
      uploadProgress.value += Math.random() * 15
    }
  }, 200)

  try {
    emit('upload', selectedFile.value)
  } catch (e) {
    console.error('upload emit error', e)
    error.value = '上传失败'
  } finally {
    clearInterval(progressInterval)
    uploadProgress.value = 100
    setTimeout(() => {
      uploading.value = false
      uploadProgress.value = 0
    }, 500)
  }
}

function handleCameraCapture() {
  // On mobile, open camera directly
  if (fileInput.value) {
    fileInput.value.setAttribute('capture', 'environment')
    fileInput.value.click()
  }
}

defineExpose({
  removeImage,
  getFile: () => selectedFile.value,
  hasImage
})
</script>

<template>
  <div class="space-y-4">
    <!-- Upload Area -->
    <div
      v-if="!hasImage"
      class="relative border-2 border-dashed rounded-xl sm:rounded-2xl transition-all duration-300 cursor-pointer"
      :class="isDragging
        ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20 scale-[1.02]'
        : 'border-surface-300 dark:border-surface-600 hover:border-brand-400 dark:hover:border-brand-500 hover:bg-surface-50 dark:hover:bg-surface-800/50'"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      @click="triggerFileInput"
    >
      <input
        ref="fileInput"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        class="hidden"
        @change="handleFileChange"
      />

      <div class="flex flex-col items-center justify-center py-6 sm:py-10 px-4 sm:px-6">
        <!-- Icon -->
        <div class="w-12 h-12 sm:w-16 sm:h-16 rounded-xl sm:rounded-2xl bg-surface-100 dark:bg-surface-700 flex items-center justify-center mb-3 sm:mb-4"
             :class="isDragging ? 'bg-brand-100 dark:bg-brand-900/30' : ''">
          <svg class="w-6 h-6 sm:w-8 sm:h-8" :class="isDragging ? 'text-brand-500' : 'text-surface-400'" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
          </svg>
        </div>

        <!-- Text -->
        <p class="text-xs sm:text-sm font-medium text-surface-700 dark:text-surface-300 mb-0.5 sm:mb-1">
          {{ isDragging ? '松开上传图片' : '点击或拖拽上传小票图片' }}
        </p>
        <p class="text-[10px] sm:text-xs text-surface-400 dark:text-surface-500">
          支持 JPG、PNG、WEBP，最大 10MB
        </p>

        <!-- Mobile camera button -->
        <button
          type="button"
          @click.stop="handleCameraCapture"
          class="mt-3 sm:mt-4 flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg sm:rounded-xl bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 text-xs sm:text-sm font-medium hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors sm:hidden"
        >
          <svg class="w-3.5 h-3.5 sm:w-4 sm:h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
          </svg>
          拍照上传
        </button>
      </div>
    </div>

    <!-- Preview -->
    <div v-if="hasImage" class="relative group">
      <div class="relative rounded-2xl overflow-hidden border border-surface-200 dark:border-surface-700">
        <img
          :src="previewUrl"
          alt="小票预览"
          class="w-full max-h-64 object-contain bg-surface-50 dark:bg-surface-800"
        />

        <!-- Overlay with actions -->
        <div class="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center gap-3">
          <button
            @click.stop="handleUpload"
            :disabled="uploading"
            class="opacity-0 group-hover:opacity-100 transition-opacity px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-xl shadow-lg text-sm font-medium disabled:opacity-50"
          >
            {{ uploading ? '识别中...' : '开始识别' }}
          </button>
          <button
            @click.stop="removeImage"
            :disabled="uploading"
            class="opacity-0 group-hover:opacity-100 transition-opacity p-2 bg-white/90 dark:bg-surface-800/90 rounded-xl shadow-lg hover:bg-white dark:hover:bg-surface-700 disabled:opacity-50"
          >
            <svg class="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
            </svg>
          </button>
        </div>

        <!-- File info -->
        <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-3">
          <p class="text-xs text-white/80 truncate">
            {{ selectedFile?.name }} · {{ (selectedFile?.size / 1024).toFixed(0) }}KB
          </p>
        </div>
      </div>

      <!-- Upload button -->
      <button
        v-if="!uploading"
        @click="handleUpload"
        class="mt-3 w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-500 hover:bg-brand-600 text-white rounded-xl font-medium transition-colors"
      >
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
        </svg>
        开始识别小票
      </button>

      <!-- Upload progress -->
      <div v-if="uploading" class="mt-3">
        <div class="flex items-center justify-between mb-1.5">
          <span class="text-xs font-medium text-surface-500 dark:text-surface-400">识别中...</span>
          <span class="text-xs font-medium text-brand-600 dark:text-brand-400">{{ Math.round(uploadProgress) }}%</span>
        </div>
        <div class="h-1.5 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
          <div
            class="h-full bg-gradient-to-r from-brand-500 to-violet-500 rounded-full transition-all duration-300"
            :style="{ width: `${uploadProgress}%` }"
          />
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
      <svg class="w-4 h-4 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
      <p class="text-xs text-red-600 dark:text-red-400">{{ error }}</p>
    </div>
  </div>
</template>
