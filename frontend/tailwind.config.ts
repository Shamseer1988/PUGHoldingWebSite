import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "1rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        // Paris United Group brand palette — anchored to the logo's
        // deep forest green wordmark and warm tan/gold mandala.
        pug: {
          green: {
            DEFAULT: "hsl(145 45% 20%)",
            50: "hsl(145 30% 96%)",
            100: "hsl(145 32% 92%)",
            200: "hsl(145 32% 82%)",
            300: "hsl(145 35% 65%)",
            400: "hsl(145 40% 45%)",
            500: "hsl(145 45% 30%)",
            600: "hsl(145 50% 22%)",
            700: "hsl(145 55% 16%)",
            800: "hsl(145 60% 12%)",
            900: "hsl(145 60% 8%)",
          },
          gold: {
            DEFAULT: "hsl(36 45% 55%)",
            50: "hsl(40 60% 96%)",
            100: "hsl(40 55% 90%)",
            200: "hsl(38 50% 80%)",
            300: "hsl(36 50% 70%)",
            400: "hsl(36 48% 62%)",
            500: "hsl(36 45% 55%)",
            600: "hsl(34 45% 45%)",
            700: "hsl(32 45% 36%)",
            800: "hsl(30 40% 28%)",
            900: "hsl(28 38% 20%)",
          },
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.4s ease-out both",
      },
    },
  },
  plugins: [animate],
};

export default config;
