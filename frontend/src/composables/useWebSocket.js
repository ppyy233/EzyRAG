import { ref, onMounted, onUnmounted } from 'vue'

export function useWebSocket(url) {
  const ws = ref(null)
  const messages = ref([])
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000

  const connect = () => {
    try {
      ws.value = new WebSocket(url)
      
      ws.value.onopen = () => {
        console.log('WebSocket 已连接')
        isConnected.value = true
        reconnectAttempts.value = 0
      }
      
      ws.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          messages.value.push(data)
          
          // 限制消息数量
          if (messages.value.length > 100) {
            messages.value = messages.value.slice(-50)
          }
        } catch (e) {
          console.error('解析 WebSocket 消息失败:', e)
        }
      }
      
      ws.value.onclose = () => {
        console.log('WebSocket 已断开')
        isConnected.value = false
        reconnect()
      }
      
      ws.value.onerror = (error) => {
        console.error('WebSocket 错误:', error)
      }
    } catch (e) {
      console.error('WebSocket 连接失败:', e)
    }
  }

  const reconnect = () => {
    if (reconnectAttempts.value < maxReconnectAttempts) {
      reconnectAttempts.value++
      console.log(`尝试重连 (${reconnectAttempts.value}/${maxReconnectAttempts})...`)
      setTimeout(connect, reconnectDelay)
    } else {
      console.error('重连失败，请检查网络连接')
    }
  }

  const send = (data) => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(data))
      return true
    }
    return false
  }

  const disconnect = () => {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
  }

  onMounted(connect)
  onUnmounted(disconnect)

  return {
    messages,
    isConnected,
    send,
    disconnect
  }
}
