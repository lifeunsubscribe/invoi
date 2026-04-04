/**
 * Marketing Landing Page for Invoi
 *
 * Shown to unauthenticated users at goinvoi.com root.
 * Explains value proposition for hourly 1099 contractors.
 */

export default function LandingPage({ onSignIn, onNavigate }) {
  const primaryColor = "#b76e79";
  const lightBg = "#fdf8f4";
  const darkText = "#2c1810";
  const mediumText = "#6a4a40";
  const lightText = "#9a8070";

  const occupations = [
    { icon: "🏥", name: "Home Health Aides" },
    { icon: "📚", name: "Tutors & Instructors" },
    { icon: "🧹", name: "House Cleaners" },
    { icon: "💪", name: "Personal Trainers" },
    { icon: "🐕", name: "Pet Sitters & Dog Walkers" },
    { icon: "🔧", name: "Handypeople" },
  ];

  const features = [
    {
      icon: "⚡",
      title: "Weekly invoices in minutes",
      description: "Enter your hours, pick a beautiful template, and generate a professional PDF. No spreadsheets, no hassle."
    },
    {
      icon: "🎨",
      title: "Professional templates",
      description: "Seven designer themes to match your brand. Morning Light, Coastal, Garden, and more."
    },
    {
      icon: "📧",
      title: "Email delivery",
      description: "Send invoices directly to your clients from the app. Track sent, paid, and overdue invoices."
    },
    {
      icon: "📊",
      title: "Monthly reports for tax time",
      description: "Automatic monthly summaries with all your invoices. Export for your accountant with one click."
    }
  ];

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(160deg, #f9f3ee, #f2ebe4)",
      fontFamily: "sans-serif"
    }}>
      {/* Header */}
      <header style={{
        padding: "20px 24px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        maxWidth: "1200px",
        margin: "0 auto"
      }}>
        <div style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: 28,
          fontWeight: 700,
          color: darkText,
          display: "flex",
          alignItems: "center",
          gap: 8
        }}>
          <span style={{ fontSize: 32 }}>📄</span>
          Invoi
        </div>
        <button
          onClick={onSignIn}
          style={{
            padding: "10px 24px",
            background: "white",
            border: `2px solid ${primaryColor}`,
            borderRadius: 8,
            color: primaryColor,
            fontWeight: 600,
            fontSize: 15,
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
          Sign in with Google
        </button>
      </header>

      {/* Hero Section */}
      <section style={{
        maxWidth: "1200px",
        margin: "0 auto",
        padding: "60px 24px",
        textAlign: "center"
      }}>
        <h1 style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: 56,
          fontWeight: 700,
          color: darkText,
          marginBottom: 20,
          lineHeight: 1.2
        }}>
          Invoicing for people who<br />work by the hour
        </h1>
        <p style={{
          fontSize: 20,
          color: mediumText,
          marginBottom: 40,
          maxWidth: 700,
          margin: "0 auto 40px"
        }}>
          Built for hourly 1099 contractors who need simple, beautiful invoices.
          Enter your hours, pick a template, and send. No accounting degree required.
        </p>
        <button
          onClick={onSignIn}
          style={{
            padding: "16px 48px",
            background: `linear-gradient(135deg, ${primaryColor}, rgba(183, 110, 121, 0.85))`,
            border: "none",
            borderRadius: 12,
            color: "white",
            fontWeight: 700,
            fontSize: 18,
            cursor: "pointer",
            boxShadow: `0 6px 24px rgba(183, 110, 121, 0.3)`,
            transition: "all 0.2s"
          }}
          onMouseEnter={e => {
            e.currentTarget.style.transform = "translateY(-2px)";
            e.currentTarget.style.boxShadow = `0 10px 32px rgba(183, 110, 121, 0.4)`;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = `0 6px 24px rgba(183, 110, 121, 0.3)`;
          }}
        >
          Get Started Free
        </button>
      </section>

      {/* Who This Is For Section */}
      <section style={{
        background: "white",
        padding: "60px 24px",
        borderTop: `1px solid #e8ddd4`,
        borderBottom: `1px solid #e8ddd4`
      }}>
        <div style={{
          maxWidth: "1200px",
          margin: "0 auto"
        }}>
          <h2 style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: 36,
            fontWeight: 700,
            color: darkText,
            textAlign: "center",
            marginBottom: 16
          }}>
            Built for contractors like you
          </h2>
          <p style={{
            fontSize: 18,
            color: mediumText,
            textAlign: "center",
            marginBottom: 48,
            maxWidth: 700,
            margin: "0 auto 48px"
          }}>
            Whether you're caring for patients, training clients, or providing services,
            Invoi handles your invoicing so you can focus on your work.
          </p>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 24,
            maxWidth: 900,
            margin: "0 auto"
          }}>
            {occupations.map((occ, i) => (
              <div key={i} style={{
                padding: "24px",
                background: lightBg,
                borderRadius: 12,
                textAlign: "center",
                border: "2px solid #f0dce0"
              }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>{occ.icon}</div>
                <div style={{
                  fontSize: 15,
                  fontWeight: 600,
                  color: darkText
                }}>{occ.name}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section style={{
        padding: "60px 24px",
        maxWidth: "1200px",
        margin: "0 auto"
      }}>
        <h2 style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: 36,
          fontWeight: 700,
          color: darkText,
          textAlign: "center",
          marginBottom: 48
        }}>
          Everything you need, nothing you don't
        </h2>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 32
        }}>
          {features.map((feat, i) => (
            <div key={i} style={{
              padding: "32px",
              background: "white",
              borderRadius: 16,
              border: "2px solid #e8ddd4",
              boxShadow: "0 2px 12px rgba(0, 0, 0, 0.04)"
            }}>
              <div style={{
                fontSize: 48,
                marginBottom: 16
              }}>{feat.icon}</div>
              <h3 style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: 22,
                fontWeight: 700,
                color: darkText,
                marginBottom: 12
              }}>{feat.title}</h3>
              <p style={{
                fontSize: 16,
                color: mediumText,
                lineHeight: 1.6
              }}>{feat.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section style={{
        padding: "60px 24px",
        background: `linear-gradient(135deg, rgba(183, 110, 121, 0.12), rgba(183, 110, 121, 0.24))`,
        borderTop: `4px solid ${primaryColor}`,
        textAlign: "center"
      }}>
        <div style={{
          maxWidth: "700px",
          margin: "0 auto"
        }}>
          <h2 style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: 42,
            fontWeight: 700,
            color: darkText,
            marginBottom: 20
          }}>
            Ready to simplify your invoicing?
          </h2>
          <p style={{
            fontSize: 18,
            color: mediumText,
            marginBottom: 36
          }}>
            Sign in with Google and create your first invoice in minutes.
            No credit card required.
          </p>
          <button
            onClick={onSignIn}
            style={{
              padding: "16px 48px",
              background: `linear-gradient(135deg, ${primaryColor}, rgba(183, 110, 121, 0.85))`,
              border: "none",
              borderRadius: 12,
              color: "white",
              fontWeight: 700,
              fontSize: 18,
              cursor: "pointer",
              boxShadow: `0 6px 24px rgba(183, 110, 121, 0.3)`,
              transition: "all 0.2s"
            }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow = `0 10px 32px rgba(183, 110, 121, 0.4)`;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = `0 6px 24px rgba(183, 110, 121, 0.3)`;
            }}
          >
            Sign in with Google
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer style={{
        padding: "40px 24px",
        textAlign: "center",
        color: lightText,
        fontSize: 14
      }}>
        <div style={{
          maxWidth: "1200px",
          margin: "0 auto"
        }}>
          <div style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: 20,
            fontWeight: 700,
            color: darkText,
            marginBottom: 12
          }}>Invoi</div>
          <div>Invoicing for hourly contractors</div>
          <div style={{
            marginTop: 16,
            display: "flex",
            gap: 20,
            justifyContent: "center",
            alignItems: "center",
            flexWrap: "wrap"
          }}>
            <button
              onClick={() => onNavigate && onNavigate("privacy")}
              style={{
                background: "none",
                border: "none",
                color: primaryColor,
                fontSize: 14,
                fontWeight: 600,
                cursor: "pointer",
                textDecoration: "none",
                padding: 0
              }}
              onMouseEnter={e => e.currentTarget.style.textDecoration = "underline"}
              onMouseLeave={e => e.currentTarget.style.textDecoration = "none"}
            >
              Privacy Policy
            </button>
            <span style={{ color: "#d0c0b0" }}>•</span>
            <button
              onClick={() => onNavigate && onNavigate("terms")}
              style={{
                background: "none",
                border: "none",
                color: primaryColor,
                fontSize: 14,
                fontWeight: 600,
                cursor: "pointer",
                textDecoration: "none",
                padding: 0
              }}
              onMouseEnter={e => e.currentTarget.style.textDecoration = "underline"}
              onMouseLeave={e => e.currentTarget.style.textDecoration = "none"}
            >
              Terms of Service
            </button>
          </div>
          <div style={{ marginTop: 12 }}>© 2026 Invoi. Built for people who work by the hour.</div>
        </div>
      </footer>
    </div>
  );
}
