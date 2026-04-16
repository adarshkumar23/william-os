import clsx from "clsx";
import { format } from "date-fns";
import { motion } from "framer-motion";
import { Bot, MessageSquarePlus, Mic, Send, Sparkles, Trash2 } from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";

import { AppCard, Badge, InsightBanner, SkeletonLoader } from "../components/ui";
import { useAuth } from "../contexts/AuthContext";
import { fadeInUp, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { AgentName, ChatMessage, ChatSessionListItem, ChatStreamEvent } from "../types/api";

const AGENT_COLORS: Record<AgentName, string> = {
  os: "bg-accent/20 text-accent border-accent/20",
  health: "bg-emerald-500/20 text-emerald-400 border-emerald-500/20",
  study: "bg-blue-500/20 text-blue-400 border-blue-500/20",
  trading: "bg-purple-500/20 text-purple-400 border-purple-500/20",
  executive: "bg-amber-500/20 text-amber-400 border-amber-500/20",
  recovery: "bg-rose-500/20 text-rose-400 border-rose-500/20",
};

function getWilliamModeByHour(hour: number): string {
  if (hour >= 5 && hour < 12) {
    return "🌅 Morning Mode — Energized";
  }
  if (hour >= 12 && hour < 17) {
    return "⚡ Focus Mode — Analytical";
  }
  if (hour >= 17 && hour < 22) {
    return "🌆 Evening Mode — Reflective";
  }
  return "🌙 Night Mode — Recovery";
}

export default function ChatPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<ChatSessionListItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [chatLoading, setChatLoading] = useState(false);
  const [williamMode, setWilliamMode] = useState(() => getWilliamModeByHour(new Date().getHours()));
  const [error, setError] = useState("");
  const [proactiveSending, setProactiveSending] = useState<"morning" | "afternoon" | "evening" | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Voice Input State
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (activeSessionId) {
      loadMessages(activeSessionId);
    } else {
      setMessages([]);
    }
  }, [activeSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatLoading]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setWilliamMode(getWilliamModeByHour(new Date().getHours()));
    }, 60000);
    return () => window.clearInterval(timer);
  }, []);

  const loadSessions = async () => {
    try {
      const data = (await api.chat.listSessions()) as ChatSessionListItem[];
      setSessions(data);
      if (data.length > 0 && !activeSessionId) {
        setActiveSessionId(data[0].id);
      }
    } catch (err) {
      console.error(err);
      setError("Failed to load chat history");
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (id: string) => {
    setChatLoading(true);
    try {
      const data = (await api.chat.getMessages(id)) as ChatMessage[];
      setMessages(data.reverse());
    } catch {
      setError("Failed to load conversation");
    } finally {
      setChatLoading(false);
    }
  };

  const createSession = async (agent: AgentName = "os") => {
    try {
      const newSession = (await api.chat.createSession({
        agent_name: agent,
        title: "New Conversation",
      })) as ChatSessionListItem;
      setSessions([newSession, ...sessions]);
      setActiveSessionId(newSession.id);
    } catch {
      setError("Failed to create session");
    }
  };

  const deleteSession = async (id: string) => {
    const session = sessions.find((item) => item.id === id);
    const label = session?.title?.trim() || "this conversation";
    if (!window.confirm(`Delete ${label}? This cannot be undone.`)) {
      return;
    }

    try {
      await api.chat.deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      setActiveSessionId((prev) => (prev === id ? null : prev));
    } catch {
      setError("Failed to delete session");
    }
  };

  const sendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || !activeSessionId) return;

    const content = input.trim();
    setInput("");

    // Optimistic UI updates
    const tempId = `temp-${Date.now()}`;
    const assistantTempId = `assistant-temp-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: tempId,
        session_id: activeSessionId,
        user_id: user?.id || "",
        role: "user",
        content,
        created_at: new Date().toISOString(),
      },
      {
        id: assistantTempId,
        session_id: activeSessionId,
        user_id: user?.id || "",
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
      },
    ]);
    setChatLoading(true);

    try {
      await api.chat.streamMessage(activeSessionId, {
        content,
      }, (event: ChatStreamEvent) => {
        if (event.event === "user_message") {
          const userMessage = event.data;
          setMessages((prev) => prev.map((m) => (m.id === tempId ? userMessage : m)));
          return;
        }

        if (event.event === "delta") {
          const partial = event.data.content;
          setMessages((prev) => prev.map((m) => (m.id === assistantTempId ? { ...m, content: partial } : m)));
          return;
        }

        if (event.event === "done") {
          const assistantMessage = event.data.assistant_message;
          setMessages((prev) => prev.map((m) => (m.id === assistantTempId ? assistantMessage : m)));
        }
      });

      // Refresh sessions to get any updated title preview
      api.chat.listSessions().then(setSessions);
    } catch {
      setError("Failed to send message. Please try again.");
      setMessages((prev) => prev.filter((m) => m.id !== tempId && m.id !== assistantTempId));
    } finally {
      setChatLoading(false);
    }
  };

  const toggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        
        // Stop all tracks to release the microphone
        stream.getTracks().forEach((track) => track.stop());

        setChatLoading(true);
        try {
          // Send to transcribe endpoint
          const transcriptionData = await api.voice.transcribe(audioBlob);
          const transcribedText = transcriptionData?.transcription || transcriptionData?.text;
          
          if (transcribedText) {
            setInput(String(transcribedText));
            // Optionally auto-send if confidence > 0.8, but for now we put it in the input box
            if (transcriptionData?.confidence && Number(transcriptionData.confidence) > 0.8) {
               // Schedule the send using the event loop, letting React update the state
               setTimeout(() => {
                 const fakeFormEvent = { preventDefault: () => {} } as React.FormEvent;
                 sendMessage(fakeFormEvent);
               }, 100);
            }
          }
        } catch (err) {
          setError("Failed to process voice command");
        } finally {
          setChatLoading(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      setError("Microphone access denied or error occurred");
    }
  };

  const triggerProactive = async (trigger: "morning" | "afternoon" | "evening") => {
    if (!activeSessionId) {
      return;
    }
    setProactiveSending(trigger);
    try {
      await api.chat.triggerProactive(trigger);
      await loadMessages(activeSessionId);
    } catch {
      setError("Failed to send proactive message.");
    } finally {
      setProactiveSending(null);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] w-full gap-6">
      {/* Sidebar: Session History */}
      <AppCard className="flex w-80 flex-col overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-border p-4">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-text-primary">Conversations</h2>
          </div>
          <button
            onClick={() => createSession("os")}
            className="rounded-lg p-1.5 text-text-muted hover:bg-surface-raised hover:text-text-primary"
            title="New Chat"
          >
            <MessageSquarePlus className="h-5 w-5" />
          </button>
        </div>
        
        <div className="flex gap-2 overflow-x-auto border-b border-border px-4 py-3 hide-scrollbar">
           {(["os", "executive", "health", "study", "trading", "recovery"] as AgentName[]).map((agent) => (
             <button
                key={agent}
                onClick={() => createSession(agent)}
                className={clsx(
                  "shrink-0 rounded-full border px-3 py-1 text-xs font-medium capitalize outline-none transition",
                  AGENT_COLORS[agent],
                  "hover:opacity-80"
                )}
             >
               + {agent}
             </button>
           ))}
        </div>

        <div className="flex-1 overflow-y-auto outline-none">
          {loading ? (
            <div className="space-y-4 p-4">
              <SkeletonLoader variant="text" lines={2} />
              <SkeletonLoader variant="text" lines={2} />
            </div>
          ) : sessions.length === 0 ? (
            <div className="p-4 text-center text-sm text-text-muted">No conversations yet.</div>
          ) : (
            <div className="divide-y divide-border">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  onClick={() => setActiveSessionId(s.id)}
                  className={clsx(
                    "group relative cursor-pointer p-4 outline-none transition",
                    activeSessionId === s.id ? "bg-surface-raised" : "hover:bg-surface-raised/50",
                  )}
                >
                  <div className="flex items-start justify-between">
                    <p className="max-w-[70%] truncate text-sm font-medium text-text-primary">{s.title}</p>
                    <span className="text-xs text-text-muted">{format(new Date(s.updated_at), "MMM d")}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between">
                    <p className="truncate text-xs text-text-secondary">
                      {s.last_message_preview || "No messages"}
                    </p>
                    <Badge label={s.agent_name} className="ml-2 capitalize" variant={s.agent_name === 'os' ? 'accent' : 'default'} />
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSession(s.id);
                    }}
                    className="absolute right-2 top-2 hidden rounded p-1 text-text-muted hover:bg-surface hover:text-danger group-hover:block"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </AppCard>

      {/* Main Chat Area */}
      <AppCard className="flex flex-1 flex-col overflow-hidden relative p-0">
         {error && (
            <div className="absolute top-4 left-4 right-4 z-10">
              <InsightBanner text={error} type="danger" dismissible />
            </div>
         )}
        
        {/* Header */}
        <div className="flex h-16 shrink-0 items-center border-b border-border px-6">
          <div className="flex items-center justify-between w-full gap-3">
            <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-surface-raised border border-border">
              <Bot className="h-5 w-5 text-accent" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-text-primary">
                {sessions.find((s) => s.id === activeSessionId)?.title || "Select a conversation"}
              </h2>
              <p className="text-xs text-text-muted capitalize">
                {sessions.find((s) => s.id === activeSessionId)?.agent_name || "William OS"} Agent
              </p>
              <p className="mt-1 text-[11px] font-medium tracking-wide text-accent">
                {williamMode}
              </p>
            </div>
            </div>
            <div className="hidden items-center gap-2 md:flex">
              {activeSessionId ? (
                <button
                  type="button"
                  onClick={() => void deleteSession(activeSessionId)}
                  className="inline-flex items-center gap-1 rounded-lg border border-border px-2 py-1 text-xs text-text-secondary hover:text-danger"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Delete
                </button>
              ) : null}
              {(["morning", "afternoon", "evening"] as const).map((trigger) => (
                <button
                  key={trigger}
                  type="button"
                  onClick={() => void triggerProactive(trigger)}
                  disabled={proactiveSending === trigger}
                  className="inline-flex items-center gap-1 rounded-lg border border-border px-2 py-1 text-xs text-text-secondary hover:text-text-primary disabled:opacity-40"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  {proactiveSending === trigger ? "Sending..." : trigger}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Message List */}
        <div className="flex-1 overflow-y-auto p-6 scroll-smooth">
          {!activeSessionId ? (
            <div className="flex h-full items-center justify-center text-sm text-text-muted">
              Select or start a new conversation.
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg, idx) => {
                const isUser = msg.role === "user";
                const proactive = Boolean((msg.extra_metadata && msg.extra_metadata.proactive) || (msg.metadata && msg.metadata.proactive));
                return (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    key={msg.id || idx}
                    className={clsx("flex w-full group", isUser ? "justify-end" : "justify-start")}
                  >
                    <div
                      className={clsx(
                        "relative max-w-[80%] rounded-2xl p-4 text-sm whitespace-pre-wrap",
                        isUser
                          ? "bg-accent text-white"
                          : proactive
                            ? "bg-amber-400/10 border border-amber-400/30 text-text-primary"
                            : "bg-surface-raised border border-border text-text-primary",
                      )}
                    >
                      {proactive && !isUser ? (
                        <p className="mb-2 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                          <Sparkles className="h-3 w-3" /> Proactive check-in
                        </p>
                      ) : null}
                      {!isUser && !msg.content && chatLoading ? "Thinking..." : msg.content}
                      
                      {msg.actions_taken && msg.actions_taken.length > 0 && (
                        <div className="mt-3 space-y-2 border-t border-border pt-3">
                           <p className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-1">Actions Executed</p>
                           {msg.actions_taken.map((act, i) => (
                             <div key={i} className={clsx("text-xs p-2 rounded-lg", act.success ? "bg-success/15 text-success" : "bg-danger/15 text-danger")}>
                               {act.message}
                             </div>
                           ))}
                        </div>
                      )}
                      
                      <span className="absolute -bottom-5 text-[10px] text-text-muted opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                        {format(new Date(msg.created_at), "h:mm a")}
                      </span>
                    </div>
                  </motion.div>
                );
              })}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="rounded-2xl border border-border bg-surface-raised p-4">
                     <div className="flex gap-1 items-center h-[20px]">
                        <span className="h-2 w-2 rounded-full bg-text-muted animate-bounce" />
                        <span className="h-2 w-2 rounded-full bg-text-muted animate-bounce delay-75" />
                        <span className="h-2 w-2 rounded-full bg-text-muted animate-bounce delay-150" />
                     </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} className="h-8" />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="shrink-0 border-t border-border bg-surface p-4">
          <form
            onSubmit={sendMessage}
            className="flex items-center gap-2 rounded-xl border border-border bg-surface-raised p-2 focus-within:border-border-strong focus-within:ring-1 focus-within:ring-accent"
          >
            <button
              type="button"
              className={clsx("rounded-lg p-2 transition", isRecording ? "bg-danger/20 text-danger" : "text-text-muted hover:text-text-primary")}
              onClick={() => void toggleRecording()}
              title="Voice Input (Coming soon)"
            >
              <Mic className="h-5 w-5" />
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask WILLIAM OS..."
              className="flex-1 bg-transparent px-2 py-2 text-sm outline-none placeholder:text-text-muted"
              disabled={!activeSessionId || chatLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || !activeSessionId || chatLoading}
              className="rounded-lg bg-accent p-2 text-white transition hover:bg-accent-hover disabled:opacity-50"
            >
              <Send className="h-5 w-5" />
            </button>
          </form>
          <div className="mt-2 text-center">
            <p className="text-[10px] text-text-muted">WILLIAM OS uses AI block scheduling and memory insights.</p>
          </div>
        </div>
      </AppCard>
    </div>
  );
}
