import { useState, useEffect, useCallback, useRef } from 'react'
import type { WSEvent } from '@/types/api'

interface UseWebSocketOptions {
  onMessage?: (event: WSEvent) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: Event) => void
  reconnect?: boolean
  reconnectInterval?: number
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WSEvent | null>(null)
  const [messages, setMessages] = useState<WSEvent[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnect = true,
    reconnectInterval = 3000,
  } = options

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        setIsConnected(true)
        onConnect?.()
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WSEvent
          setLastMessage(data)
          setMessages((prev) => [...prev.slice(-99), data])
          onMessage?.(data)
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        onDisconnect?.()

        if (reconnect) {
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        }
      }

      ws.onerror = (error) => {
        onError?.(error)
      }

      wsRef.current = ws
    } catch (error) {
      console.error('WebSocket connection error:', error)
    }
  }, [url, onMessage, onConnect, onDisconnect, onError, reconnect, reconnectInterval])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const sendMessage = useCallback((data: object) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
    setLastMessage(null)
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return {
    isConnected,
    lastMessage,
    messages,
    sendMessage,
    clearMessages,
    disconnect,
    reconnect: connect,
  }
}

export function useRunWebSocket(runId: string, options: Omit<UseWebSocketOptions, 'url'> = {}) {
  const wsUrl = `ws://${window.location.host}/api/ws/runs/${runId}`
  return useWebSocket(wsUrl, options)
}

export function useGlobalWebSocket(options: Omit<UseWebSocketOptions, 'url'> = {}) {
  const wsUrl = `ws://${window.location.host}/api/ws/global`
  return useWebSocket(wsUrl, options)
}
