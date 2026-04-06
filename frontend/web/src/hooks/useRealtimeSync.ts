import { useEffect, useRef } from "react";

import { useAuth } from "../contexts/AuthContext";
import { getAccessToken } from "../services/api";
import { RealtimeWebSocketClient, SyncMessage } from "../services/websocket";

type RealtimeCallbacks = {
  onScheduleUpdated?: (message: SyncMessage) => void;
  onHabitCheckedIn?: (message: SyncMessage) => void;
  onMedicineLogged?: (message: SyncMessage) => void;
  onJournalCreated?: (message: SyncMessage) => void;
  onBlockCompleted?: (message: SyncMessage) => void;
};

export function useRealtimeSync(callbacks: RealtimeCallbacks = {}) {
  const { currentUser } = useAuth();
  const callbacksRef = useRef<RealtimeCallbacks>(callbacks);

  useEffect(() => {
    callbacksRef.current = callbacks;
  }, [callbacks]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }

    const token = getAccessToken();
    if (!token) {
      return;
    }

    const client = new RealtimeWebSocketClient({
      token,
      onMessage: (message) => {
        switch (message.type) {
          case "schedule_updated":
            callbacksRef.current.onScheduleUpdated?.(message);
            break;
          case "habit_checked_in":
            callbacksRef.current.onHabitCheckedIn?.(message);
            break;
          case "medicine_logged":
            callbacksRef.current.onMedicineLogged?.(message);
            break;
          case "journal_created":
            callbacksRef.current.onJournalCreated?.(message);
            break;
          case "block_completed":
            callbacksRef.current.onBlockCompleted?.(message);
            break;
          default:
            break;
        }
      },
    });

    client.connect();
    return () => {
      client.disconnect();
    };
  }, [currentUser?.id]);
}
