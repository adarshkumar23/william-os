import { AnimatePresence, motion } from "framer-motion";
import { RotateCw } from "lucide-react";
import { useState } from "react";

type FlashCardProps = {
  question: string;
  answer: string;
  onRate: (quality: number) => Promise<void>;
};

export default function FlashCard({ question, answer, onRate }: FlashCardProps) {
  const [flipped, setFlipped] = useState(false);

  return (
    <div className="card p-6">
      <button
        type="button"
        className="mb-4 inline-flex items-center gap-2 rounded-lg border border-[rgb(var(--border))] px-3 py-1 text-xs"
        onClick={() => setFlipped((prev) => !prev)}
      >
        <RotateCw className="h-3.5 w-3.5" /> Flip card
      </button>

      <AnimatePresence mode="wait">
        <motion.div
          key={flipped ? "answer" : "question"}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          className="min-h-[120px]"
        >
          <p className="mb-2 text-xs uppercase tracking-wider text-[rgb(var(--text-dim))]">
            {flipped ? "Answer" : "Question"}
          </p>
          <p className="text-lg font-medium leading-relaxed">{flipped ? answer : question}</p>
        </motion.div>
      </AnimatePresence>

      {flipped ? (
        <div className="mt-6 grid grid-cols-6 gap-2">
          {[0, 1, 2, 3, 4, 5].map((score) => (
            <button
              key={score}
              type="button"
              className="rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] py-2 text-sm font-semibold"
              onClick={() => void onRate(score)}
            >
              {score}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
