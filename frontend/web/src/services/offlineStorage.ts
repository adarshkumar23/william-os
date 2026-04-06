type CacheKey =
  | "schedule_today"
  | "habits_list"
  | "medicine_list"
  | "journal_drafts";

type CacheRecord<T = unknown> = {
  key: CacheKey;
  value: T;
  updatedAt: number;
};

const DB_NAME = "william_offline";
const DB_VERSION = 1;
const STORE_NAME = "cache";

let dbPromise: Promise<IDBDatabase> | null = null;

function openDB(): Promise<IDBDatabase> {
  if (dbPromise) {
    return dbPromise;
  }

  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "key" });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  return dbPromise;
}

async function putRecord<T>(record: CacheRecord<T>): Promise<void> {
  const db = await openDB();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    store.put(record);

    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getRecord<T>(key: CacheKey): Promise<CacheRecord<T> | null> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const request = store.get(key);

    request.onsuccess = () => resolve((request.result as CacheRecord<T>) ?? null);
    request.onerror = () => reject(request.error);
  });
}

export async function cacheTodaySchedule(schedule: unknown): Promise<void> {
  await putRecord({
    key: "schedule_today",
    value: schedule,
    updatedAt: Date.now(),
  });
}

export async function cacheHabitsList(habits: unknown[]): Promise<void> {
  await putRecord({
    key: "habits_list",
    value: habits,
    updatedAt: Date.now(),
  });
}

export async function cacheMedicineList(medicines: unknown[]): Promise<void> {
  await putRecord({
    key: "medicine_list",
    value: medicines,
    updatedAt: Date.now(),
  });
}

export async function saveJournalDrafts(drafts: unknown[]): Promise<void> {
  await putRecord({
    key: "journal_drafts",
    value: drafts,
    updatedAt: Date.now(),
  });
}

export async function getCachedScheduleToday<T = unknown>(): Promise<T | null> {
  const record = await getRecord<T>("schedule_today");
  return record?.value ?? null;
}

export async function getCachedHabitsList<T = unknown[]>(): Promise<T | null> {
  const record = await getRecord<T>("habits_list");
  return record?.value ?? null;
}

export async function getCachedMedicineList<T = unknown[]>(): Promise<T | null> {
  const record = await getRecord<T>("medicine_list");
  return record?.value ?? null;
}

export async function getJournalDrafts<T = unknown[]>(): Promise<T | null> {
  const record = await getRecord<T>("journal_drafts");
  return record?.value ?? null;
}

export async function syncCriticalDataOnReconnect(fetchers: {
  fetchScheduleToday: () => Promise<unknown>;
  fetchHabitsList: () => Promise<unknown[]>;
  fetchMedicineList: () => Promise<unknown[]>;
}): Promise<{
  schedule: unknown;
  habits: unknown[];
  medicine: unknown[];
  journalDrafts: unknown[];
}> {
  const [serverSchedule, serverHabits, serverMedicine, localDrafts] = await Promise.all([
    fetchers.fetchScheduleToday(),
    fetchers.fetchHabitsList(),
    fetchers.fetchMedicineList(),
    getJournalDrafts<unknown[]>(),
  ]);

  await cacheTodaySchedule(serverSchedule);
  await cacheHabitsList(serverHabits);
  await cacheMedicineList(serverMedicine);

  const mergedDrafts = localDrafts ?? [];
  await saveJournalDrafts(mergedDrafts);

  return {
    schedule: serverSchedule,
    habits: serverHabits,
    medicine: serverMedicine,
    journalDrafts: mergedDrafts,
  };
}
