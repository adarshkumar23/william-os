export const fadeInUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] },
};

export const staggerContainer = {
  animate: { transition: { staggerChildren: 0.07 } },
};

export const cardHover = {
  whileHover: { y: -2, transition: { duration: 0.2 } },
};

export const scaleIn = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  transition: { duration: 0.2 },
};

export const slideInRight = {
  initial: { opacity: 0, x: 24 },
  animate: { opacity: 1, x: 0 },
  transition: { duration: 0.3 },
};

export function reduceMotion<T extends { initial?: unknown; animate?: unknown; exit?: unknown; transition?: unknown }>(
  shouldReduceMotion: boolean,
  variant: T,
): T {
  if (!shouldReduceMotion) {
    return variant;
  }

  return {
    ...variant,
    initial: { opacity: 1, y: 0, x: 0, scale: 1 },
    animate: { opacity: 1, y: 0, x: 0, scale: 1 },
    exit: { opacity: 1, y: 0, x: 0, scale: 1 },
    transition: { duration: 0 },
  } as T;
}
