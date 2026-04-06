type TimelineBlock = {
  id?: string;
  title: string;
  category: string;
  start_time: string;
  end_time: string;
  status?: string;
};

export default function ScheduleTimeline({ blocks }: { blocks: TimelineBlock[] }) {
  if (!blocks.length) {
    return <div className="panel p-6">No schedule blocks available yet.</div>;
  }

  return (
    <div className="panel p-5">
      <h3 className="mb-4 font-display text-lg font-bold">Today's Timeline</h3>
      <ol className="relative border-l border-slate-200 pl-4 dark:border-slate-700">
        {blocks.map((block, index) => (
          <li key={block.id || `${block.title}-${index}`} className="mb-5 ml-3 animate-rise">
            <span className="absolute -left-[9px] mt-1 h-4 w-4 rounded-full bg-gradient-to-br from-william-electric to-william-ember" />
            <div className="rounded-xl border border-slate-200 bg-white/70 p-3 dark:border-slate-700 dark:bg-slate-900/70">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {block.start_time} - {block.end_time} • {block.category}
              </p>
              <p className="font-semibold">{block.title}</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">Status: {block.status || "pending"}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
