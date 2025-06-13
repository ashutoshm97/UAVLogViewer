<template>
  <div class="agent-container">
    <header class="agent-header">
      <h3>Agentic Flight Log Analyst</h3>
      <div class="status-bar">
        <button @click="triggerFileUpload" :disabled="isLoading">
          Upload .bin Log
        </button>
        <input
          type="file"
          ref="fileInput"
          @change="handleFileUpload"
          style="display: none"
          accept=".bin"
        />
        <span>{{ fileStatus }}</span>
      </div>
    </header>

    <div class="chat-window" ref="chatWindow">
      <div v-for="(msg, index) in messages" :key="index" :class="['message-bubble', msg.type]">
        <p v-html="msg.text"></p>
      </div>
      <div v-if="isLoading" class="message-bubble agent">
        <p>Thinking...</p>
      </div>
    </div>

    <form @submit.prevent="sendMessage" class="chat-form">
      <input
        v-model="input"
        type="text"
        placeholder="What was the highest altitude?"
        :disabled="isLoading"
      />
      <button type="submit" :disabled="isLoading">Send</button>
    </form>
  </div>
</template>

<script>
export default {
    name: 'AgentView',
    data () {
        return {
            messages: [],
            input: '',
            isLoading: false,
            fileStatus: 'Please upload a .bin flight log to begin.'
        }
    },
    methods: {
        scrollToBottom () {
            this.$nextTick(() => {
                const chatWindow = this.$refs.chatWindow
                if (chatWindow) {
                    chatWindow.scrollTop = chatWindow.scrollHeight
                }
            })
        },
        triggerFileUpload () {
            this.$refs.fileInput.click()
        },
        async handleFileUpload (event) {
            const file = event.target.files[0]
            if (!file) return

            this.fileStatus = `Uploading "${file.name}"...`
            this.isLoading = true
            const formData = new FormData()
            formData.append('file', file)

            try {
                const response = await fetch('http://localhost:5000/api/upload', {
                    method: 'POST',
                    body: formData
                })
                const data = await response.json()
                if (response.ok) {
                    this.fileStatus = `File "${file.name}" loaded successfully.`
                    this.messages = [{ type: 'agent', text: 'Log file loaded. I am ready to analyze the flight.' }]
                } else {
                    this.fileStatus = `Error: ${data.error || 'Upload failed.'}`
                }
            } catch (error) {
                this.fileStatus = 'Error: Cannot connect to backend server.'
            } finally {
                this.isLoading = false
                this.scrollToBottom()
            }
        },
        async sendMessage () {
            if (!this.input.trim() || this.isLoading) return

            const userMessage = { type: 'user', text: this.input }
            this.messages.push(userMessage)
            const currentInput = this.input
            this.input = ''
            this.isLoading = true
            this.scrollToBottom()

            try {
                const response = await fetch('http://localhost:5000/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: currentInput })
                })
                const data = await response.json()
                // Replace newlines with <br> for HTML rendering
                const formattedText = data.response.replace(/\n/g, '<br>')
                this.messages.push({ type: 'agent', text: formattedText })
            } catch (error) {
                this.messages.push({ type: 'agent', text: 'Sorry, I encountered an error talking to the backend.' })
            } finally {
                this.isLoading = false
                this.scrollToBottom()
            }
        }
    }
}
</script>

<style scoped>
  /* These styles are scoped and will NOT affect the rest of your app. */
  .agent-container {
    border: 1px solid #e0e0e0;
    margin: 1rem;
    display: flex;
    flex-direction: column;
    height: calc(100vh - 2rem - 2px); /* Full viewport height minus margin and border */
    background-color: #ffffff;
    box-sizing: border-box;
  }
  .agent-header { padding: 1rem; border-bottom: 1px solid #e0e0e0; }
  .agent-header h3 { margin: 0 0 0.5rem 0; }
  .status-bar { display: flex; align-items: center; gap: 12px; font-size: 0.9rem; color: #666; }
  .status-bar button { padding: 6px 10px; border-radius: 6px; border: 1px solid #ccc;
   background-color: #f7f7f7; cursor: pointer; }
  .status-bar button:disabled { cursor: not-allowed; opacity: 0.6; }
  .chat-window { flex-grow: 1; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 12px; }
  .message-bubble { padding: 10px 14px; border-radius: 18px; max-width: 75%; word-wrap: break-word; }
  .message-bubble p { margin: 0; }
  .message-bubble.user { background-color: #007bff; color: white; align-self: flex-end; }
  .message-bubble.agent { background-color: #f0f0f0; color: black; align-self: flex-start; text-align: left; }
  .chat-form { display: flex; padding: 1rem; border-top: 1px solid #e0e0e0; gap: 10px; }
  .chat-form input { flex-grow: 1; border: 1px solid #ccc; border-radius: 18px; padding: 10px 16px; font-size: 1rem; }
  .chat-form button { padding: 10px 20px; border: none;
   background-color: #007bff; color: white; border-radius: 18px; cursor: pointer; font-size: 1rem; }
  .chat-form button:disabled { background-color: #a0c3e8; cursor: not-allowed; }
</style>
