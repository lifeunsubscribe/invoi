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

    // Template-specific color schemes
    caringHands: {
      accent: "#7ab5a8",
      headerBg: "#1a2a3a",
      headerMeta: "#8aacaa",
      textDark: "#1a2a3a",
      textMedium: "#4a6a60",
      textLight: "#7a9a90",
      rowOdd: "#f4f9f8",
      infoBg: "#f4f8f8",
      infoBorder: "#e0eeec",
      chromeBg: "#f4f8f8",
      chromeBorder: "#e0eeec",
    },
    garden: {
      accent: "#5a8a5a",
      headerBg: "linear-gradient(135deg,#2d4a2d,#3d6b3d)",
      headerAccent: "#a8d8a0",
      headerName: "#e8f5e4",
      headerMeta: "#a8c8a0",
      textDark: "#2d4a2d",
      textMedium: "#6a8a60",
      textLight: "#7a9a70",
      rowEven: "#fffef8",
      rowOdd: "#f4f8f0",
      infoBg: "#f6fbf4",
      infoBorder: "#d0e8c8",
      footerBg: "#f0f8ec",
      footerText: "#7a9a70",
      dividerBg: "#5a8a5a",
      dividerText: "#c8e8c0",
      chromeBg: "#f6fbf4",
      chromeBorder: "#d0e8c8",
      chromeMuted: "#7a9a70",
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
    primaryWithOpacity: (alpha) => `rgba(${theme.colors.primaryRgb}, ${alpha})`,
  },

  // Common gradients
  gradients: {
    primaryButton: (primaryColor) =>
      `linear-gradient(135deg, ${primaryColor}, rgba(${theme.colors.primaryRgb}, 0.85))`,
    ctaBackground: `linear-gradient(135deg, rgba(${theme.colors.primaryRgb}, 0.12), rgba(${theme.colors.primaryRgb}, 0.24))`,
  },

  // Common shadows
  shadows: {
    primary: `0 6px 24px rgba(${theme.colors.primaryRgb}, 0.3)`,
    primaryHover: `0 10px 32px rgba(${theme.colors.primaryRgb}, 0.4)`,
  },
};

export default theme;
