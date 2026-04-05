/**
 * Privacy Policy Page
 *
 * Required for Google OAuth approval and legal compliance.
 * Covers data collection, storage, user rights, and contact information.
 *
 * Last Updated: 2026-04-04
 */

import theme from "../theme.js";

export default function PrivacyPolicy({ onBack }) {
  const primaryColor = theme.colors.primary;
  const darkText = theme.colors.text.dark;
  const lightText = theme.colors.text.light;
  const lightBg = theme.colors.background.light;

  return (
    <div style={{
      minHeight: "100vh",
      background: theme.colors.background.gradient,
      fontFamily: "sans-serif"
    }}>
      {/* Header */}
      <header style={{
        padding: "20px 24px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        maxWidth: "900px",
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
          onClick={onBack || (() => window.history.back())}
          style={{
            padding: "8px 20px",
            background: "white",
            border: `2px solid ${primaryColor}`,
            borderRadius: 8,
            color: primaryColor,
            fontWeight: 600,
            fontSize: 14,
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
          ← Back
        </button>
      </header>

      {/* Content */}
      <main style={{
        maxWidth: "800px",
        margin: "0 auto",
        padding: "40px 24px 80px",
        background: "white",
        borderRadius: 16,
        marginTop: 20,
        marginBottom: 40,
        boxShadow: "0 2px 12px rgba(0, 0, 0, 0.08)"
      }}>
        <h1 style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: 42,
          fontWeight: 700,
          color: darkText,
          marginBottom: 12
        }}>
          Privacy Policy
        </h1>
        <p style={{
          fontSize: 14,
          color: lightText,
          marginBottom: 40
        }}>
          Last Updated: April 4, 2026
        </p>

        <Section title="Introduction">
          <p>
            Invoi ("we," "our," or "us") is committed to protecting your privacy. This Privacy Policy
            explains how we collect, use, disclose, and safeguard your information when you use our
            invoicing application and services (the "Service").
          </p>
          <p>
            By using Invoi, you agree to the collection and use of information in accordance with this
            policy. If you do not agree with our policies and practices, please do not use the Service.
          </p>
        </Section>

        <Section title="Information We Collect">
          <h3 style={{ fontSize: 18, fontWeight: 700, color: darkText, marginTop: 20, marginBottom: 10 }}>
            Information You Provide
          </h3>
          <p>When you use Invoi, we collect information that you provide directly, including:</p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Account information (name, email address, profile details)</li>
            <li>Business information (address, occupation, hourly rate)</li>
            <li>Client information (client names, email addresses, contact details)</li>
            <li>Invoice data (hours worked, services provided, payment terms)</li>
            <li>Service logs and notes (for home health aides and other service providers)</li>
            <li>Payment and billing information (for Pro subscriptions, when available)</li>
          </ul>

          <h3 style={{ fontSize: 18, fontWeight: 700, color: darkText, marginTop: 20, marginBottom: 10 }}>
            Information Collected Automatically
          </h3>
          <p>We automatically collect certain information when you use the Service:</p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Log data (IP address, browser type, pages visited, timestamps)</li>
            <li>Device information (device type, operating system)</li>
            <li>Usage data (features used, preferences, interaction patterns)</li>
          </ul>

          <h3 style={{ fontSize: 18, fontWeight: 700, color: darkText, marginTop: 20, marginBottom: 10 }}>
            Google OAuth Information
          </h3>
          <p>
            When you sign in with Google, we receive your basic profile information (name, email address,
            profile picture) from Google. We use this information to create and authenticate your account.
            We do not have access to your Google password.
          </p>
        </Section>

        <Section title="How We Use Your Information">
          <p>We use the information we collect to:</p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Provide, maintain, and improve the Service</li>
            <li>Create and manage your account</li>
            <li>Generate and deliver invoices to your clients</li>
            <li>Process payments for Pro subscriptions (when available)</li>
            <li>Send you service-related communications and updates</li>
            <li>Respond to your inquiries and provide customer support</li>
            <li>Monitor and analyze usage patterns to improve user experience</li>
            <li>Detect, prevent, and address technical issues and security threats</li>
            <li>Comply with legal obligations and enforce our Terms of Service</li>
          </ul>
        </Section>

        <Section title="How We Store Your Information">
          <p>
            Your data is stored securely on Amazon Web Services (AWS) infrastructure in the United States:
          </p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>User profiles and configuration data are stored in DynamoDB (encrypted at rest)</li>
            <li>Generated invoice PDFs and uploaded logos are stored in Amazon S3 (encrypted at rest)</li>
            <li>All data transmission occurs over encrypted HTTPS connections</li>
            <li>We implement industry-standard security measures to protect your data</li>
          </ul>
          <p>
            We retain your data for as long as your account is active or as needed to provide the Service.
            You may request deletion of your account and data at any time (see "Your Rights" below).
          </p>
        </Section>

        <Section title="How We Share Your Information">
          <p>We do not sell or rent your personal information. We may share your information only in the following circumstances:</p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>
              <strong>With your clients:</strong> When you send invoices, your name, business information,
              and invoice details are shared with the recipients you specify
            </li>
            <li>
              <strong>With service providers:</strong> We may share information with third-party service
              providers who perform services on our behalf (e.g., AWS for hosting, email delivery services)
            </li>
            <li>
              <strong>For legal reasons:</strong> We may disclose information if required by law, legal
              process, or governmental request, or to protect the rights, property, or safety of Invoi,
              our users, or others
            </li>
            <li>
              <strong>Business transfers:</strong> If Invoi is involved in a merger, acquisition, or sale
              of assets, your information may be transferred as part of that transaction
            </li>
          </ul>
        </Section>

        <Section title="Your Rights">
          <p>Depending on your location, you may have certain rights regarding your personal information:</p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li><strong>Access:</strong> You can access and review your information through your profile settings</li>
            <li><strong>Correction:</strong> You can update or correct your information at any time</li>
            <li><strong>Deletion:</strong> You can request deletion of your account and associated data</li>
            <li><strong>Data portability:</strong> You can export your invoice data in PDF or CSV format</li>
            <li><strong>Opt-out:</strong> You can opt out of non-essential communications</li>
          </ul>
          <p>
            To exercise these rights, please contact us at <a href="mailto:privacy@goinvoi.com" style={{ color: primaryColor, textDecoration: "none", fontWeight: 600 }}>privacy@goinvoi.com</a>.
          </p>
        </Section>

        <Section title="Cookies and Tracking">
          <p>
            Invoi uses minimal cookies and local storage to maintain your session and preferences. We do not
            use third-party advertising cookies or tracking pixels. Essential cookies are required for the
            Service to function properly.
          </p>
        </Section>

        <Section title="Third-Party Links">
          <p>
            The Service may contain links to third-party websites or services (e.g., Google for authentication).
            We are not responsible for the privacy practices of these third parties. We encourage you to review
            their privacy policies.
          </p>
        </Section>

        <Section title="Children's Privacy">
          <p>
            Invoi is not intended for use by individuals under the age of 18. We do not knowingly collect
            personal information from children. If you believe we have collected information from a child,
            please contact us immediately.
          </p>
        </Section>

        <Section title="International Users">
          <p>
            Invoi is operated in the United States. If you access the Service from outside the United States,
            your information will be transferred to and processed in the United States. By using the Service,
            you consent to this transfer and processing.
          </p>
        </Section>

        <Section title="Changes to This Privacy Policy">
          <p>
            We may update this Privacy Policy from time to time. We will notify you of any material changes
            by posting the new policy on this page and updating the "Last Updated" date. Your continued use
            of the Service after changes are posted constitutes acceptance of the updated policy.
          </p>
        </Section>

        <Section title="Contact Us">
          <p>
            If you have questions or concerns about this Privacy Policy or our privacy practices, please contact us:
          </p>
          <p style={{ marginTop: 16, padding: 16, background: lightBg, borderRadius: 8, border: "2px solid #f0dce0" }}>
            <strong>Email:</strong> <a href="mailto:privacy@goinvoi.com" style={{ color: primaryColor, textDecoration: "none", fontWeight: 600 }}>privacy@goinvoi.com</a><br />
            <strong>Subject Line:</strong> Privacy Inquiry - Invoi
          </p>
          <p style={{ marginTop: 20, fontSize: 14, color: lightText, fontStyle: "italic" }}>
            Note: This privacy policy template is provided for informational purposes. We recommend consulting
            with a qualified attorney to ensure compliance with all applicable laws and regulations.
          </p>
        </Section>
      </main>

      {/* Footer */}
      <footer style={{
        padding: "40px 24px",
        textAlign: "center",
        color: lightText,
        fontSize: 14
      }}>
        <div style={{
          maxWidth: "800px",
          margin: "0 auto"
        }}>
          <div style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: 20,
            fontWeight: 700,
            color: darkText,
            marginBottom: 12
          }}>Invoi</div>
          <div style={{ marginBottom: 8 }}>Invoicing for hourly contractors</div>
          <div>© 2026 Invoi. Built for people who work by the hour.</div>
        </div>
      </footer>
    </div>
  );
}

// Reusable section component for consistent styling
function Section({ title, children }) {
  const darkText = "#2c1810";
  const mediumText = "#6a4a40";

  return (
    <section style={{ marginBottom: 40 }}>
      <h2 style={{
        fontFamily: "'Playfair Display', serif",
        fontSize: 26,
        fontWeight: 700,
        color: darkText,
        marginBottom: 16,
        paddingBottom: 8,
        borderBottom: "2px solid #f0dce0"
      }}>
        {title}
      </h2>
      <div style={{
        fontSize: 16,
        lineHeight: 1.8,
        color: mediumText
      }}>
        {children}
      </div>
    </section>
  );
}
