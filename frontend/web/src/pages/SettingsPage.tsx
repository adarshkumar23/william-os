import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";

export default function SettingsPage() {
  const { currentUser } = useAuth();

  const [telegramChatId, setTelegramChatId] = useState("");
  const [telegramUsername, setTelegramUsername] = useState("");
  const [telegramStatus, setTelegramStatus] = useState<any | null>(null);

  const [devices, setDevices] = useState<any[]>([]);
  const [deviceName, setDeviceName] = useState("Apple Watch");
  const [deviceType, setDeviceType] = useState("apple_watch");

  const load = async () => {
    const [status, deviceData] = await Promise.all([
      api.messaging.telegramStatus().catch(() => null),
      api.fitness.devices().catch(() => []),
    ]);
    setTelegramStatus(status);
    setDevices(deviceData);
  };

  useEffect(() => {
    void load();
  }, []);

  const handleTelegramLink = async (event: FormEvent) => {
    event.preventDefault();
    await api.messaging.linkTelegram({
      telegram_chat_id: Number(telegramChatId),
      telegram_username: telegramUsername,
    });
    await load();
  };

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="panel p-5">
        <h1 className="font-display text-3xl font-bold">Settings</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Profile: {currentUser?.full_name}</p>
        <p className="text-sm text-slate-600 dark:text-slate-300">Timezone: {currentUser?.timezone}</p>
        <p className="text-sm text-slate-600 dark:text-slate-300">Wake/Sleep: {currentUser?.wake_time} / {currentUser?.sleep_time}</p>
      </section>

      <section className="panel p-5">
        <h2 className="font-display text-xl font-bold">Telegram Link</h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
          Status: {telegramStatus?.is_verified ? `Linked (${telegramStatus.telegram_username})` : "Not linked"}
        </p>
        <form className="mt-3 space-y-3" onSubmit={handleTelegramLink}>
          <input
            className="w-full rounded-xl border border-slate-300 bg-white/80 p-2 dark:border-slate-700 dark:bg-slate-900"
            placeholder="Telegram Chat ID"
            value={telegramChatId}
            onChange={(event) => setTelegramChatId(event.target.value)}
          />
          <input
            className="w-full rounded-xl border border-slate-300 bg-white/80 p-2 dark:border-slate-700 dark:bg-slate-900"
            placeholder="Telegram Username"
            value={telegramUsername}
            onChange={(event) => setTelegramUsername(event.target.value)}
          />
          <button className="btn-primary" type="submit">Link Telegram</button>
        </form>
      </section>

      <section className="panel p-5 lg:col-span-2">
        <h2 className="font-display text-xl font-bold">Fitness Devices</h2>
        <form
          className="mt-3 grid gap-2 md:grid-cols-3"
          onSubmit={async (event) => {
            event.preventDefault();
            await api.fitness.addDevice({ device_type: deviceType, device_name: deviceName });
            await load();
          }}
        >
          <input
            className="rounded-xl border border-slate-300 bg-white/80 p-2 dark:border-slate-700 dark:bg-slate-900"
            value={deviceName}
            onChange={(event) => setDeviceName(event.target.value)}
          />
          <input
            className="rounded-xl border border-slate-300 bg-white/80 p-2 dark:border-slate-700 dark:bg-slate-900"
            value={deviceType}
            onChange={(event) => setDeviceType(event.target.value)}
          />
          <button className="btn-primary" type="submit">Add Device</button>
        </form>

        <div className="mt-4 grid gap-2 md:grid-cols-2">
          {devices.map((device) => (
            <div key={device.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
              <p className="font-semibold">{device.device_name}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{device.device_type}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
