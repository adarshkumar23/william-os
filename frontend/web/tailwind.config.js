/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        william: {
          ink: "#0B1020",
          paper: "#F7F6F2",
          mist: "#E8EEF5",
          electric: "#0EA5E9",
          ember: "#F97316",
          mint: "#14B8A6",
          berry: "#E11D48"
        }
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Source Sans 3'", "sans-serif"]
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(14,165,233,.15), 0 20px 40px -20px rgba(14,165,233,.55)"
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(18px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        }
      },
      animation: {
        rise: "rise .45s ease-out both"
      }
    }
  },
  plugins: [],
};
