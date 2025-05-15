<template>
    <div>
        <!-- Floating icon button to reopen chat -->
        <div v-if="!show" class="chat-icon" @click="show = true">
            <i class="fa fa-comments"></i>
        </div>

        <!-- Main chat widget -->
        <div class="widget" v-bind:class="{ hidden: !show }" ref="chatWidget">
            <div class="widget-header" @mousedown="startDragging">
                <span>Flight Log Chat</span>
                <div class="header-controls">
                    <button class="control-button" @click="toggleSize">
                        <i :class="['fas', isExpanded ? 'fa-compress-alt' : 'fa-expand-alt']"></i>
                    </button>
                    <button class="close-button" @click="show = false">×</button>
                </div>
            </div>
            <div class="chat-container">
                <div class="messages" ref="messagesContainer">
                    <div v-for="(message, index) in messages" :key="index"
                        :class="['message', message.role]">
                        <div class="message-content" v-html="renderMarkdown(message.content)"></div>
                    </div>
                </div>
                <div class="input-container">
                    <input
                        v-model="userInput"
                        @keyup.enter="sendMessage"
                        placeholder="Ask about your flight log..."
                        type="text"
                    />
                    <button @click="sendMessage" :disabled="isLoading">
                        {{ isLoading ? 'Sending...' : 'Send' }}
                    </button>
                </div>
            </div>
            <div class="resize-handle"></div>
        </div>
    </div>
</template>

<script>
import { store } from '@/components/Globals.js'
import { marked } from 'marked'

export default {
    name: 'ChatWidget',
    data () {
        return {
            show: true,
            userInput: '',
            messages: [],
            isLoading: false,
            state: store,
            isExpanded: false,
            isDragging: false,
            dragOffset: { x: 0, y: 0 },
            originalSize: { width: 400, height: 600 }
        }
    },
    watch: {
        'state.showChat': {
            handler (newVal) {
                this.show = newVal
            },
            immediate: true
        },
        show (newVal) {
            this.state.showChat = newVal
        },
        messages: {
            handler () {
                this.$nextTick(() => {
                    this.scrollToBottom()
                })
            },
            deep: true
        }
    },
    mounted () {
        // Store original size
        const widget = this.$refs.chatWidget
        if (widget) {
            this.originalSize = {
                width: widget.offsetWidth,
                height: widget.offsetHeight
            }
        }

        // Add event listeners for dragging
        document.addEventListener('mousemove', this.onDrag)
        document.addEventListener('mouseup', this.stopDragging)
    },
    beforeDestroy () {
        // Remove event listeners
        document.removeEventListener('mousemove', this.onDrag)
        document.removeEventListener('mouseup', this.stopDragging)
    },
    methods: {
        renderMarkdown (content) {
            return marked(content, {
                breaks: true,
                gfm: true
            })
        },
        toggleSize () {
            const widget = this.$refs.chatWidget
            if (!widget) return

            this.isExpanded = !this.isExpanded

            if (this.isExpanded) {
                // Save current size before expanding
                this.originalSize = {
                    width: widget.offsetWidth,
                    height: widget.offsetHeight
                }
                // Expand to maximum size
                widget.style.width = '800px'
                widget.style.height = '800px'
            } else {
                // Restore original size
                widget.style.width = `${this.originalSize.width}px`
                widget.style.height = `${this.originalSize.height}px`
            }
        },
        startDragging (event) {
            if (event.target.closest('.control-button, .close-button')) return

            this.isDragging = true
            const widget = this.$refs.chatWidget
            this.dragOffset = {
                x: event.clientX - widget.offsetLeft,
                y: event.clientY - widget.offsetTop
            }
        },
        onDrag (event) {
            if (!this.isDragging) return

            const widget = this.$refs.chatWidget
            const newLeft = event.clientX - this.dragOffset.x
            const newTop = event.clientY - this.dragOffset.y

            // Ensure the widget stays within the viewport
            const maxX = window.innerWidth - widget.offsetWidth
            const maxY = window.innerHeight - widget.offsetHeight

            widget.style.left = `${Math.max(0, Math.min(newLeft, maxX))}px`
            widget.style.top = `${Math.max(0, Math.min(newTop, maxY))}px`
        },
        stopDragging () {
            this.isDragging = false
        },
        scrollToBottom () {
            const container = this.$refs.messagesContainer
            if (container) {
                container.scrollTop = container.scrollHeight
            }
        },
        async sendMessage () {
            if (!this.userInput.trim() || this.isLoading) return

            // Add user message to chat
            this.messages.push({
                role: 'user',
                content: this.userInput
            })

            const question = this.userInput
            this.userInput = ''
            this.isLoading = true

            try {
                // Prepare telemetry data
                const telemetry = {
                    attitude: this.state.timeAttitude,
                    trajectory: this.state.currentTrajectory,
                    flightModes: this.state.flightModeChanges,
                    messages: this.state.messages,
                    airspeed: this.state.messages?.ARSP || this.state.messages?.ASP2 || this.state.messages?.VFR_HUD,
                    groundSpeed: this.state.messages?.VFR_HUD?.groundspeed || this.state.messages?.GPS?.vel,
                    gps: this.state.messages?.GPS,
                    altitude: this.state.messages?.VFR_HUD?.alt || this.state.messages?.GPS?.alt
                }

                const response = await fetch('http://127.0.0.1:8000/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question, telemetry })
                })

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`)
                }

                const data = await response.json()

                // Add AI response to chat
                this.messages.push({
                    role: 'assistant',
                    content: data.answer
                })
            } catch (error) {
                console.error('Error:', error)
                this.messages.push({
                    role: 'assistant',
                    content: 'Sorry, I encountered an error processing your request.'
                })
            } finally {
                this.isLoading = false
                this.$nextTick(() => {
                    this.scrollToBottom()
                })
            }
        }
    }
}
</script>

<style scoped>
.widget {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 400px;
    height: 600px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    display: flex;
    flex-direction: column;
    z-index: 1000;
    resize: both;
    overflow: hidden;
    min-width: 300px;
    min-height: 400px;
    max-width: 800px;
    max-height: 800px;
    transition: width 0.3s, height 0.3s;
}

.widget.expanded {
    width: 800px;
    height: 800px;
}

.chat-icon {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 60px;
    height: 60px;
    background: #007bff;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    z-index: 1000;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s;
}

.chat-icon:hover {
    transform: scale(1.1);
}

.chat-icon i {
    color: white;
    font-size: 24px;
}

.widget.hidden {
    display: none;
}

.widget-header {
    padding: 16px;
    background: linear-gradient(to right, #2c3e50, #3498db);
    color: white;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: move;
    user-select: none;
}

.close-button {
    background: none;
    border: none;
    color: white;
    font-size: 20px;
    cursor: pointer;
    padding: 0 5px;
}

.header-controls {
    display: flex;
    gap: 8px;
    align-items: center;
}

.control-button {
    background: none;
    border: none;
    color: white;
    font-size: 16px;
    cursor: pointer;
    padding: 0 5px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 4px;
    transition: background-color 0.2s;
}

.control-button:hover {
    background: rgba(255, 255, 255, 0.1);
}

.chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: #f8f9fa;
    overflow: hidden;
}

.messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    scroll-behavior: smooth;
}

.message {
    margin-bottom: 12px;
    padding: 12px 16px;
    border-radius: 12px;
    max-width: 85%;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    line-height: 1.5;
}

.message.user {
    background: linear-gradient(135deg, #007bff, #0056b3);
    color: white;
    margin-left: auto;
    border-bottom-right-radius: 4px;
}

.message.assistant {
    background: white;
    color: #2c3e50;
    margin-right: auto;
    border-bottom-left-radius: 4px;
    border: 1px solid #e9ecef;
}

.input-container {
    padding: 16px;
    background: white;
    border-top: 1px solid #e9ecef;
    display: flex;
    gap: 12px;
}

.input-container input {
    flex: 1;
    padding: 12px;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    font-size: 14px;
    transition: border-color 0.2s;
}

.input-container input:focus {
    outline: none;
    border-color: #007bff;
    box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}

.input-container button {
    padding: 12px 20px;
    background: linear-gradient(135deg, #007bff, #0056b3);
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 500;
    transition: transform 0.2s, box-shadow 0.2s;
}

.input-container button:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.input-container button:disabled {
    background: #e9ecef;
    cursor: not-allowed;
}

.resize-handle {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 15px;
    height: 15px;
    cursor: se-resize;
    background: linear-gradient(135deg, transparent 50%, #007bff 50%);
    border-bottom-right-radius: 12px;
    opacity: 0.5;
    transition: opacity 0.2s;
}

.resize-handle:hover {
    opacity: 1;
}

.message-content {
    white-space: pre-wrap;
    word-break: break-word;
}

.message-content :deep(ul) {
    margin: 0;
    padding-left: 20px;
}

.message-content :deep(p) {
    margin: 0;
}

.message-content :deep(strong) {
    font-weight: 600;
}
</style>
