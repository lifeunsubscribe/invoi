/**
 * Welcome Page for First-Time Users
 *
 * Shown on first sign-in when user has no profile data.
 * Provides quick-start guide and feedback collection mechanism.
 */

import theme from "../theme.js";

export default function WelcomePage({ onGetStarted, onNavigate }) {
  const primaryColor = theme.colors.primary;
  const lightBg = theme.colors.background.light;
  const darkText = theme.colors.text.dark;
  const mediumText = theme.colors.text.medium;
  const lightText = theme.colors.text.light;

  const steps = [
    {
      icon: "👤",
      title: "Set up your profile",
      description: "Add your name, contact info, hourly rate, and client details. This information appears on all your invoices."
    },
    {
      icon: "📝",
      title: "Create your first weekly invoice",
      description: "Enter the hours you worked each day. Pick from seven beautiful templates. Preview the PDF before sending."
    },
    {
      icon: "📧",
      title: "Send it to your client",
      description: "Email your invoice directly from Invoi. Track when it's sent, paid, or overdue—all in one place."
    },
    {
      icon: "📊",
      title: "View your invoice history",
      description: "See all your invoices in a calendar view. Export monthly reports for your accountant at tax time."
    }
  ];

  const tips = [
    { emoji: "🎨", text: "Choose from 7 designer templates to match your brand" },
    { emoji: "⚡", text: "Create weekly invoices in under 2 minutes" },
    { emoji: "📱", text: "Access Invoi from any device with a browser" },
    { emoji: "💡", text: "Use tooltips throughout the app for quick help" }
  ];

  return (
    <div style={{
      minHeight: "100vh",
      background: theme.colors.background.gradient,
      fontFamily: "sans-serif",
      padding: "40px 24px"
    }}>
      <div style={{
        maxWidth: "800px",
        margin: "0 auto"
      }}>
        {/* Header */}
        <div style={{
          textAlign: "center",
          marginBottom: 48
        }}>
          <div style={{
            fontSize: 64,
            marginBottom: 16
          }}>
            👋
          </div>
          <h1 style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: 48,
            fontWeight: 700,
            color: darkText,
            marginBottom: 16,
            lineHeight: 1.2
          }}>
            Welcome to Invoi!
          </h1>
          <p style={{
            fontSize: 20,
            color: mediumText,
            marginBottom: 0,
            lineHeight: 1.6
          }}>
            You're all set up and ready to create professional invoices in minutes.
            Let's get you started.
          </p>
        </div>

        {/* Quick Start Guide */}
        <div style={{
          background: "white",
          borderRadius: 16,
          padding: "32px",
          boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
          marginBottom: 32
        }}>
          <h2 style={{
            fontSize: 24,
            fontWeight: 700,
            color: darkText,
            marginBottom: 24,
            fontFamily: "'Playfair Display', serif"
          }}>
            Quick Start Guide
          </h2>

          <div style={{
            display: "flex",
            flexDirection: "column",
            gap: 24
          }}>
            {steps.map((step, index) => (
              <div
                key={index}
                style={{
                  display: "flex",
                  gap: 16,
                  alignItems: "flex-start"
                }}
              >
                <div style={{
                  fontSize: 40,
                  flexShrink: 0,
                  width: 56,
                  height: 56,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: lightBg,
                  borderRadius: 12,
                  border: `2px solid ${primaryColor}20`
                }}>
                  {step.icon}
                </div>
                <div style={{ flex: 1, paddingTop: 4 }}>
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 6
                  }}>
                    <span style={{
                      fontSize: 14,
                      fontWeight: 700,
                      color: primaryColor,
                      background: `${primaryColor}15`,
                      padding: "2px 8px",
                      borderRadius: 4
                    }}>
                      Step {index + 1}
                    </span>
                    <h3 style={{
                      fontSize: 18,
                      fontWeight: 600,
                      color: darkText,
                      margin: 0
                    }}>
                      {step.title}
                    </h3>
                  </div>
                  <p style={{
                    fontSize: 15,
                    color: mediumText,
                    margin: 0,
                    lineHeight: 1.6
                  }}>
                    {step.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Tips Section */}
        <div style={{
          background: "white",
          borderRadius: 16,
          padding: "32px",
          boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
          marginBottom: 32
        }}>
          <h2 style={{
            fontSize: 20,
            fontWeight: 700,
            color: darkText,
            marginBottom: 20,
            fontFamily: "'Playfair Display', serif"
          }}>
            Quick Tips
          </h2>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 16
          }}>
            {tips.map((tip, index) => (
              <div
                key={index}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 10
                }}
              >
                <span style={{ fontSize: 20, flexShrink: 0 }}>
                  {tip.emoji}
                </span>
                <p style={{
                  fontSize: 14,
                  color: mediumText,
                  margin: 0,
                  lineHeight: 1.5
                }}>
                  {tip.text}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* CTA Button */}
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16
        }}>
          <button
            onClick={onGetStarted}
            style={{
              padding: "16px 48px",
              background: theme.gradients.primaryButton(primaryColor),
              border: "none",
              borderRadius: 12,
              color: "white",
              fontWeight: 700,
              fontSize: 18,
              cursor: "pointer",
              boxShadow: theme.shadows.primary,
              transition: "all 0.2s"
            }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow = theme.shadows.primaryHover;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = theme.shadows.primary;
            }}
          >
            Complete Your Profile
          </button>

          <button
            onClick={() => onNavigate && onNavigate("menu")}
            style={{
              background: "transparent",
              border: "none",
              color: lightText,
              fontSize: 14,
              cursor: "pointer",
              textDecoration: "underline",
              padding: "8px 16px"
            }}
          >
            Skip for now
          </button>
        </div>

        {/* Feedback Link */}
        <div style={{
          marginTop: 48,
          padding: "24px",
          background: `${primaryColor}10`,
          borderRadius: 12,
          border: `1px solid ${primaryColor}30`,
          textAlign: "center"
        }}>
          <p style={{
            fontSize: 15,
            color: mediumText,
            margin: "0 0 12px 0"
          }}>
            <strong style={{ color: darkText }}>You're part of our beta program!</strong>
            <br />
            Your feedback helps us build a better invoicing experience.
          </p>
          <a
            href="mailto:feedback@goinvoi.com?subject=Invoi Beta Feedback"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "10px 20px",
              background: "white",
              border: `2px solid ${primaryColor}`,
              borderRadius: 8,
              color: primaryColor,
              fontWeight: 600,
              fontSize: 14,
              textDecoration: "none",
              cursor: "pointer",
              transition: "all 0.2s"
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = primaryColor;
              e.currentTarget.style.color = "white";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = "white";
              e.currentTarget.style.color = primaryColor;
            }}
          >
            📧 Send Feedback
          </a>
        </div>
      </div>
    </div>
  );
}
