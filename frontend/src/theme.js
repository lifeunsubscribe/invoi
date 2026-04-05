/**
 * Invoi Brand Theme
 *
 * Centralized color palette and design tokens for consistent branding.
 * Used across landing pages, templates, and app components.
 */

const theme = {
  colors: {
    // Primary brand color
    primary: "#b76e79",
    primaryRgb: "183, 110, 121",

    // Text colors
    text: {
      dark: "#2c1810",
      medium: "#6a4a40",
      light: "#9a8070",
    },

    // Background colors
    background: {
      light: "#fdf8f4",
      gradient: "linear-gradient(160deg, #f9f3ee, #f2ebe4)",
    },

    // Border colors
    border: {
      light: "#e8ddd4",
      pink: "#f0dce0",
      muted: "#d0c0b0",
    },

    // Info box backgrounds
    info: {
      background: "#fdf2f4",
      border: "#f0dce0",
    },
  },

  // Utility functions
  utils: {
    /**
     * Generate rgba color with opacity
     * @param {string} rgb - RGB values as "r, g, b"
     * @param {number} alpha - Opacity from 0 to 1
     * @returns {string} rgba color string
     */
    withOpacity: (rgb, alpha) => `rgba(${rgb}, ${alpha})`,

    /**
     * Generate primary color with opacity
     * @param {number} alpha - Opacity from 0 to 1
     * @returns {string} rgba color string
     */
    primaryWithOpacity: (alpha) => `rgba(183, 110, 121, ${alpha})`,
  },

  // Common gradients
  gradients: {
    primaryButton: (primaryColor) =>
      `linear-gradient(135deg, ${primaryColor}, rgba(183, 110, 121, 0.85))`,
    ctaBackground: "linear-gradient(135deg, rgba(183, 110, 121, 0.12), rgba(183, 110, 121, 0.24))",
  },

  // Common shadows
  shadows: {
    primary: "0 6px 24px rgba(183, 110, 121, 0.3)",
    primaryHover: "0 10px 32px rgba(183, 110, 121, 0.4)",
  },
};

export default theme;
