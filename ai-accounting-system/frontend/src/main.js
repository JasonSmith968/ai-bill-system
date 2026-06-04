import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { vPermission } from './directives/v-permission'
import { getWSClient } from '@/utils/websocket'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

app.directive('permission', vPermission)

app.mount('#app')

// Connect WebSocket if user is already logged in (page refresh)
const token = localStorage.getItem('token')
if (token) {
  getWSClient().connect(token)
}

// Watch for login/logout to connect/disconnect WebSocket
pinia.use(({ store }) => {
  if (store.$id === 'user') {
    store.$subscribe((_mutation, state) => {
      const ws = getWSClient()
      if (state.token && !ws.connected) {
        ws.connect(state.token)
      } else if (!state.token && ws.connected) {
        ws.disconnect()
      }
    })
  }
})