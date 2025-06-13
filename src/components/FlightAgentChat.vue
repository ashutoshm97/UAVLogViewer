<template>
  <div class="flight-agent-root">
    <button class="download-chat-btn" @click="downloadChatLog">
      📥 Download Transcript
    </button>

    <div class="chat-wrapper">
      <div :class="['agent-container', isDarkMode ? 'dark' : 'light']">
        <header class="agent-header">
          <h3>Telemetric Whisperer</h3>
          <div class="status-bar">
            <span>{{ fileStatus }}</span>
            <button class="toggle-btn" @click="toggleDarkMode">
              {{ isDarkMode ? '☀ Light Mode' : '🌙 Dark Mode' }}
            </button>
          </div>
        </header>

        <div class="chat-window" ref="chatWindow">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message-bubble', msg.type]"
          >
            <p v-html="formatMessage(msg.text)"></p>
            <button
              v-if="msg.type === 'agent'"
              class="download-btn"
              @click="downloadMessage(msg.text, index)"
            >
              ⬇ Download
            </button>
          </div>
          <div v-if="isLoading" class="message-bubble agent">
            <p>Thinking...</p>
          </div>
        </div>

        <form @submit.prevent="sendMessage" class="chat-form">
          <input
            v-model="input"
            type="text"
            placeholder="Ask something about the flight..."
            :disabled="isLoading"
          />
          <button type="submit" :disabled="isLoading">Send</button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'

const messages = ref([])
const input = ref('')
const isLoading = ref(false)
// const fileStatus = ref('Flight log loaded. You can begin querying.')
const isDarkMode = ref(false)

const chatWindow = ref(null)

const toggleDarkMode = () => {
    isDarkMode.value = !isDarkMode.value
}

const scrollToBottom = () => {
    nextTick(() => {
        if (chatWindow.value) {
            chatWindow.value.scrollTop = chatWindow.value.scrollHeight
        }
    })
}

function formatMessage (text) {
    return text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // for **bold**
        .replace(/\*(.*?)\*/g, '<em>$1</em>') // for *italic*
}

watch(messages, scrollToBottom)

const typeAgentMessage = async (text) => {
    const agentMsg = { type: 'agent', text: '' }
    messages.value.push(agentMsg)
    for (let i = 0; i < text.length; i++) {
        agentMsg.text += text[i]
        await nextTick()
        scrollToBottom()
        await new Promise((resolve) => setTimeout(resolve, 10)) // Typing speed
    }
}

const sendMessage = async () => {
    if (!input.value.trim() || isLoading.value) return

    const userMessage = { type: 'user', text: input.value }
    messages.value.push(userMessage)
    const currentInput = input.value
    input.value = ''
    isLoading.value = true

    try {
        const response = await fetch('http://localhost:5000/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: currentInput })
        })
        const data = await response.json()
        await typeAgentMessage(data.response)
    } catch (error) {
        messages.value.push({
            type: 'agent',
            text: 'Sorry, I encountered an error talking to the backend.'
        })
    } finally {
        isLoading.value = false
    }
}

const downloadMessage = (text, index) => {
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `agent-message-${index + 1}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}

const downloadChatLog = () => {
    const log = messages.value
        .map((msg, idx) => {
            const label = msg.type === 'user' ? '🧑 User' : '🤖 Agent'
            return `${label}:\n${msg.text}\n`
        })
        .join('\n---\n\n')

    const blob = new Blob([log], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'flight-chat-transcript.txt'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}

</script>

  <style scoped>
  .agent-container {
    border: 1px solid #d1d5db;
    border-radius: 8px;
    margin: 1rem;
    display: flex;
    flex-direction: column;
    height: 85vh;
    font-family: 'Inter', sans-serif;
    transition: background-color 0.3s ease, color 0.3s ease;
  }

  .agent-header {
    padding: 1rem;
    border-bottom: 1px solid #d1d5db;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .agent-header h3 {
    margin: 0;
    font-size: 1.2rem;
  }

  .status-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.9rem;
  }

  .toggle-btn {
    background: none;
    border: 1px solid #ccc;
    padding: 5px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
  }

  /* Chat */
  .chat-window {
    flex-grow: 1;
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .message-bubble {
    padding: 10px 14px;
    border-radius: 18px;
    max-width: 75%;
    word-wrap: break-word;
    font-size: 0.95rem;
    line-height: 1.5;
  }

  .message-bubble p {
    margin: 0;
  }

  .message-bubble.user {
    align-self: flex-end;
  }

  .message-bubble.agent {
    align-self: flex-start;
  }

  .chat-form {
    display: flex;
    padding: 1rem;
    border-top: 1px solid #d1d5db;
    gap: 10px;
  }

  .chat-form input {
    flex-grow: 1;
    border-radius: 18px;
    padding: 10px 16px;
    font-size: 1rem;
    border: 1px solid #ccc;
  }

  .chat-form button {
    padding: 10px 20px;
    border: none;
    border-radius: 18px;
    cursor: pointer;
    font-size: 1rem;
  }

  /* Light Mode */
  .light {
    background-color: #f5f8ff;
    color: #1c1c1e;
  }

  .light .message-bubble.user {
    background-color: #0057ff;
    color: white;
  }

  .light .message-bubble.agent {
    background-color: #eaf0ff;
    color: #1c1c1e;
  }

  .light .chat-form button {
    background-color: #0057ff;
    color: white;
  }

  .light .chat-form input {
    background-color: white;
    color: #1c1c1e;
  }

  /* Dark Mode */
  .dark {
    background-color: #1e1e1e;
    color: #f9f9f9;
  }

  .dark .agent-header {
    border-color: #444;
  }

  .dark .message-bubble.user {
    background-color: #0a84ff;
    color: white;
  }

  .dark .message-bubble.agent {
    background-color: #2c2c2e;
    color: #f9f9f9;
  }

  .dark .chat-form {
    border-color: #444;
  }

  .dark .chat-form input {
    background-color: #2c2c2e;
    color: white;
    border: 1px solid #555;
  }

  .dark .chat-form button {
    background-color: #0a84ff;
    color: white;
  }

  .dark .toggle-btn {
    color: white;
    border-color: #555;
  }

  .download-btn {
  margin-top: 6px;
  background-color: transparent;
  border: 1px solid #ccc;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 0.8rem;
  cursor: pointer;
  color: inherit;
}
.download-btn:hover {
  background-color: #ddd;
}

.dark .download-btn:hover {
  background-color: #444;
}

.download-chat-btn {
  background: none;
  border: 1px solid #ccc;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  margin-left: 10px;
}

.dark .download-chat-btn {
  color: white;
  border-color: #555;
}
  </style>
