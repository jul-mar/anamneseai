/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./*.{html,js}"],
  theme: {
    extend: {},
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: [
      {
        medical: {
          "primary": "#3A6EA5",         // A calming, professional blue for user messages and primary actions
          "primary-content": "#ffffff", // White text on primary color
          "secondary": "#EBF0F6",       // A very light, neutral grey for assistant messages
          "secondary-content": "#1f2937", // Dark text for high readability
          "accent": "#27AE60",          // A trustworthy green for success states or highlights
          "neutral": "#3d4451",         // A neutral color for text
          "base-100": "#ffffff",        // Main content background (chatbox)
          "base-200": "#F9FAFB",        // Slightly off-white page background
          "base-300": "#E5E7EB",        // For borders
          "info": "#3ABFF8",
          "success": "#36D399",
          "warning": "#FBBD23",
          "error": "#F87272",
        },
      },
    ],
  },
} 