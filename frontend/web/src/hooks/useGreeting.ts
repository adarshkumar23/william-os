export function useGreeting(name?: string | null) {
  const hour = new Date().getHours();
  const part =
    hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : hour < 22 ? "Good evening" : "Good night";

  return name ? `${part}, ${name.split(" ")[0]}` : part;
}
