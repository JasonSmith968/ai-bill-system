<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/utils/api'

const stats = ref({
  users: { total: 0, active: 0, new_today: 0 },
  transactions: { total: 0, today: 0, today_income: 0, today_expense: 0 }
})

const users = ref([])
const categories = ref([])
const loading = ref(true)
const activeTab = ref('overview')

const userPagination = ref({ page: 1, per_page: 20, total: 0, pages: 0 })
const categoryForm = ref({ name: '', type: 'expense', icon: 'tag', color: '#6B7280' })
const showCategoryModal = ref(false)
const editingCategory = ref(null)

const tabs = [
  { key: 'overview', label: '概览', icon: `<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6z" /></svg>` },
  { key: 'users', label: '用户', icon: `<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" /></svg>` },
  { key: 'categories', label: '分类', icon: `<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" /><path stroke-linecap="round" stroke-linejoin="round" d="M6 6h.008v.008H6V6z" /></svg>` },
]

onMounted(async () => { await loadData() })

async function loadData() {
  loading.value = true
  try { await Promise.all([loadStats(), loadUsers(), loadCategories()]) }
  finally { loading.value = false }
}

async function loadStats() {
  try { const { data } = await api.get('/admin/stats'); stats.value = data } catch (e) { console.error(e) }
}

async function loadUsers() {
  try {
    const { data } = await api.get('/admin/users', { params: { page: userPagination.value.page, per_page: userPagination.value.per_page } })
    users.value = data.users; userPagination.value.total = data.total; userPagination.value.pages = data.pages
  } catch (e) { console.error(e) }
}

async function loadCategories() {
  try { const { data } = await api.get('/admin/categories'); categories.value = data.categories } catch (e) { console.error(e) }
}

async function toggleUserStatus(user) {
  try { await api.put(`/admin/users/${user.id}/status`, { is_active: !user.is_active }); user.is_active = !user.is_active } catch (e) { alert('操作失败') }
}

async function toggleAdminStatus(user) {
  try { await api.put(`/admin/users/${user.id}/status`, { is_admin: !user.is_admin }); user.is_admin = !user.is_admin } catch (e) { alert('操作失败') }
}

function openCategoryModal(category = null) {
  editingCategory.value = category
  categoryForm.value = category
    ? { name: category.name, type: category.type, icon: category.icon, color: category.color }
    : { name: '', type: 'expense', icon: 'tag', color: '#6B7280' }
  showCategoryModal.value = true
}

async function saveCategory() {
  try {
    if (editingCategory.value) { await api.put(`/admin/categories/${editingCategory.value.id}`, categoryForm.value) }
    else { await api.post('/admin/categories', categoryForm.value) }
    showCategoryModal.value = false; await loadCategories()
  } catch (e) { alert(e.response?.data?.error || '操作失败') }
}

async function deleteCategory(id) {
  if (!confirm('确定要删除这个分类吗？')) return
  try { await api.delete(`/admin/categories/${id}`); await loadCategories() } catch (e) { alert(e.response?.data?.error || '删除失败') }
}

function formatAmount(n) { return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(n) }
function formatDate(d) { return new Date(d).toLocaleDateString('zh-CN') }
</script>

<template>
  <div class="animate-fade-in space-y-6">
    <h1 class="text-2xl font-bold text-surface-900 dark:text-white">管理后台</h1>

    <!-- Tabs -->
    <div class="flex gap-1 p-1 bg-surface-100 dark:bg-surface-800 rounded-xl">
      <button
        v-for="tab in tabs" :key="tab.key"
        @click="activeTab = tab.key"
        class="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-medium transition-all duration-200"
        :class="activeTab === tab.key
          ? 'bg-white dark:bg-surface-700 text-brand-600 dark:text-brand-400 shadow-sm'
          : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'"
      >
        <span v-html="tab.icon" />
        {{ tab.label }}
      </button>
    </div>

    <!-- Overview -->
    <div v-if="activeTab === 'overview'" class="space-y-6">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="card in [
          { title: '总用户数', value: stats.users.total, color: 'text-brand-600 dark:text-brand-400' },
          { title: '活跃用户', value: stats.users.active, color: 'text-emerald-600 dark:text-emerald-400' },
          { title: '今日新增', value: stats.users.new_today, color: 'text-violet-600 dark:text-violet-400' },
          { title: '总交易数', value: stats.transactions.total, color: 'text-amber-600 dark:text-amber-400' },
        ]" :key="card.title" class="card-hover">
          <p class="text-sm text-surface-500 mb-1">{{ card.title }}</p>
          <p class="text-2xl font-bold" :class="card.color">{{ card.value }}</p>
        </div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="card-hover">
          <p class="text-sm text-surface-500 mb-1">今日交易</p>
          <p class="text-2xl font-bold text-surface-900 dark:text-white">{{ stats.transactions.today }} 笔</p>
        </div>
        <div class="card-hover">
          <p class="text-sm text-surface-500 mb-1">今日收入</p>
          <p class="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{{ formatAmount(stats.transactions.today_income) }}</p>
        </div>
        <div class="card-hover">
          <p class="text-sm text-surface-500 mb-1">今日支出</p>
          <p class="text-2xl font-bold text-rose-600 dark:text-rose-400">{{ formatAmount(stats.transactions.today_expense) }}</p>
        </div>
      </div>
    </div>

    <!-- Users -->
    <div v-if="activeTab === 'users'" class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-surface-100 dark:border-surface-700/50">
              <th class="text-left py-3 px-5 text-xs font-semibold text-surface-400 uppercase tracking-wider">ID</th>
              <th class="text-left py-3 px-5 text-xs font-semibold text-surface-400 uppercase tracking-wider">用户名</th>
              <th class="text-left py-3 px-5 text-xs font-semibold text-surface-400 uppercase tracking-wider">邮箱</th>
              <th class="text-left py-3 px-5 text-xs font-semibold text-surface-400 uppercase tracking-wider">注册时间</th>
              <th class="text-left py-3 px-5 text-xs font-semibold text-surface-400 uppercase tracking-wider">状态</th>
              <th class="text-left py-3 px-5 text-xs font-semibold text-surface-400 uppercase tracking-wider">管理员</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-surface-100 dark:divide-surface-700/50">
            <tr v-for="user in users" :key="user.id" class="hover:bg-surface-50 dark:hover:bg-surface-700/30 transition-colors">
              <td class="py-3 px-5 text-sm text-surface-500">{{ user.id }}</td>
              <td class="py-3 px-5 text-sm font-medium text-surface-800 dark:text-surface-200">{{ user.username }}</td>
              <td class="py-3 px-5 text-sm text-surface-500">{{ user.email }}</td>
              <td class="py-3 px-5 text-sm text-surface-500">{{ formatDate(user.created_at) }}</td>
              <td class="py-3 px-5">
                <button @click="toggleUserStatus(user)" class="px-2.5 py-0.5 text-xs font-semibold rounded-full transition-colors"
                  :class="user.is_active ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400' : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'">
                  {{ user.is_active ? '正常' : '禁用' }}
                </button>
              </td>
              <td class="py-3 px-5">
                <button @click="toggleAdminStatus(user)" class="px-2.5 py-0.5 text-xs font-semibold rounded-full transition-colors"
                  :class="user.is_admin ? 'bg-violet-50 text-violet-700 dark:bg-violet-900/20 dark:text-violet-400' : 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400'">
                  {{ user.is_admin ? '是' : '否' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="userPagination.pages > 1" class="flex justify-center gap-2 p-4 border-t border-surface-100 dark:border-surface-700/50">
        <button v-for="page in userPagination.pages" :key="page" @click="userPagination.page = page; loadUsers()"
          class="w-9 h-9 rounded-lg text-sm font-medium transition-all"
          :class="page === userPagination.page ? 'bg-brand-600 text-white shadow-md' : 'text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700'">
          {{ page }}
        </button>
      </div>
    </div>

    <!-- Categories -->
    <div v-if="activeTab === 'categories'">
      <div class="flex justify-end mb-4">
        <button @click="openCategoryModal()" class="btn-primary flex items-center gap-2">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
          添加分类
        </button>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div v-for="type in ['expense', 'income']" :key="type" class="card">
          <h3 class="font-semibold text-surface-900 dark:text-white mb-3 flex items-center gap-2">
            <div class="w-2 h-2 rounded-full" :class="type === 'expense' ? 'bg-rose-500' : 'bg-emerald-500'" />
            {{ type === 'expense' ? '支出分类' : '收入分类' }}
          </h3>
          <div class="space-y-1">
            <div v-for="cat in categories.filter(c => c.type === type)" :key="cat.id"
              class="flex items-center justify-between p-2.5 rounded-xl hover:bg-surface-50 dark:hover:bg-surface-700/30 transition-colors group">
              <div class="flex items-center gap-3">
                <div class="w-3 h-3 rounded-full" :style="{ backgroundColor: cat.color }" />
                <span class="text-sm font-medium text-surface-800 dark:text-surface-200">{{ cat.name }}</span>
                <span v-if="cat.is_default" class="text-xs text-surface-400">默认</span>
              </div>
              <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button @click="openCategoryModal(cat)" class="p-1.5 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 text-surface-400 hover:text-brand-600">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" /></svg>
                </button>
                <button v-if="!cat.is_default" @click="deleteCategory(cat.id)" class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-surface-400 hover:text-red-500">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Category Modal -->
    <Transition name="fade">
      <div v-if="showCategoryModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="fixed inset-0 bg-black/40 backdrop-blur-sm" @click="showCategoryModal = false" />
        <Transition name="scale" appear>
          <div class="relative bg-white dark:bg-surface-800 rounded-2xl shadow-xl w-full max-w-md p-6 border border-surface-200 dark:border-surface-700">
            <h2 class="text-lg font-bold text-surface-900 dark:text-white mb-5">{{ editingCategory ? '编辑分类' : '添加分类' }}</h2>
            <form @submit.prevent="saveCategory" class="space-y-4">
              <div><label class="label">分类名称</label><input v-model="categoryForm.name" type="text" class="input-field" required /></div>
              <div><label class="label">类型</label>
                <select v-model="categoryForm.type" class="input-field">
                  <option value="expense">支出</option>
                  <option value="income">收入</option>
                </select>
              </div>
              <div><label class="label">颜色</label><input v-model="categoryForm.color" type="color" class="w-full h-10 rounded-xl cursor-pointer border border-surface-200 dark:border-surface-600" /></div>
              <div class="flex gap-3 pt-2">
                <button type="submit" class="flex-1 btn-primary py-3">保存</button>
                <button type="button" @click="showCategoryModal = false" class="flex-1 btn-secondary py-3">取消</button>
              </div>
            </form>
          </div>
        </Transition>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.fade-enter-active { transition: opacity 0.2s ease; }
.fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.scale-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.scale-leave-active { transition: all 0.15s ease; }
.scale-enter-from, .scale-leave-to { opacity: 0; transform: scale(0.95); }
</style>