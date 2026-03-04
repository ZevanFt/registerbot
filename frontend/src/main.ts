import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useThemeStore } from '@/stores/theme'
import './styles/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

const themeStore = useThemeStore(pinia)
themeStore.init()

app.use(router)
app.mount('#app')
